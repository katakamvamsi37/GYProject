"""Password authentication and administrator-managed access. No public OTP issuance."""

from uuid import uuid4
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse
from rest_framework import status
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
    throttle_classes,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken, TokenError
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from core.models import UserProfile, ProfileImage
from core.services.audit import record
from core.services.phone import normalize_phone
from .permissions import Administrator, role_for
from .serializers import (
    CreateUserSerializer,
    ProfileSerializer,
    UserAccessSerializer,
    PasswordSerializer,
    AdminPasswordSerializer,
)
from .pagination import StandardPagination


class LoginThrottle(AnonRateThrottle):
    scope = "login"


def user_payload(user, request=None):
    profile, _ = UserProfile.objects.get_or_create(user=user, defaults={"role": role_for(user)})
    avatar_url = profile.avatar_url
    if request and avatar_url.startswith("/"):
        avatar_url = request.build_absolute_uri(avatar_url)
    return {
        "id": user.id,
        "username": user.username,
        "email": user.email,
        "name": user.get_full_name() or user.username,
        "phone": profile.phone,
        "avatar_url": avatar_url,
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
    identifiers = [
        request.data.get(key)
        for key in ("identifier", "email", "phone", "username")
        if key in request.data and request.data.get(key) != ""
    ]
    password = request.data.get("password", "")
    if (
        not identifiers
        or any(not isinstance(value, str) for value in identifiers)
        or not isinstance(password, str)
        or not password
    ):
        return Response({"detail": "Provide an email or mobile number and password."}, status=400)
    identifiers = {value.strip() for value in identifiers}
    if len(identifiers) != 1 or not next(iter(identifiers)):
        return Response({"detail": "Provide one email or mobile number and password."}, status=400)
    identifier = identifiers.pop()
    # Email-shaped usernames are historical signup identifiers; only the current
    # email may be used after a profile email change. Legacy plain usernames work.
    lookup = Q(email__iexact=identifier) if "@" in identifier else Q(username=identifier)
    try:
        phone = normalize_phone(identifier)
    except ValueError:
        phone = ""
    if phone:
        lookup |= Q(profile__phone=phone)
    matches = list(get_user_model().objects.filter(lookup)[:2])
    user = None
    if len(matches) == 1:
        user = authenticate(username=matches[0].username, password=password)
    else:
        # Match password hashing cost for missing or ambiguous identifiers.
        get_user_model()().set_password(password)
    if not user:
        return Response({"detail": "Invalid credentials or inactive account."}, status=401)
    refresh = RefreshToken.for_user(user)
    return Response(
        {
            "access": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user_payload(user, request),
        }
    )


@api_view(["GET"])
def me(request):
    return Response({"user": user_payload(request.user, request)})


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


def save_password(actor, user, password, action):
    with transaction.atomic():
        user.set_password(password)
        user.save(update_fields=["password"])
        for token in OutstandingToken.objects.filter(user=user):
            BlacklistedToken.objects.get_or_create(token=token)
        record(actor, action, user, after={"password_changed": True})


@api_view(["POST"])
def change_password(request):
    serializer = PasswordSerializer(data=request.data, context={"user": request.user})
    serializer.is_valid(raise_exception=True)
    save_password(
        request.user, request.user, serializer.validated_data["new_password"], "password_changed"
    )
    return Response({"detail": "Password changed. Sign in again."})


@api_view(["POST"])
@permission_classes([IsAuthenticated, Administrator])
def admin_password(request, user_id):
    user = get_object_or_404(get_user_model(), pk=user_id)
    serializer = AdminPasswordSerializer(data=request.data, context={"user": user})
    serializer.is_valid(raise_exception=True)
    save_password(request.user, user, serializer.validated_data["new_password"], "password_reset")
    return Response({"detail": "Password updated. This user must sign in again."})


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
                current_urls = {profile.avatar_url}
                if profile.avatar_url.startswith("/"):
                    current_urls.add(request.build_absolute_uri(profile.avatar_url))
                if values["avatar_url"] not in current_urls:
                    profile.avatar_url = values["avatar_url"]
                    ProfileImage.objects.filter(user=user).delete()
            if "avatar" in values:
                image, _ = ProfileImage.objects.update_or_create(
                    user=user, defaults={"image": values["avatar"], "version": uuid4()}
                )
                profile.avatar_url = reverse(
                    "profile-avatar", kwargs={"user_id": user.pk, "version": image.version}
                )
            user.save()
            profile.save()
            record(request.user, "profile_updated", user, before=before, after=user_payload(user))
    return Response({"user": user_payload(user, request)})


@api_view(["GET"])
@authentication_classes([])
@permission_classes([AllowAny])
@throttle_classes([])
def profile_avatar(request, user_id, version):
    image = get_object_or_404(ProfileImage, user_id=user_id, version=version, user__is_active=True)
    response = HttpResponse(bytes(image.image), content_type="image/webp")
    response["Cache-Control"] = "no-cache"
    response["X-Content-Type-Options"] = "nosniff"
    return response


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
        UserProfile.objects.create(user=user, role=values["role"], phone=values["phone"])
        record(request.user, "user_created", user, after=user_payload(user))
    return Response({"user": user_payload(user, request)}, status=status.HTTP_201_CREATED)


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
            | Q(profile__phone__icontains=search)
        )
    paginator = StandardPagination()
    return paginator.get_paginated_response(
        [user_payload(user, request) for user in paginator.paginate_queryset(queryset, request)]
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
    return Response({"user": user_payload(user, request)})
