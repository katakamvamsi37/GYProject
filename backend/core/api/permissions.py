"""Single role matrix used by every operational endpoint."""

from rest_framework.permissions import BasePermission, SAFE_METHODS


def role_for(user):
    if user.is_superuser or user.is_staff:
        return "admin"
    profile = getattr(user, "profile", None)
    return profile.role if profile else "member"


FINANCE_ROLES = {"admin", "treasurer"}
MANAGEMENT_ROLES = {"admin", "treasurer", "secretary", "coordinator"}


class ManagementRead(BasePermission):
    def has_permission(self, request, view):
        role = role_for(request.user)
        if request.method in SAFE_METHODS:
            return role in MANAGEMENT_ROLES
        return role in getattr(view, "write_roles", FINANCE_ROLES)


class Administrator(BasePermission):
    def has_permission(self, request, view):
        return role_for(request.user) == "admin"
