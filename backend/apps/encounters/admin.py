from django.contrib import admin

from apps.encounters.models import Encounter


@admin.register(Encounter)
class EncounterAdmin(admin.ModelAdmin):
    list_display = ["id", "patient", "clinician", "specialty", "consent_for_research", "created_at"]
    list_filter = ["specialty", "consent_for_research"]
    search_fields = ["chief_complaint", "diagnosis"]
