from decimal import Decimal

from django.test import SimpleTestCase

from expenses.services.importer import ExpenseImportService


class SplitMathTests(SimpleTestCase):
    def test_allocate_by_weights_rounds_to_total(self):
        service = object.__new__(ExpenseImportService)
        splits = service.allocate_by_weights(
            Decimal("899.995"),
            [("Aisha", Decimal("1"), "equal"), ("Rohan", Decimal("1"), "equal"), ("Priya", Decimal("1"), "equal")],
        )
        total = sum(amount for _, amount, _ in splits)
        self.assertEqual(total, Decimal("900.00"))
