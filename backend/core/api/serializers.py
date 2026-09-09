"""Input validation and explicit API response shapes."""

from decimal import Decimal
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Sum
from rest_framework import serializers
from core.models import Member, Plan, Expense, Payment, UserProfile, AuditEvent


class MemberSerializer(serializers.ModelSerializer):
    class Meta:
        model = Member
        fields = "__all__"
        read_only_fields = ["id", "joined_on"]


class PlanSerializer(serializers.ModelSerializer):
    spent = serializers.SerializerMethodField()
    status = serializers.ChoiceField(choices=["Planning", "In progress", "Completed", "Cancelled"])
    budget = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    target_date = serializers.DateField(required=True, allow_null=False)

    def get_spent(self, instance):
        value = getattr(instance, "actual_spent", None)
        if value is None:
            value = (
                instance.expenses.filter(status="approved").aggregate(total=Sum("amount"))["total"]
                or 0
            )
        return str(value)

    class Meta:
        model = Plan
        fields = ["id", "title", "category", "budget", "spent", "status", "target_date"]


class ExpenseSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    plan_title = serializers.CharField(source="plan.title", read_only=True, default="")
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default="Legacy entry"
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.username", read_only=True, default=""
    )

    def validate(self, attrs):
        plan = attrs.get("plan", getattr(self.instance, "plan", None))
        spent_on = attrs.get("spent_on", getattr(self.instance, "spent_on", None))
        if plan and (not plan.target_date or plan.target_date.year != spent_on.year):
            raise serializers.ValidationError(
                {"plan": "Choose a budget from the same festival year."}
            )
        return attrs

    class Meta:
        model = Expense
        fields = "__all__"
        read_only_fields = [
            "id",
            "status",
            "created_by",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "created_at",
            "submission_key",
            "submission_hash",
        ]


class PaymentSerializer(serializers.ModelSerializer):
    amount = serializers.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal("0.01"))
    method = serializers.ChoiceField(choices=["Cash", "UPI", "Bank transfer", "Cheque"])
    paid_on = serializers.DateTimeField(required=True)
    created_by_name = serializers.CharField(
        source="created_by.username", read_only=True, default="Legacy entry"
    )
    reviewed_by_name = serializers.CharField(
        source="reviewed_by.username", read_only=True, default=""
    )

    def validate(self, attrs):
        if (
            attrs.get("method", "UPI") != "Cash"
            and not attrs.get("transaction_reference", "").strip()
        ):
            raise serializers.ValidationError(
                {"transaction_reference": "A bank / UPI / cheque reference is required."}
            )
        return attrs

    class Meta:
        model = Payment
        fields = "__all__"
        read_only_fields = [
            "id",
            "reference",
            "status",
            "created_by",
            "reviewed_by",
            "reviewed_at",
            "review_note",
            "submission_key",
            "submission_hash",
        ]


class ReviewSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["approve", "reject", "void"])
    note = serializers.CharField(max_length=500, allow_blank=False)


class ProfileSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=30, allow_blank=True)
    avatar_url = serializers.URLField(allow_blank=True)

    def validate_email(self, value):
        value = value.strip().lower()
        if (
            get_user_model()
            .objects.filter(email__iexact=value)
            .exclude(pk=self.context["user"].pk)
            .exists()
        ):
            raise serializers.ValidationError("This email is already in use.")
        return value


class CreateUserSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=150)
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES, default="member")

    def validate(self, attrs):
        email = attrs["email"].lower()
        User = get_user_model()
        if (
            User.objects.filter(email__iexact=email).exists()
            or User.objects.filter(username__iexact=email).exists()
        ):
            raise serializers.ValidationError({"email": "An account already exists."})
        attrs["email"] = email
        try:
            validate_password(
                attrs["password"], User(username=email, email=email, first_name=attrs["name"])
            )
        except DjangoValidationError as error:
            raise serializers.ValidationError({"password": error.messages})
        return attrs


class UserAccessSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=UserProfile.ROLE_CHOICES)
    is_active = serializers.BooleanField()


class PasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField()
    new_password = serializers.CharField()

    def validate(self, attrs):
        user = self.context["user"]
        if not user.check_password(attrs["current_password"]):
            raise serializers.ValidationError(
                {"current_password": "Current password is incorrect."}
            )
        try:
            validate_password(attrs["new_password"], user)
        except DjangoValidationError as error:
            raise serializers.ValidationError({"new_password": error.messages})
        return attrs


class AuditSerializer(serializers.ModelSerializer):
    class Meta:
        model = AuditEvent
        fields = "__all__"
