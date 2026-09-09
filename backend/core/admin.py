"""Operational records are read-only here so writes cannot bypass audit services."""

from django.contrib import admin
from .models import Member, Plan, Expense, Payment, UserProfile, OTPChallenge, AuditEvent


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_superuser


for model in (Member, Plan, Expense, Payment, UserProfile, OTPChallenge, AuditEvent):
    admin.site.register(model, ReadOnlyAdmin)
