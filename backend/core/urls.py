from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .api import auth
from .api.dashboard import dashboard
from .api.exports import export_records
from .api.records import MemberViewSet, PlanViewSet, ExpenseViewSet, PaymentViewSet, AuditViewSet

router = DefaultRouter()
router.register("members", MemberViewSet)
router.register("plans", PlanViewSet)
router.register("expenses", ExpenseViewSet)
router.register("payments", PaymentViewSet)
router.register("audit", AuditViewSet)
urlpatterns = [
    path("dashboard/", dashboard),
    path("login/", auth.login),
    path("me/", auth.me),
    path("logout/", auth.logout),
    path("auth/password/change/", auth.change_password),
    path("signup/", auth.signup),
    path("users/", auth.users),
    path("users/<int:user_id>/access/", auth.user_access),
    path("profiles/<int:user_id>/", auth.profile_detail),
    path("auth/otp/request/", auth.otp_unavailable),
    path("auth/otp/verify/", auth.otp_unavailable),
    path("auth/password/reset/", auth.otp_unavailable),
    path("export/<str:resource>/", export_records),
    path("", include(router.urls)),
]
