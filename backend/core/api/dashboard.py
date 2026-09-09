from decimal import Decimal
from django.db.models import Sum
from django.db.models.functions import ExtractMonth
from rest_framework.decorators import api_view
from rest_framework.response import Response
from core.models import Plan, Expense, Payment, Member
from .filters import festival_year
from .permissions import role_for, MANAGEMENT_ROLES
from .serializers import ExpenseSerializer


def total(queryset, field="amount"):
    return queryset.aggregate(value=Sum(field))["value"] or Decimal("0")


@api_view(["GET"])
def dashboard(request):
    year = festival_year(request.query_params)
    plans = Plan.objects.filter(target_date__year=year).exclude(status="Cancelled")
    expenses = Expense.objects.filter(spent_on__year=year)
    payments = Payment.objects.filter(paid_on__year=year)
    approved = expenses.filter(status="approved")
    confirmed = payments.filter(status="confirmed")
    budget, spent, collected = total(plans, "budget"), total(approved), total(confirmed)
    # Basic members see aggregate transparency figures, never donor/contact/audit records.
    data = {
        "year": year,
        "budget": str(budget),
        "spent": str(spent),
        "collected": str(collected),
        "remaining_budget": str(budget - spent),
        "cash_balance": str(collected - spent),
        "members": Member.objects.filter(active=True).count(),
        "plans": plans.count(),
        "pending_expenses": expenses.filter(status="pending").count(),
        "pending_collections": payments.filter(status="pending").count(),
        "pending_amount": str(total(expenses.filter(status="pending"))),
        "missing_receipts": expenses.filter(
            status__in=["pending", "approved"], receipt_reference="", evidence_url=""
        ).count(),
        "legacy_payments": payments.exclude(
            status__in=["pending", "confirmed", "rejected", "void"]
        ).count(),
    }
    monthly = {
        row["month"]: row["amount"]
        for row in approved.annotate(month=ExtractMonth("spent_on"))
        .values("month")
        .annotate(amount=Sum("amount"))
    }
    data["monthly_spend"] = [
        {"month": name, "amount": str(monthly.get(i, 0))}
        for i, name in enumerate(
            ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1
        )
    ]
    data["expenses_by_category"] = list(
        approved.values("category").annotate(amount=Sum("amount")).order_by("-amount")
    )
    data["recent_expenses"] = (
        ExpenseSerializer(
            expenses.select_related("plan", "created_by", "reviewed_by").order_by(
                "-spent_on", "-id"
            )[:5],
            many=True,
        ).data
        if role_for(request.user) in MANAGEMENT_ROLES
        else []
    )
    return Response(data)
