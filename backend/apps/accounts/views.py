from django.conf import settings
from django.contrib.auth import logout as django_logout
from mozilla_django_oidc.auth import OIDCAuthenticationBackend
from rest_framework import generics, permissions, status
from rest_framework.authentication import SessionAuthentication
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.accounts.models import User
from apps.accounts.serializers import (
    EmailTokenObtainPairSerializer,
    RegisterSerializer,
    UserSerializer,
)


class EntraOIDCAuthenticationBackend(OIDCAuthenticationBackend):
    """Maps a verified Microsoft Entra ID identity onto the local User
    (email is the login identifier; there is no username field)."""

    def filter_users_by_claims(self, claims):
        email = claims.get("email")
        if not email:
            return self.UserModel.objects.none()
        return self.UserModel.objects.filter(email__iexact=email)

    def create_user(self, claims):
        # No password: the account can only sign in through the IdP.
        return self.UserModel.objects.create_user(
            email=claims.get("email"),
            full_name=claims.get("name", ""),
        )

    def update_user(self, user, claims):
        return user


def _set_refresh_cookie(response, refresh):
    """Refresh tokens travel only in an HttpOnly cookie, never in JS-readable
    storage."""
    response.set_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        refresh,
        max_age=int(settings.SIMPLE_JWT["REFRESH_TOKEN_LIFETIME"].total_seconds()),
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        secure=settings.AUTH_REFRESH_COOKIE_SECURE,
        httponly=True,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )


def _delete_refresh_cookie(response):
    response.delete_cookie(
        settings.AUTH_REFRESH_COOKIE_NAME,
        path=settings.AUTH_REFRESH_COOKIE_PATH,
        samesite=settings.AUTH_REFRESH_COOKIE_SAMESITE,
    )


class RegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class EmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = EmailTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)
        if response.status_code == status.HTTP_200_OK and "refresh" in response.data:
            _set_refresh_cookie(response, response.data["refresh"])
        return response


class ThrottledTokenRefreshView(TokenRefreshView):
    """Reads the refresh token from the HttpOnly cookie (falling back to the
    request body for API clients) and rotates the cookie."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if not data.get("refresh"):
            cookie = request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
            if cookie:
                data["refresh"] = cookie
        serializer = self.get_serializer(data=data)
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            raise InvalidToken(e.args[0])
        payload = dict(serializer.validated_data)
        new_refresh = payload.pop("refresh", None)
        response = Response(payload, status=status.HTTP_200_OK)
        if new_refresh:
            _set_refresh_cookie(response, new_refresh)
        return response


class OIDCSessionTokenView(APIView):
    """Exchanges the server-side session created by the Entra ID OIDC
    callback (/oidc/callback/) for an in-memory access token and an HttpOnly
    refresh cookie."""

    authentication_classes = [SessionAuthentication]
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def get(self, request):
        refresh = EmailTokenObtainPairSerializer.get_token(request.user)
        response = Response({"access": str(refresh.access_token)})
        _set_refresh_cookie(response, str(refresh))
        return response


class LogoutView(APIView):
    """Blacklists the supplied refresh token so it can no longer be used to
    mint new access tokens (requires rest_framework_simplejwt.token_blacklist,
    enabled in INSTALLED_APPS)."""

    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"

    def post(self, request):
        refresh = request.data.get("refresh") or request.COOKIES.get(settings.AUTH_REFRESH_COOKIE_NAME)
        # Also end the server-side OIDC session so it can't mint new tokens.
        django_logout(request._request)
        if not refresh:
            response = Response({"detail": "refresh is required."}, status=status.HTTP_400_BAD_REQUEST)
            _delete_refresh_cookie(response)
            return response
        try:
            token = RefreshToken(refresh)
            token.blacklist()
        except TokenError:
            response = Response({"detail": "Invalid or already-blacklisted token."}, status=status.HTTP_400_BAD_REQUEST)
            _delete_refresh_cookie(response)
            return response
        response = Response(status=status.HTTP_205_RESET_CONTENT)
        _delete_refresh_cookie(response)
        return response


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)
