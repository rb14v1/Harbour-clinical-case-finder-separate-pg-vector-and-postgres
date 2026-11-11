from rest_framework import status
from rest_framework.test import APITestCase

from apps.common.test_utils import auth_client, create_user
from apps.patients.models import Patient


class PatientCrudTests(APITestCase):
    def setUp(self):
        self.clinician = create_user(email="clin@example.com")
        self.client = auth_client(self.clinician)

    def test_create_and_list_patient(self):
        resp = self.client.post("/api/patients/", {
            "full_name": "Jane Doe",
            "date_of_birth": "1990-01-01",
            "mrn": "MRN-1",
        })
        self.assertEqual(resp.status_code, status.HTTP_201_CREATED, resp.data)

        list_resp = self.client.get("/api/patients/")
        self.assertEqual(list_resp.status_code, status.HTTP_200_OK)
        mrns = [p["mrn"] for p in list_resp.data["results"]]
        self.assertIn("MRN-1", mrns)

    def test_mrn_must_be_unique(self):
        Patient.objects.create(full_name="A", date_of_birth="1980-01-01", mrn="MRN-DUP")
        resp = self.client.post("/api/patients/", {
            "full_name": "B",
            "date_of_birth": "1981-01-01",
            "mrn": "MRN-DUP",
        })
        self.assertEqual(resp.status_code, status.HTTP_400_BAD_REQUEST)

    def test_update_patient(self):
        patient = Patient.objects.create(full_name="Old Name", date_of_birth="1980-01-01", mrn="MRN-2")
        resp = self.client.patch(f"/api/patients/{patient.id}/", {"full_name": "New Name"})
        self.assertEqual(resp.status_code, status.HTTP_200_OK)
        patient.refresh_from_db()
        self.assertEqual(patient.full_name, "New Name")

    def test_delete_patient(self):
        patient = Patient.objects.create(full_name="To Delete", date_of_birth="1980-01-01", mrn="MRN-3")
        resp = self.client.delete(f"/api/patients/{patient.id}/")
        self.assertEqual(resp.status_code, status.HTTP_204_NO_CONTENT)
        self.assertFalse(Patient.objects.filter(id=patient.id).exists())

    def test_unauthenticated_rejected(self):
        from rest_framework.test import APIClient
        resp = APIClient().get("/api/patients/")
        self.assertEqual(resp.status_code, status.HTTP_401_UNAUTHORIZED)
