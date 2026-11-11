from django.apps import AppConfig


class EncountersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.encounters"
    label = "encounters"

    def ready(self):
        import apps.encounters.signals  # noqa: F401
