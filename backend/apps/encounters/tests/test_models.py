from django.test import TestCase

from apps.common.test_utils import create_user
from apps.encounters.models import Encounter
from apps.patients.models import Patient


class EncounterModelTests(TestCase):
    def setUp(self):
        self.clinician = create_user(email="doc@example.com")
        self.patient = Patient.objects.create(full_name="Pat One", date_of_birth="1990-01-01", mrn="MODEL-1")

    def test_embedding_text_combines_chief_complaint_notes_and_diagnosis(self):
        encounter = Encounter.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            specialty=Encounter.Specialty.CARDIOLOGY,
            chief_complaint="Chest pain",
            notes="Some notes",
            diagnosis="Angina",
            treatment="Aspirin",
        )
        self.assertEqual(encounter.embedding_text, "Chest pain Some notes Angina")

    def test_embedding_text_excludes_treatment(self):
        # Treatment is deliberately NOT part of the embedding text - it's the
        # historical outcome similarity search surfaces, not part of what
        # describes the case itself.
        encounter = Encounter.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            specialty=Encounter.Specialty.CARDIOLOGY,
            chief_complaint="Chest pain",
            notes="Some notes",
            diagnosis="Angina",
            treatment="A very distinctive unlikely treatment string",
        )
        self.assertNotIn("distinctive unlikely treatment", encounter.embedding_text)

    def test_str_representation_includes_patient_name(self):
        encounter = Encounter.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            specialty=Encounter.Specialty.CARDIOLOGY,
            chief_complaint="cc",
            notes="n",
            diagnosis="d",
            treatment="t",
        )
        self.assertIn(self.patient.full_name, str(encounter))

    def test_consent_for_research_defaults_false(self):
        encounter = Encounter.objects.create(
            patient=self.patient,
            clinician=self.clinician,
            specialty=Encounter.Specialty.CARDIOLOGY,
            chief_complaint="cc",
            notes="n",
            diagnosis="d",
            treatment="t",
        )
        self.assertFalse(encounter.consent_for_research)
