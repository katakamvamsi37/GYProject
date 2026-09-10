"""Paginated records and auditable, two-person financial review."""

from uuid import uuid4, UUID
import hashlib
import json
from django.db import transaction, IntegrityError
from django.db.models import Sum, Q
from django.utils import timezone
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from core.models import Member, Plan, Expense, Payment, AuditEvent
from core.services.audit import record, snapshot
from .permissions import ManagementRead, MANAGEMENT_ROLES, FINANCE_ROLES, role_for
from .serializers import (
    MemberSerializer,
    PlanSerializer,
    ExpenseSerializer,
    PaymentSerializer,
    ReviewSerializer,
    AuditSerializer,
)
from .filters import filter_records


class AuditedRecords(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [ManagementRead]
    write_roles = FINANCE_ROLES

    def perform_create(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            record(self.request.user, "created", instance)


class MemberViewSet(mixins.UpdateModelMixin, AuditedRecords):
    queryset = Member.objects.order_by("name", "id")
    serializer_class = MemberSerializer
    write_roles = {"admin", "secretary"}

    def get_queryset(self):
        qs = self.queryset
        search = self.request.query_params.get("search", "").strip()
        if search:
            qs = qs.filter(
                Q(name__icontains=search)
                | Q(email__icontains=search)
                | Q(position__icontains=search)
            )
        return qs

    def perform_update(self, serializer):
        with transaction.atomic():
            before = snapshot(serializer.instance)
            instance = serializer.save()
            record(self.request.user, "updated", instance, before=before)


class PlanViewSet(mixins.UpdateModelMixin, AuditedRecords):
    queryset = Plan.objects.order_by("target_date", "id")
    serializer_class = PlanSerializer

    def get_queryset(self):
        qs = filter_records(
            self.queryset, self.request.query_params, "target_date", ["title", "category"]
        )
        return qs.annotate(
            actual_spent=Sum("expenses__amount", filter=Q(expenses__status="approved"))
        )

    def perform_update(self, serializer):
        with transaction.atomic():
            before = snapshot(serializer.instance)
            old_date = serializer.instance.target_date
            new_date = serializer.validated_data.get("target_date", old_date)
            if (
                old_date
                and new_date.year != old_date.year
                and serializer.instance.expenses.exists()
            ):
                raise ValidationError(
                    {"target_date": "A budget with expenses cannot move to another festival year."}
                )
            instance = serializer.save()
            record(self.request.user, "budget_updated", instance, before=before)


class FinancialRecords(AuditedRecords):
    write_roles = MANAGEMENT_ROLES

    def create(self, request, *args, **kwargs):
        key = request.headers.get("Idempotency-Key")
        self.submission = {}
        model = self.serializer_class.Meta.model
        if key:
            try:
                key = UUID(key)
            except ValueError:
                raise ValidationError({"detail": "Invalid submission identifier."})
            digest = hashlib.sha256(json.dumps(request.data, sort_keys=True).encode()).hexdigest()
            self.submission = {"submission_key": key, "submission_hash": digest}
            previous = model.objects.filter(submission_key=key).first()
            if previous:
                return self.replay(previous, digest)
        try:
            return super().create(request, *args, **kwargs)
        except IntegrityError:
            if key:
                previous = model.objects.filter(submission_key=key).first()
                if previous:
                    return self.replay(previous, digest)
            raise ValidationError(
                {
                    "detail": "This transaction reference is already recorded, or the entry violates a financial constraint."
                }
            )

    def replay(self, instance, digest):
        if instance.created_by_id != self.request.user.pk or instance.submission_hash != digest:
            raise ValidationError(
                {
                    "detail": "This submission was already saved with different details. Refresh the ledger before starting a new entry."
                }
            )
        return Response(self.get_serializer(instance).data)

    def perform_create(self, serializer):
        with transaction.atomic():
            extra = {"created_by": self.request.user, **getattr(self, "submission", {})}
            if serializer.Meta.model is Payment:
                extra["reference"] = "GY-" + uuid4().hex[:16].upper()
            instance = serializer.save(**extra)
            record(self.request.user, "submitted", instance)

    @action(detail=True, methods=["post"])
    def review(self, request, pk=None):
        if role_for(request.user) not in FINANCE_ROLES:
            raise PermissionDenied(
                "Only administrators and treasurers can review financial entries."
            )
        serializer = ReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            # Lock only the financial record: PostgreSQL cannot lock the nullable
            # outer joins used to display creator, reviewer, and budget details.
            instance = (
                self.get_queryset()
                .select_related(None)
                .select_for_update()
                .get(pk=self.get_object().pk)
            )
            if instance.created_by_id == request.user.pk:
                raise ValidationError(
                    {"detail": "A different administrator or treasurer must review your entry."}
                )
            action_name, note = (
                serializer.validated_data["action"],
                serializer.validated_data["note"],
            )
            if action_name == "approve" and instance.amount <= 0:
                raise ValidationError(
                    {
                        "detail": "An invalid legacy amount cannot be approved. Reject it and submit a corrected entry."
                    }
                )
            final_status = "approved" if isinstance(instance, Expense) else "confirmed"
            transitions = {"approve": ("pending", final_status), "reject": ("pending", "rejected")}
            if action_name == "void":
                if instance.status not in (final_status, "Dummy verified"):
                    raise ValidationError(
                        {"detail": "Only a posted or legacy dummy record can be voided."}
                    )
                next_status = "void"
            else:
                expected, next_status = transitions[action_name]
                if instance.status != expected:
                    raise ValidationError({"detail": "This entry has already been reviewed."})
            before = snapshot(instance)
            changed = (
                type(instance)
                .objects.filter(pk=instance.pk, status=instance.status)
                .update(
                    status=next_status,
                    reviewed_by=request.user,
                    reviewed_at=timezone.now(),
                    review_note=note,
                )
            )
            if changed != 1:
                raise ValidationError(
                    {"detail": "Another reviewer changed this entry. Refresh the page."}
                )
            instance.refresh_from_db()
            record(
                request.user,
                action_name,
                instance,
                before=before,
                summary=f"{action_name.title()}: {note[:200]}",
            )
        return Response(self.get_serializer(instance).data)


class ExpenseViewSet(FinancialRecords):
    queryset = Expense.objects.select_related("plan", "created_by", "reviewed_by").order_by(
        "-spent_on", "-id"
    )
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        return filter_records(
            self.queryset,
            self.request.query_params,
            "spent_on",
            ["description", "vendor", "receipt_reference"],
        )


class PaymentViewSet(FinancialRecords):
    queryset = Payment.objects.select_related("created_by", "reviewed_by").order_by(
        "-paid_on", "-id"
    )
    serializer_class = PaymentSerializer

    def get_queryset(self):
        return filter_records(
            self.queryset,
            self.request.query_params,
            "paid_on",
            ["donor_name", "reference", "transaction_reference"],
        )


class AuditViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = AuditEvent.objects.select_related("actor").all()
    serializer_class = AuditSerializer
    permission_classes = [ManagementRead]

    def get_queryset(self):
        return filter_records(
            self.queryset,
            self.request.query_params,
            "created_at",
            ["actor_name", "summary", "resource"],
        )
