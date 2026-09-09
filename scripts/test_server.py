"""Browser-test API using a temporary database; never touches backend/db.sqlite3."""

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
os.environ["DJANGO_DEBUG"] = "true"
os.environ["DJANGO_ALLOWED_HOSTS"] = "127.0.0.1,localhost"
import django
from django.conf import settings

with tempfile.TemporaryDirectory(prefix="gy-browser-tests-") as directory:
    settings.DATABASES["default"] = {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": str(Path(directory) / "test.sqlite3"),
    }
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []
    settings.REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"]["login"] = "1000/minute"
    django.setup()
    from django.core.management import call_command
    from django.contrib.auth import get_user_model
    from core.models import UserProfile, Plan, Expense, Payment, Member

    call_command("migrate", verbosity=0)
    accounts = {}
    for role in ("admin", "treasurer", "member"):
        user = get_user_model().objects.create_user(
            username=role,
            email=f"{role}@example.test",
            first_name=role.title(),
            password="BrowserTest!234",
        )
        UserProfile.objects.create(user=user, role=role)
        accounts[role] = user
    year = date.today().year
    plan = Plan.objects.create(
        title="Mandap and decoration",
        category="Decoration",
        budget=80000,
        target_date=date(year, 9, 1),
    )
    Expense.objects.create(
        description="Mandap setup and flowers",
        category="Decoration",
        amount=12000,
        spent_on=date(year, 9, 1),
        plan=plan,
        status="approved",
        created_by=accounts["treasurer"],
        reviewed_by=accounts["admin"],
        vendor="Festival supplier",
        receipt_reference="TEST-BILL-01",
    )
    Expense.objects.create(
        description="Prasadam ingredients",
        category="Food & prasadam",
        amount=4500,
        spent_on=date(year, 9, 2),
        status="pending",
        created_by=accounts["treasurer"],
        vendor="Community kitchen",
        receipt_reference="TEST-BILL-02",
    )
    Payment.objects.create(
        donor_name="Community contributions",
        amount=35000,
        method="Cash",
        reference="TEST-RECEIPT-01",
        status="confirmed",
        created_by=accounts["treasurer"],
        reviewed_by=accounts["admin"],
    )
    Member.objects.create(
        name="Festival volunteer", email="volunteer@example.test", position="Decoration coordinator"
    )
    call_command("runserver", "127.0.0.1:8011", use_reloader=False)
