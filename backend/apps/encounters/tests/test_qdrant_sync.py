"""
Verifies apps/encounters/signals.py actually keeps Qdrant in sync with
Postgres writes to Encounter. Because Encounter's post_save handler defers
to `transaction.on_commit` (deliberately - see that module's docstring), and
Django's plain TestCase wraps each test in a transaction that is rolled back
rather than committed, these callbacks do not fire on their own here. We use
`captureOnCommitCallbacks(execute=True)` to run them explicitly, which
exercises the real signal pipeline end-to-end against the embedded
`:memory:` Qdrant client.
"""
from django.conf import settings
from django.test import TestCase

from apps.common import qdrant_store
from apps.common.test_utils import create_user
from apps.encounters.models import Encounter
from apps.patients.models import Patient


class QdrantSyncOnSaveTests(TestCase):
    def setUp(self):
        qdrant_store.reset_client()
        self.clinician = create_user(email="doc@example.com")
        self.patient = Patient.objects.create(full_name="Pat One", date_of_birth="1990-01-01", mrn="SYNC-1")

    def test_create_upserts_point_into_qdrant(self):
        with self.captureOnCommitCallbacks(execute=True):
            encounter = Encounter.objects.create(
                patient=self.patient,
                clinician=self.clinician,
                specialty=Encounter.Specialty.CARDIOLOGY,
                chief_complaint="Chest pain on exertion",
                notes="Risk factors include hypertension and smoking",
                diagnosis="Stable angina",
                treatment="Nitroglycerin PRN",
                consent_for_research=True,
            )

        client = qdrant_store.get_client()
        points = client.retrieve(settings.QDRANT_COLLECTION, ids=[encounter.id], with_vectors=True)
        self.assertEqual(len(points), 1)
        self.assertEqual(len(points[0].vector), settings.EMBEDDING_DIMENSIONS)
        self.assertEqual(points[0].payload["specialty"], "cardiology")
        self.assertTrue(points[0].payload["consent_for_research"])
        self.assertEqual(points[0].payload["clinician_id"], self.clinician.id)

    def test_update_recomputes_and_reupserts_vector(self):
        with self.captureOnCommitCallbacks(execute=True):
            encounter = Encounter.objects.create(
                patient=self.patient,
                clinician=self.clinician,
                specialty=Encounter.Specialty.DERMATOLOGY,
                chief_complaint="Itchy rash",
                notes="On the arms",
                diagnosis="Eczema",
                treatment="Topical steroid",
            )
        client = qdrant_store.get_client()
        original_vector = client.retrieve(
            settings.QDRANT_COLLECTION, ids=[encounter.id], with_vectors=True
        )[0].vector

        with self.captureOnCommitCallbacks(execute=True):
            encounter.diagnosis = "Psoriasis, not eczema"
            encounter.save()

        updated_vector = client.retrieve(
            settings.QDRANT_COLLECTION, ids=[encounter.id], with_vectors=True
        )[0].vector
        self.assertNotEqual(original_vector, updated_vector)

    def test_delete_removes_point_from_qdrant(self):
        with self.captureOnCommitCallbacks(execute=True):
            encounter = Encounter.objects.create(
                patient=self.patient,
                clinician=self.clinician,
                specialty=Encounter.Specialty.ONCOLOGY,
                chief_complaint="Fatigue and weight loss",
                notes="Night sweats",
                diagnosis="Suspected lymphoma",
                treatment="Biopsy pending",
            )
        encounter_id = encounter.id

        encounter.delete()

        client = qdrant_store.get_client()
        points = client.retrieve(settings.QDRANT_COLLECTION, ids=[encounter_id])
        self.assertEqual(points, [])

    def test_rolled_back_create_never_reaches_qdrant(self):
        """Proves the on_commit deferral is load-bearing: a Postgres write
        that rolls back must never schedule (let alone run) a Qdrant write,
        and must never produce a Qdrant point."""
        from django.db import transaction

        with self.captureOnCommitCallbacks(execute=True) as callbacks:
            with self.assertRaises(ValueError):
                with transaction.atomic():
                    encounter = Encounter.objects.create(
                        patient=self.patient,
                        clinician=self.clinician,
                        specialty=Encounter.Specialty.GENERAL_MEDICINE,
                        chief_complaint="cc",
                        notes="n",
                        diagnosis="d",
                        treatment="t",
                    )
                    encounter_id = encounter.id
                    raise ValueError("force rollback")

        self.assertEqual(callbacks, [])

        # No upsert ever ran against this test's fresh `:memory:` client, so
        # the collection itself may not exist yet - ensure it does before
        # asserting the point is absent.
        qdrant_store.ensure_collection()
        client = qdrant_store.get_client()
        points = client.retrieve(settings.QDRANT_COLLECTION, ids=[encounter_id])
        self.assertEqual(points, [])
