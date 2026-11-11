from django.conf import settings
from django.db import models

from apps.patients.models import Patient


class Encounter(models.Model):
    """A single clinical encounter write-up. Embeddings are NOT stored on
    this model/Postgres at all - they live exclusively in Qdrant (see
    apps/common/qdrant_store.py and apps/encounters/signals.py), keyed by
    this row's integer primary key. There is no foreign-key/transactional
    link between the two stores; see the README for the sync strategy and
    its failure mode."""

    class Specialty(models.TextChoices):
        CARDIOLOGY = "cardiology", "Cardiology"
        PEDIATRICS = "pediatrics", "Pediatrics"
        ONCOLOGY = "oncology", "Oncology"
        GENERAL_MEDICINE = "general_medicine", "General Medicine"
        DERMATOLOGY = "dermatology", "Dermatology"

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="encounters")
    clinician = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="encounters")
    specialty = models.CharField(max_length=30, choices=Specialty.choices)
    chief_complaint = models.TextField()
    notes = models.TextField(help_text="The clinician's free-text write-up.")
    diagnosis = models.TextField()
    treatment = models.TextField()
    consent_for_research = models.BooleanField(
        default=False,
        help_text=(
            "Only encounters with consent_for_research=True are eligible to "
            "surface in OTHER clinicians' similarity searches."
        ),
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_specialty_display()} encounter for {self.patient.full_name}"

    @property
    def embedding_text(self) -> str:
        return f"{self.chief_complaint} {self.notes} {self.diagnosis}"
