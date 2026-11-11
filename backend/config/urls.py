from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    # Entra ID OIDC: /oidc/authenticate/, /oidc/callback/, /oidc/logout/
    path("oidc/", include("mozilla_django_oidc.urls")),
    path("api/auth/", include("apps.accounts.auth_urls")),
    path("api/", include("apps.accounts.urls")),
    path("api/patients/", include("apps.patients.urls")),
    path("api/encounters/", include("apps.encounters.urls")),
]
