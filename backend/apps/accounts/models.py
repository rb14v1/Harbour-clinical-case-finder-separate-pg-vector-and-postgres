from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts.managers import UserManager


class User(AbstractUser):
    """Clinician or admin account. email is the login identifier (no
    `username` field). `specialty` is only meaningful for clinicians - it
    scopes which encounters they typically author and is shown alongside
    their name, but the similarity-search specialty filter itself is driven
    by the `Encounter.specialty` field, not the user's."""

    class Role(models.TextChoices):
        CLINICIAN = "clinician", "Clinician"
        ADMIN = "admin", "Admin"

    username = None
    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CLINICIAN)
    specialty = models.CharField(max_length=50, blank=True, null=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    objects = UserManager()

    def __str__(self):
        return self.email

    @property
    def is_admin(self) -> bool:
        return self.role == self.Role.ADMIN

    @property
    def is_clinician(self) -> bool:
        return self.role == self.Role.CLINICIAN
