from rest_framework import permissions


class IsClinicianOrAdmin(permissions.BasePermission):
    """Every account in this app is a clinician or admin - this is an
    explicit, descriptive gate (defense in depth) rather than relying solely
    on IsAuthenticated, and a natural extension point if other roles are
    ever added."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and user.role in (user.Role.CLINICIAN, user.Role.ADMIN)
        )
