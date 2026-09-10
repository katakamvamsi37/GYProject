from datetime import date
from decimal import Decimal
from django.contrib.auth import get_user_model
from django.core.management import call_command
from core.models import Expense, Payment, Plan, AuditEvent, UserProfile
from .base import APITestCase

YEAR = date.today().year


class FinancialWorkflowTests(APITestCase):
    def expense(self, **changes):
        body = {
            "description": "Pooja flowers",
            "category": "Pooja & rituals",
            "amount": "150.25",
            "spent_on": f"{YEAR}-09-01",
            "vendor": "Flower supplier",
            "receipt_reference": "BILL-001",
        }
        body.update(changes)
        return self.post("/api/expenses/", body)

    def test_submit_review_dashboard_void_audit(self):
        response = self.expense()
        self.assertEqual(response.status_code, 201)
        item_id = response.data["id"]
        dashboard = self.client.get(f"/api/dashboard/?year={YEAR}").data
        self.assertEqual(Decimal(dashboard["spent"]), 0)
        self.assertEqual(dashboard["pending_expenses"], 1)
        self.assertEqual(
            self.post(
                f"/api/expenses/{item_id}/review/", {"action": "approve", "note": "Checked bill"}
            ).status_code,
            400,
        )
        self.use("treasurer")
        response = self.post(
            f"/api/expenses/{item_id}/review/",
            {"action": "approve", "note": "Checked supplier bill"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")
        self.assertEqual(
            Decimal(self.client.get("/api/dashboard/").data["spent"]), Decimal("150.25")
        )
        self.assertEqual(
            self.post(
                f"/api/expenses/{item_id}/review/", {"action": "approve", "note": "Again"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.client.patch(
                f"/api/expenses/{item_id}/", {"amount": "1"}, format="json"
            ).status_code,
            405,
        )
        self.assertEqual(self.client.delete(f"/api/expenses/{item_id}/").status_code, 405)
        self.assertEqual(
            self.post(
                f"/api/expenses/{item_id}/review/",
                {"action": "void", "note": "Duplicate voucher; replacing entry"},
            ).status_code,
            200,
        )
        self.assertEqual(Decimal(self.client.get("/api/dashboard/").data["spent"]), 0)
        self.assertEqual(
            list(
                AuditEvent.objects.filter(resource="expense")
                .order_by("id")
                .values_list("action", flat=True)
            ),
            ["submitted", "approve", "void"],
        )
        self.assertEqual(AuditEvent.objects.get(action="approve").before["status"], "pending")

    def test_invalid_amount_and_year_rejected(self):
        for value in ["0", "-1", "abc", "1.999", "999999999999999"]:
            self.assertEqual(self.expense(amount=value).status_code, 400)
        self.assertEqual(self.client.get("/api/dashboard/?year=bad").status_code, 400)
        self.assertEqual(self.client.get("/api/expenses/?year=99999").status_code, 400)

    def test_basic_member_cannot_read_contacts_or_mutate_finances(self):
        self.use("member")
        for url in ["members", "plans", "expenses", "payments", "audit"]:
            self.assertEqual(self.client.get(f"/api/{url}/").status_code, 403)
        self.assertEqual(self.expense().status_code, 403)
        self.assertEqual(self.client.get("/api/dashboard/").status_code, 200)
        self.assertEqual(self.client.get("/api/dashboard/").data["recent_expenses"], [])

    def test_coordinator_can_submit_but_not_review(self):
        self.use("coordinator")
        response = self.expense()
        self.assertEqual(response.status_code, 201)
        self.assertEqual(
            self.post(
                f"/api/expenses/{response.data['id']}/review/",
                {"action": "approve", "note": "Okay"},
            ).status_code,
            403,
        )
        self.assertEqual(self.post("/api/plans/", {}).status_code, 403)

    def test_plan_spending_is_derived_and_year_consistent(self):
        plan = Plan.objects.create(
            title="Rituals", category="Pooja", budget=1000, spent=999, target_date=date(YEAR, 9, 1)
        )
        bad_plan = Plan.objects.create(
            title="Old year", category="Pooja", budget=1000, target_date=date(YEAR - 1, 9, 1)
        )
        self.assertEqual(self.expense(plan=bad_plan.pk).status_code, 400)
        response = self.expense(plan=plan.pk)
        self.use("treasurer")
        self.post(
            f"/api/expenses/{response.data['id']}/review/",
            {"action": "approve", "note": "Bill verified"},
        )
        rows = self.client.get("/api/plans/").data["results"]
        self.assertEqual(Decimal(rows[0]["spent"]), Decimal("150.25"))
        response = self.client.patch(
            f"/api/plans/{plan.pk}/", {"target_date": f"{YEAR + 1}-09-01"}, format="json"
        )
        self.assertEqual(response.status_code, 400)

    def test_collection_confirmation_excludes_legacy(self):
        Payment.objects.create(
            donor_name="Old demo", amount=9999, reference="GY-DEMO-0001", status="Dummy verified"
        )
        body = {
            "donor_name": "Supporter",
            "amount": "200",
            "method": "UPI",
            "paid_on": f"{YEAR}-09-01T12:00:00+05:30",
        }
        self.assertEqual(self.post("/api/payments/", body).status_code, 400)
        body["transaction_reference"] = "BANK-001"
        response = self.post("/api/payments/", body)
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Decimal(self.client.get("/api/dashboard/").data["collected"]), 0)
        self.use("treasurer")
        self.assertEqual(
            self.post(
                f"/api/payments/{response.data['id']}/review/",
                {"action": "approve", "note": "Bank entry matched"},
            ).status_code,
            200,
        )
        self.assertEqual(Decimal(self.client.get("/api/dashboard/").data["collected"]), 200)

    def test_second_admin_can_approve_cash_collection(self):
        creator = self.accounts["admin"]
        reviewer = get_user_model().objects.create_user(username="second_admin")
        UserProfile.objects.create(user=reviewer, role="admin")
        response = self.post(
            "/api/payments/",
            {
                "donor_name": "uday",
                "amount": "100000.00",
                "method": "Cash",
                "transaction_reference": "",
                "paid_on": f"{YEAR}-09-10T12:00:00+05:30",
            },
        )
        self.assertEqual(response.status_code, 201, response.data)
        item_id = response.data["id"]
        url = f"/api/payments/{item_id}/review/"
        decision = {"action": "approve", "note": "good"}
        own_review = self.post(url, decision)
        self.assertEqual(own_review.status_code, 400)
        self.assertIn("A different administrator", str(own_review.data["detail"]))
        self.assertEqual(Payment.objects.get(pk=item_id).status, "pending")

        self.client.force_authenticate(user=reviewer)
        response = self.post(url, decision)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "confirmed")
        self.assertEqual(response.data["created_by"], creator.pk)
        self.assertEqual(response.data["reviewed_by"], reviewer.pk)
        self.assertEqual(response.data["reviewed_by_name"], reviewer.username)
        self.assertEqual(response.data["review_note"], "good")
        self.assertIsNotNone(response.data["reviewed_at"])
        self.assertEqual(
            Decimal(self.client.get(f"/api/dashboard/?year={YEAR}").data["collected"]),
            Decimal("100000.00"),
        )
        self.assertEqual(self.post(url, decision).status_code, 400)
        event = AuditEvent.objects.get(
            resource="payment", object_id=str(item_id), action="approve"
        )
        self.assertEqual(event.actor_id, reviewer.pk)
        self.assertEqual(event.before["status"], "pending")
        self.assertEqual(event.after["status"], "confirmed")

    def test_second_admin_can_approve_expense_without_budget(self):
        response = self.expense()
        self.assertEqual(response.status_code, 201)
        reviewer = get_user_model().objects.create_user(username="second_admin")
        UserProfile.objects.create(user=reviewer, role="admin")
        self.client.force_authenticate(user=reviewer)
        response = self.post(
            f"/api/expenses/{response.data['id']}/review/",
            {"action": "approve", "note": "Receipt verified"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["status"], "approved")
        self.assertIsNone(response.data["plan"])
        self.assertEqual(response.data["reviewed_by"], reviewer.pk)

    def test_list_pagination_and_audit_read_only(self):
        Expense.objects.bulk_create(
            [
                Expense(
                    description=f"Expense {i}",
                    category="Operations",
                    amount=1,
                    spent_on=date(YEAR, 9, 1),
                )
                for i in range(28)
            ]
        )
        response = self.client.get("/api/expenses/").data
        self.assertEqual(response["count"], 28)
        self.assertEqual(len(response["results"]), 25)
        self.assertIsNotNone(response["next"])
        self.assertEqual(self.post("/api/audit/", {}).status_code, 405)

    def test_seed_demo_preserves_existing_data(self):
        self.expense()
        existing = Expense.objects.count()
        call_command("seed_demo", verbosity=0)
        call_command("seed_demo", verbosity=0)
        self.assertEqual(Expense.objects.count(), existing)
        self.assertEqual(Plan.objects.filter(title__startswith="[DEMO]").count(), 3)

    def test_financial_retry_returns_same_record_and_one_audit_event(self):
        from uuid import uuid4

        key = str(uuid4())
        body = {
            "description": "Retry-safe voucher",
            "category": "Operations",
            "amount": "50",
            "spent_on": f"{YEAR}-09-01",
        }
        first = self.client.post("/api/expenses/", body, format="json", HTTP_IDEMPOTENCY_KEY=key)
        second = self.client.post("/api/expenses/", body, format="json", HTTP_IDEMPOTENCY_KEY=key)
        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(first.data["id"], second.data["id"])
        self.assertEqual(Expense.objects.count(), 1)
        self.assertEqual(AuditEvent.objects.count(), 1)
        body["amount"] = "51"
        self.assertEqual(
            self.client.post(
                "/api/expenses/", body, format="json", HTTP_IDEMPOTENCY_KEY=key
            ).status_code,
            400,
        )

    def test_non_cash_transaction_reference_cannot_be_recorded_twice(self):
        body = {
            "donor_name": "Supporter",
            "amount": "200",
            "method": "UPI",
            "paid_on": f"{YEAR}-09-01T12:00:00+05:30",
            "transaction_reference": "SAME-BANK-REF",
        }
        self.assertEqual(self.post("/api/payments/", body).status_code, 201)
        self.assertEqual(self.post("/api/payments/", body).status_code, 400)
        self.assertEqual(Payment.objects.count(), 1)

    def test_rejected_entry_does_not_affect_totals_and_reason_is_required(self):
        item = self.expense()
        self.use("treasurer")
        url = f"/api/expenses/{item.data['id']}/review/"
        self.assertEqual(self.post(url, {"action": "reject", "note": ""}).status_code, 400)
        self.assertEqual(
            self.post(url, {"action": "reject", "note": "Wrong voucher"}).status_code, 200
        )
        self.assertEqual(Decimal(self.client.get("/api/dashboard/").data["spent"]), 0)

    def test_budget_and_member_changes_are_audited(self):
        body = {
            "title": "Safety",
            "budget": "2000",
            "category": "Safety",
            "target_date": f"{YEAR}-09-01",
            "status": "Planning",
        }
        created = self.post("/api/plans/", body)
        self.assertEqual(created.status_code, 201)
        response = self.client.patch(
            f"/api/plans/{created.data['id']}/", {"budget": "2200"}, format="json"
        )
        self.assertEqual(response.status_code, 200)
        event = AuditEvent.objects.get(action="budget_updated")
        self.assertEqual(Decimal(event.before["budget"]), Decimal("2000"))
        self.assertEqual(Decimal(event.after["budget"]), Decimal("2200"))

    def test_inapplicable_filters_return_validation_errors(self):
        self.assertEqual(self.client.get("/api/payments/?plan=1").status_code, 400)
        self.assertEqual(self.client.get("/api/audit/?category=Food").status_code, 400)
