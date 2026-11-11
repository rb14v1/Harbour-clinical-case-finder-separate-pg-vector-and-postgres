from rest_framework import serializers

from apps.encounters.models import Encounter


class EncounterSerializer(serializers.ModelSerializer):
    clinician_email = serializers.EmailField(source="clinician.email", read_only=True)
    patient_name = serializers.CharField(source="patient.full_name", read_only=True)

    class Meta:
        model = Encounter
        fields = [
            "id",
            "patient",
            "patient_name",
            "clinician",
            "clinician_email",
            "specialty",
            "chief_complaint",
            "notes",
            "diagnosis",
            "treatment",
            "consent_for_research",
            "created_at",
        ]
        # clinician is always the requesting user - set in
        # EncounterViewSet.perform_create, never client-supplied, so an
        # encounter can't be created/attributed to a different clinician.
        read_only_fields = ["id", "clinician", "created_at"]


class SimilarEncounterResultSerializer(serializers.Serializer):
    encounter_id = serializers.IntegerField()
    score = serializers.FloatField()
    specialty = serializers.CharField()
    chief_complaint = serializers.CharField()
    diagnosis = serializers.CharField()
    treatment = serializers.CharField()
    clinician_id = serializers.IntegerField()
