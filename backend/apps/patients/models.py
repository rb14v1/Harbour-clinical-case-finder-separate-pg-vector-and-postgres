from django.db import models


class Patient(models.Model):
    full_name = models.CharField(max_length=255)
    date_of_birth = models.DateField()
    mrn = models.CharField(max_length=50, unique=True, help_text="Medical record number")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["full_name"]

    def __str__(self):
        return f"{self.full_name} (MRN {self.mrn})"
