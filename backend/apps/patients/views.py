from rest_framework import permissions, viewsets

from apps.patients.models import Patient
from apps.patients.serializers import PatientSerializer


class PatientViewSet(viewsets.ModelViewSet):
    """Any authenticated clinician or admin can view/manage patient records -
    patients themselves aren't scoped per-clinician (a patient may see
    multiple clinicians), unlike encounters below."""

    queryset = Patient.objects.all()
    serializer_class = PatientSerializer
    permission_classes = [permissions.IsAuthenticated]
