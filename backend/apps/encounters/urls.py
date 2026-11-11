from rest_framework.routers import DefaultRouter

from apps.encounters.views import EncounterViewSet

router = DefaultRouter()
router.register(r"", EncounterViewSet, basename="encounter")

urlpatterns = router.urls
