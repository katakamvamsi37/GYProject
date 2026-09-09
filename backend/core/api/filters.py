from datetime import date
from django.db.models import Q
from rest_framework.exceptions import ValidationError


def festival_year(params):
    try:
        year = int(params.get("year", date.today().year))
        if not 2000 <= year <= 2100:
            raise ValueError()
        return year
    except (ValueError, TypeError):
        raise ValidationError({"year": "Choose a year between 2000 and 2100."})


def filter_records(queryset, params, date_field=None, search_fields=()):
    available_fields = {field.name for field in queryset.model._meta.get_fields()}
    for name in ("status", "category", "plan"):
        if params.get(name) and name not in available_fields:
            raise ValidationError({name: "This filter does not apply to these records."})
    if date_field:
        queryset = queryset.filter(**{date_field + "__year": festival_year(params)})
    search = params.get("search", "").strip()
    if search and search_fields:
        clause = Q()
        for field in search_fields:
            clause |= Q(**{field + "__icontains": search})
        queryset = queryset.filter(clause)
    if params.get("status"):
        queryset = queryset.filter(status=params["status"])
    if params.get("category"):
        queryset = queryset.filter(category__iexact=params["category"])
    if params.get("plan"):
        try:
            queryset = queryset.filter(plan_id=int(params["plan"]))
        except ValueError:
            raise ValidationError({"plan": "Choose a valid budget."})
    return queryset
