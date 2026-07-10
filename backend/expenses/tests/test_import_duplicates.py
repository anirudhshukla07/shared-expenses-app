import tempfile
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.contrib.auth import get_user_model
from django.test import TestCase

from expenses.models import ExpenseGroup, GroupMembership, ImportBatch, Person
from expenses.services.balances import calculate_group_balances
from expenses.services.importer import ExpenseImportService, canonical_key


class ImportDuplicateTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="demo")
        self.group = ExpenseGroup.objects.create(name="Flatmates Feb-Apr 2026", created_by=self.user)
        self.aisha = self.create_person("Aisha")
        self.rohan = self.create_person("Rohan")
        for person in [self.aisha, self.rohan]:
            GroupMembership.objects.create(
                group=self.group,
                person=person,
                starts_on=date(2026, 2, 1),
            )

    def create_person(self, name):
        return Person.objects.create(name=name, canonical_name=canonical_key(name))

    def import_csv(self, contents):
        with tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, newline="") as file:
            file.write(contents)
            path = Path(file.name)
        self.addCleanup(path.unlink, missing_ok=True)
        batch = ImportBatch.objects.create(
            group=self.group,
            uploaded_by=self.user,
            source_filename="expenses.csv",
        )
        service = ExpenseImportService(
            group=self.group,
            batch=batch,
            file_path=path,
            fx_rates={"INR": Decimal("1.00"), "USD": Decimal("83.00")},
        )
        return service.run()

    def test_reimported_expense_requires_review_and_does_not_double_balance(self):
        csv_data = (
            "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
            "2026-02-01,Groceries,Aisha,1000,INR,equal,Aisha;Rohan,,\n"
        )

        first_batch = self.import_csv(csv_data)
        second_batch = self.import_csv(csv_data)

        self.assertEqual(first_batch.posted_rows, 1)
        self.assertEqual(second_batch.posted_rows, 0)
        self.assertEqual(second_batch.review_rows, 0)
        self.assertEqual(second_batch.skipped_rows, 1)
        duplicate = second_batch.anomalies.get(code="DUPLICATE_EXISTING_LEDGER")
        self.assertFalse(duplicate.requires_review)
        self.assertIsNone(duplicate.expense)
        self.assertEqual(
            calculate_group_balances(self.group),
            {"Aisha": Decimal("500.00"), "Rohan": Decimal("-500.00")},
        )

    def test_reimported_settlement_requires_review_and_does_not_double_balance(self):
        csv_data = (
            "date,description,paid_by,amount,currency,split_type,split_with,split_details,notes\n"
            "2026-02-02,Rohan paid Aisha back,Rohan,500,INR,,Aisha,,settlement\n"
        )

        first_batch = self.import_csv(csv_data)
        second_batch = self.import_csv(csv_data)

        self.assertEqual(first_batch.posted_rows, 1)
        self.assertEqual(second_batch.posted_rows, 0)
        self.assertEqual(second_batch.review_rows, 0)
        self.assertEqual(second_batch.skipped_rows, 1)
        duplicate = second_batch.anomalies.get(code="DUPLICATE_EXISTING_SETTLEMENT")
        self.assertFalse(duplicate.requires_review)
        self.assertIsNone(duplicate.settlement)
        self.assertEqual(
            calculate_group_balances(self.group),
            {"Aisha": Decimal("-500.00"), "Rohan": Decimal("500.00")},
        )
