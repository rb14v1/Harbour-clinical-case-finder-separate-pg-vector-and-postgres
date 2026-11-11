from django.contrib import admin

from apps.patients.models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ["id", "full_name", "mrn", "date_of_birth", "created_at"]
    search_fields = ["full_name", "mrn"]
