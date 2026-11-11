from rest_framework import status
from rest_framework.test import APITestCase

from apps.common import qdrant_store
from apps.common.test_utils import auth_client, create_user
from apps.encounters.models import Encounter
from apps.patients.models import Patient


def encounter_payload(patient_id, **overrides):
    data = dict(
        patient=patient_id,
        specialty="cardiology",
        chief_complaint="Chest tightness on exertion",
        notes="Risk factors include hypertension",
        diagnosis="Stable angina",
        treatment="Nitroglycerin PRN",
        consent_for_research=True,
    )
    data.update(overrides)
    return data


class EncounterCrudTests(APITestCase):
    def setUp(self):
        qdrant_store.reset_client()
        self.clinician = create_user(email="c1@example.com")
        self.client = auth_client(self.clinician)
        self.patient = Patient.objects.create(full_name="Pat One", date_of_birth="1990-01-01", mrn="CRUD-1")

    def test_create_and_list_encounter(self):
        resp = self.client.post("/api/encounters/", encounter_payload(self.patient.id))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["clinician"], self.clinician.id)
        self.assertEqual(resp.data["patient_name"], self.patient.full_name)

        list_resp = self.client.get("/api/encounters/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        ids = [e["id"] for e in list_resp.data["results"]]
        self.assertIn(resp.data["id"], ids)

    def test_clinician_field_is_always_the_requesting_user(self):
        other = create_user(email="other@example.com")
        resp = self.client.post("/api/encounters/", encounter_payload(self.patient.id, clinician=other.id))
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)
        self.assertEqual(resp.data["clinician"], self.clinician.id)

    def test_update_encounter(self):
        created = self.client.post("/api/encounters/", encounter_payload(self.patient.id))
        resp = self.client.patch(f"/api/encounters/{created.data['id']}/", {"diagnosis": "Unstable angina"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertEqual(resp.data["diagnosis"], "Unstable angina")

    def test_delete_encounter(self):
        created = self.client.post("/api/encounters/", encounter_payload(self.patient.id))
        resp = self.client.delete(f"/api/encounters/{created.data['id']}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Encounter.objects.filter(id=created.data["id"]).exists())

    def test_filter_by_specialty(self):
        self.client.post("/api/encounters/", encounter_payload(self.patient.id, specialty="cardiology"))
        self.client.post("/api/encounters/", encounter_payload(self.patient.id, specialty="dermatology"))

        resp = self.client.get("/api/encounters/", {"specialty": "dermatology"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        specialties = {e["specialty"] for e in resp.data["results"]}
        self.assertEqual(specialties, {"dermatology"})

    def test_filter_by_consent_for_research(self):
        self.client.post("/api/encounters/", encounter_payload(self.patient.id, consent_for_research=True))
        self.client.post("/api/encounters/", encounter_payload(self.patient.id, consent_for_research=False))

        resp = self.client.get("/api/encounters/", {"consent_for_research": "False"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        self.assertTrue(all(e["consent_for_research"] is False for e in resp.data["results"]))

    def test_unauthenticated_request_rejected(self):
        from rest_framework.test import APIClient
        resp = APIClient().get("/api/encounters/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)


class EncounterOwnershipTests(APITestCase):
    """Guards the core permission rule: a clinician only ever sees/edits
    their own encounters directly; admins see everything."""

    def setUp(self):
        qdrant_store.reset_client()
        self.clinician_a = create_user(email="a@example.com")
        self.clinician_b = create_user(email="b@example.com")
        self.admin = create_user(email="admin-owner-test@example.com", role="admin")
        self.client_a = auth_client(self.clinician_a)
        self.client_b = auth_client(self.clinician_b)
        self.client_admin = auth_client(self.admin)
        self.patient = Patient.objects.create(full_name="Pat Two", date_of_birth="1985-05-05", mrn="OWN-1")

        created = self.client_a.post(
            "/api/encounters/",
            encounter_payload(self.patient.id, consent_for_research=False),
        )
        self.encounter_a_id = created.data["id"]

    def test_clinician_b_list_excludes_clinician_a_encounter(self):
        resp = self.client_b.get("/api/encounters/")
        ids = [e["id"] for e in resp.data["results"]]
        self.assertNotIn(self.encounter_a_id, ids)

    def test_clinician_b_cannot_retrieve_clinician_a_encounter_directly(self):
        resp = self.client_b.get(f"/api/encounters/{self.encounter_a_id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_clinician_b_cannot_update_clinician_a_encounter(self):
        resp = self.client_b.patch(f"/api/encounters/{self.encounter_a_id}/", {"diagnosis": "tampered"})
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)

    def test_clinician_b_cannot_delete_clinician_a_encounter(self):
        resp = self.client_b.delete(f"/api/encounters/{self.encounter_a_id}/")
        self.assertEqual(resp.status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(Encounter.objects.filter(id=self.encounter_a_id).exists())

    def test_admin_can_list_and_retrieve_all_encounters(self):
        list_resp = self.client_admin.get("/api/encounters/")
        ids = [e["id"] for e in list_resp.data["results"]]
        self.assertIn(self.encounter_a_id, ids)

        retrieve_resp = self.client_admin.get(f"/api/encounters/{self.encounter_a_id}/")
        self.assertEqual(retrieve_resp.status_code, status.HTTP_200_OK)
