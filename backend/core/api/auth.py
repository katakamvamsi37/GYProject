"""Password authentication and administrator-managed access. No public OTP issuance."""

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, throttle_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from core.models import UserProfile
from core.services.audit import record
from .permissions import Administrator, role_for
from .serializers import (
    CreateUserSerializer,
    ProfileSerializer,
    UserAccessSerializer,
    PasswordSerializer,
)
from .pagination import StandardPagination


class LoginThrottle(AnonRateThrottle):
    scope = "login"


def user_payload(user):
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": role_for(user)})
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "name": user.get_full_name() or user.username,
        "phone": profile.phone,
        "avatar_url": profile.avatar_url,
        "role": role_for(user),
        "authority": dict(UserProfile.ROLE_CHOICES).get(role_for(user), "Member"),
        "is_active": user.is_active,
        "phone_verified": profile.phone_verified,
        "email_verified": profile.email_verified,
    }


@api_view(["POST"])
@permission_classes([AllowAny])
@throttle_classes([LoginThrottle])
def login(request):
    identifier = request.data.get("email", "")
    password = request.data.get("password", "")
    if not isinstance(identifier, str) or not isinstance(password, str):
        return Response({"detail": "Provide a username and password."}, status=400)
    identifier = identifier.strip()
    account = get_user_model().objects.filter(username=identifier).first()
    if not account:
        matches = list(get_user_model().objects.filter(email__iexact=identifier)[:2])
        account = matches[0] if len(matches) == 1 else None
    user = authenticate(username=account.username if account else identifier, password=password)
    if not user:
        return Response({"detail": "Invalid credentials or inactive account."}, status=401)
    refresh = RefreshToken.for_user(user)
    return Response(
        {"access": str(refresh.access_token), "refresh": str(refresh), "user": user_payload(user)}
    )


@api_view(["GET"])
def me(request):
    return Response({"user": user_payload(request.user)})


@api_view(["POST"])
def logout(request):
    try:
        token = RefreshToken(request.data.get("refresh", ""))
        if str(token["user_id"]) != str(request.user.pk):
            return Response({"detail": "Invalid session."}, status=400)
        token.blacklist()
    except TokenError:
        pass
    return Response(status=204)


@api_view(["POST"])
def change_password(request):
    serializer = PasswordSerializer(data=request.data, context={"user": request.user})
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        request.user.set_password(serializer.validated_data["new_password"])
        request.user.save(update_fields=["password"])
        record(request.user, "password_changed", request.user, after={"password_changed": True})
    return Response({"detail": "Password changed. Sign in again."})


@api_view(["POST"])
@permission_classes([AllowAny])
def otp_unavailable(request):
    return Response(
        {"detail": "OTP access is disabled. Contact your administrator for account recovery."},
        status=410,
    )


@api_view(["GET", "PATCH"])
def profile_detail(request, user_id):
    user = get_object_or_404(get_user_model(), pk=user_id)
    if request.user.pk != user.pk and role_for(request.user) != "admin":
        return Response({"detail": "You can only access your own profile."}, status=403)
    if request.method == "PATCH":
        serializer = ProfileSerializer(data=request.data, partial=True, context={"user": user})
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            before = user_payload(user)
            values = serializer.validated_data
            profile = user.profile
            if "name" in values:
                user.first_name, user.last_name = values["name"], ""
            if "email" in values and values["email"] != user.email:
                user.email = values["email"]
                profile.email_verified = False
            if "phone" in values and values["phone"] != profile.phone:
                profile.phone = values["phone"]
                profile.phone_verified = False
            if "avatar_url" in values:
                profile.avatar_url = values["avatar_url"]
            user.save()
            profile.save()
            record(request.user, "profile_updated", user, before=before, after=user_payload(user))
    return Response({"user": user_payload(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticated, Administrator])
def signup(request):
    serializer = CreateUserSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    values = serializer.validated_data
    with transaction.atomic():
        user = get_user_model().objects.create_user(
            username=values["email"],
            email=values["email"],
            first_name=values["name"],
            password=values["password"],
        )
        UserProfile.objects.create(user=user, role=values["role"])
        record(request.user, "user_created", user, after=user_payload(user))
    return Response({"user": user_payload(user)}, status=status.HTTP_201_CREATED)


@api_view(["GET"])
@permission_classes([IsAuthenticated, Administrator])
def users(request):
    queryset = get_user_model().objects.select_related("profile").order_by("id")
    search = request.query_params.get("search", "").strip()
    if search:
        queryset = queryset.filter(
            Q(username__icontains=search)
            | Q(first_name__icontains=search)
            | Q(email__icontains=search)
        )
    paginator = StandardPagination()
    return paginator.get_paginated_response(
        [user_payload(user) for user in paginator.paginate_queryset(queryset, request)]
    )


@api_view(["PATCH"])
@permission_classes([IsAuthenticated, Administrator])
def user_access(request, user_id):
    user = get_object_or_404(get_user_model(), pk=user_id)
    if user.pk == request.user.pk or user.is_staff or user.is_superuser:
        return Response(
            {"detail": "Your own access and Django staff access cannot be changed here."},
            status=400,
        )
    serializer = UserAccessSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    with transaction.atomic():
        before = user_payload(user)
        user.is_active = serializer.validated_data["is_active"]
        user.profile.role = serializer.validated_data["role"]
        user.save(update_fields=["is_active"])
        user.profile.save(update_fields=["role"])
        record(request.user, "access_updated", user, before=before, after=user_payload(user))
    return Response({"user": user_payload(user)})
