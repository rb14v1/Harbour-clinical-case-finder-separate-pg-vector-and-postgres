from django.urls import path

from apps.accounts.views import (
    EmailTokenObtainPairView,
    LogoutView,
    MeView,
    OIDCSessionTokenView,
    RegisterView,
    ThrottledTokenRefreshView,
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="auth-register"),
    path("login/", EmailTokenObtainPairView.as_view(), name="auth-login"),
    path("refresh/", ThrottledTokenRefreshView.as_view(), name="auth-refresh"),
    path("logout/", LogoutView.as_view(), name="auth-logout"),
    path("me/", MeView.as_view(), name="auth-me"),
    path("oidc/token/", OIDCSessionTokenView.as_view(), name="auth-oidc-token"),
]
