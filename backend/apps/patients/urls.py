from rest_framework.routers import DefaultRouter

from apps.patients.views import PatientViewSet

router = DefaultRouter()
router.register(r"", PatientViewSet, basename="patient")

urlpatterns = router.urls
