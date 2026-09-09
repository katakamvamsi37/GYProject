"""Authenticated exports share the ledger filters and neutralize spreadsheet formulas."""

import csv
import io
from datetime import date, datetime
from decimal import Decimal
from django.http import HttpResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.exceptions import ValidationError
from openpyxl import Workbook
from core.models import Expense, Payment, Member, AuditEvent, Plan
from django.db.models import Sum, Q
from .filters import filter_records, festival_year
from .permissions import ManagementRead

EXPORTS = {
    "plans": (
        Plan,
        "target_date",
        ["id", "title", "category", "budget", "actual_spent", "status", "target_date"],
        ["title", "category"],
    ),
    "expenses": (
        Expense,
        "spent_on",
        [
            "id",
            "description",
            "category",
            "amount",
            "spent_on",
            "status",
            "vendor",
            "receipt_reference",
            "evidence_url",
            "plan_id",
            "created_by_id",
            "reviewed_by_id",
            "reviewed_at",
            "review_note",
        ],
        ["description", "vendor", "receipt_reference"],
    ),
    "payments": (
        Payment,
        "paid_on",
        [
            "reference",
            "donor_name",
            "amount",
            "method",
            "paid_on",
            "status",
            "transaction_reference",
            "evidence_url",
            "created_by_id",
            "reviewed_by_id",
            "reviewed_at",
            "review_note",
        ],
        ["donor_name", "reference", "transaction_reference"],
    ),
    "members": (
        Member,
        None,
        ["name", "email", "phone", "position", "authority", "active"],
        ["name", "email", "position"],
    ),
    "audit": (
        AuditEvent,
        "created_at",
        [
            "created_at",
            "actor_name",
            "action",
            "resource",
            "object_id",
            "summary",
            "before",
            "after",
        ],
        ["actor_name", "summary", "resource"],
    ),
}


def safe_cell(value, spreadsheet=False):
    if value is None:
        return ""
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value) if spreadsheet else str(value)
    if isinstance(value, (dict, list)):
        value = str(value)
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


@api_view(["GET"])
@permission_classes([IsAuthenticated, ManagementRead])
def export_records(request, resource):
    if resource not in EXPORTS:
        raise ValidationError({"resource": "Unknown export."})
    output_format = request.query_params.get("file_format", "csv")
    if output_format not in ("csv", "xlsx"):
        raise ValidationError({"file_format": "Choose csv or xlsx."})
    model, date_field, columns, search_fields = EXPORTS[resource]
    params = request.query_params.copy()
    # Only applicable filters are accepted by each resource.
    if resource in ("members", "audit"):
        for key in ("status", "category", "plan"):
            params.pop(key, None)
    if resource == "payments":
        params.pop("category", None)
        params.pop("plan", None)
    queryset = filter_records(model.objects.order_by("pk"), params, date_field, search_fields)
    if resource == "plans":
        queryset = queryset.annotate(
            actual_spent=Sum("expenses__amount", filter=Q(expenses__status="approved"), default=0)
        )
    rows = queryset.values_list(*columns).iterator(chunk_size=500)
    if output_format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(columns)
        for row in rows:
            writer.writerow([safe_cell(value) for value in row])
        response = HttpResponse(
            "\ufeff" + output.getvalue(), content_type="text/csv; charset=utf-8"
        )
    else:
        book = Workbook(write_only=True)
        sheet = book.create_sheet(resource.title())
        sheet.append(columns)
        for row in rows:
            sheet.append([safe_cell(value, spreadsheet=True) for value in row])
        output = io.BytesIO()
        book.save(output)
        response = HttpResponse(
            output.getvalue(),
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
    year = festival_year(params)
    response["Content-Disposition"] = (
        f'attachment; filename="ganesh-{resource}-{year}.{output_format}"'
    )
    return response
