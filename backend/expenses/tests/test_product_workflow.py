from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from rest_framework.test import APIClient

from expenses.models import (
    Expense,
    ExpenseGroup,
    GroupMembership,
    ImportAnomaly,
    ImportBatch,
    Person,
    Settlement,
)
from expenses.services.importer import ExpenseImportService, canonical_key


User = get_user_model()


class ProductWorkflowAPITests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("owner", password="secret")
        self.group = ExpenseGroup.objects.create(name="Flat 4B", created_by=self.user)
        self.aisha = Person.objects.create(name="Aisha", canonical_name="aisha")
        self.rohan = Person.objects.create(name="Rohan", canonical_name="rohan")
        for person in [self.aisha, self.rohan]:
            GroupMembership.objects.create(
                group=self.group,
                person=person,
                starts_on=date(2026, 1, 1),
            )
        self.client = APIClient()
        self.client.force_authenticate(self.user)

    def test_manual_expense_persists_splits_and_explainable_balance(self):
        response = self.client.post(
            "/api/expenses/",
            {
                "group": self.group.id,
                "date": "2026-03-01",
                "description": "March rent",
                "paid_by": self.aisha.id,
                "amount_original": "3000.00",
                "currency": "INR",
                "fx_rate_to_inr": "1",
                "split_type": "equal",
                "splits": [
                    {"person": self.aisha.id, "amount_owed_inr": "1500.00", "basis": "Equal split"},
                    {"person": self.rohan.id, "amount_owed_inr": "1500.00", "basis": "Equal split"},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        expense = Expense.objects.get()
        self.assertEqual(expense.normalized_description, "march rent")
        self.assertEqual(expense.splits.count(), 2)

        balance = self.client.get(f"/api/groups/{self.group.id}/balances/")
        self.assertEqual(balance.status_code, 200)
        self.assertEqual(balance.data["balances"], {"Aisha": "1500.00", "Rohan": "-1500.00"})
        rohan_entries = balance.data["breakdown"]["Rohan"]["entries"]
        self.assertEqual(rohan_entries[0]["description"], "March rent")
        self.assertEqual(rohan_entries[0]["amount_inr"], "-1500.00")

    def test_expense_rejects_member_outside_effective_dates(self):
        membership = GroupMembership.objects.get(group=self.group, person=self.rohan)
        membership.starts_on = date(2026, 4, 15)
        membership.save()
        response = self.client.post(
            "/api/expenses/",
            {
                "group": self.group.id,
                "date": "2026-03-01",
                "description": "Early dinner",
                "paid_by": self.aisha.id,
                "amount_original": "100.00",
                "currency": "INR",
                "fx_rate_to_inr": "1",
                "split_type": "equal",
                "splits": [
                    {"person": self.rohan.id, "amount_owed_inr": "100.00", "basis": "Equal split"},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("not an active member", str(response.data))

    def test_usd_settlement_records_explicit_conversion(self):
        response = self.client.post(
            "/api/settlements/",
            {
                "group": self.group.id,
                "date": "2026-03-02",
                "paid_by": self.rohan.id,
                "paid_to": self.aisha.id,
                "amount_original": "50.00",
                "currency": "USD",
                "fx_rate_to_inr": "83.00",
                "notes": "Repayment",
            },
            format="json",
        )
        self.assertEqual(response.status_code, 201, response.data)
        settlement = Settlement.objects.get()
        self.assertEqual(settlement.amount_inr, Decimal("4150.00"))
        self.assertEqual(settlement.fx_rate_to_inr, Decimal("83.0000"))

    def test_report_download_contains_policy_and_final_status(self):
        batch = ImportBatch.objects.create(
            group=self.group,
            uploaded_by=self.user,
            source_filename="expenses_export.csv",
            total_rows=1,
            review_rows=1,
            report_json={"rows": [{"row_number": 8, "status": "REVIEW_REQUIRED"}]},
        )
        ImportAnomaly.objects.create(
            batch=batch,
            row_number=8,
            code="MISSING_PAYER",
            severity="ERROR",
            message="Payer is blank.",
            policy="Never infer a payer.",
            action_taken="Skipped row.",
            requires_review=True,
        )
        response = self.client.get(f"/api/imports/{batch.id}/report/?export=csv")
        body = response.content.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Never infer a payer", body)
        self.assertIn("REVIEW_REQUIRED", body)


class OriginalCSVImportTests(TestCase):
    def test_original_csv_completes_and_accounts_for_every_row(self):
        call_command("seed_demo", verbosity=0)
        user = User.objects.get(username="demo")
        group = ExpenseGroup.objects.get(name="Flatmates Feb-Apr 2026", created_by=user)
        batch = ImportBatch.objects.create(
            group=group,
            uploaded_by=user,
            source_filename="expenses_export.csv",
        )
        source = Path(__file__).resolve().parents[2] / "sample_data" / "expenses_export.csv"
        result = ExpenseImportService(
            group=group,
            batch=batch,
            file_path=source,
            fx_rates={"INR": "1", "USD": "83"},
        ).run()

        self.assertEqual(result.total_rows, 42)
        self.assertEqual(
            result.posted_rows + result.review_rows + result.skipped_rows,
            result.total_rows,
        )
        self.assertGreaterEqual(
            result.anomalies.values("code").distinct().count(),
            12,
        )
