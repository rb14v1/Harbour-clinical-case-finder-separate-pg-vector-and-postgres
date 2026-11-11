from django.urls import path

from apps.accounts.views import MeView

urlpatterns = [
    path("users/me/", MeView.as_view(), name="users-me"),
]
