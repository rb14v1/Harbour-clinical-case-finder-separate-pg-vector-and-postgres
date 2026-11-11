from django.test import TestCase

from apps.accounts.models import User
from apps.encounters.models import Encounter
from apps.patients.models import Patient


class SeedDataMigrationTests(TestCase):
    """Verifies the 0002_seed_demo_data data migration
    (apps/encounters/migrations) ran as part of building the test
    database."""

    def test_demo_clinician_and_admin_exist(self):
        clinician = User.objects.filter(email="clinician@example.com").first()
        self.assertIsNotNone(clinician)
        self.assertEqual(clinician.role, User.Role.CLINICIAN)
        self.assertEqual(clinician.specialty, "cardiology")

        admin = User.objects.filter(email="admin@example.com").first()
        self.assertIsNotNone(admin)
        self.assertEqual(admin.role, User.Role.ADMIN)

    def test_seeded_patient_count(self):
        self.assertGreaterEqual(Patient.objects.count(), 3)

    def test_seeded_encounter_count_and_specialty_spread(self):
        encounters = Encounter.objects.all()
        self.assertGreaterEqual(encounters.count(), 15)
        self.assertLessEqual(encounters.count(), 18)

        specialties = set(encounters.values_list("specialty", flat=True))
        self.assertGreaterEqual(len(specialties), 3)

    def test_seeded_encounters_mix_consent_values(self):
        encounters = Encounter.objects.all()
        consented = encounters.filter(consent_for_research=True)
        not_consented = encounters.filter(consent_for_research=False)
        self.assertGreater(consented.count(), 0)
        self.assertGreater(not_consented.count(), 0)
        self.assertGreater(consented.count(), not_consented.count())

    def test_seeded_encounters_have_non_empty_clinical_text(self):
        for encounter in Encounter.objects.all():
            self.assertTrue(encounter.chief_complaint.strip())
            self.assertTrue(encounter.notes.strip())
            self.assertTrue(encounter.diagnosis.strip())
            self.assertTrue(encounter.treatment.strip())
