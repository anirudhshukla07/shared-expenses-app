from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db import transaction

from expenses.models import Expense, ExpenseGroup, ImportAnomaly, ImportBatch, LedgerStatus, Settlement


class Command(BaseCommand):
    help = "Mark duplicate imported ledger rows as skipped while keeping one canonical row."

    def add_arguments(self, parser):
        parser.add_argument("--group-id", type=int, help="Only dedupe one expense group.")
        parser.add_argument("--dry-run", action="store_true", help="Show what would change without writing.")

    def handle(self, *args, **options):
        groups = ExpenseGroup.objects.all().order_by("id")
        if options["group_id"]:
            groups = groups.filter(id=options["group_id"])

        total_expenses = 0
        total_settlements = 0
        with transaction.atomic():
            for group in groups:
                expense_count = self.dedupe_expenses(group, options["dry_run"])
                settlement_count = self.dedupe_settlements(group, options["dry_run"])
                self.clear_skipped_reviews(group, options["dry_run"])
                self.recalculate_batches(group, options["dry_run"])
                total_expenses += expense_count
                total_settlements += settlement_count
                self.stdout.write(
                    f"{group.name}: {expense_count} duplicate expenses, "
                    f"{settlement_count} duplicate settlements"
                )
            if options["dry_run"]:
                transaction.set_rollback(True)

        mode = "Would mark" if options["dry_run"] else "Marked"
        self.stdout.write(self.style.SUCCESS(f"{mode} {total_expenses} expenses and {total_settlements} settlements as skipped."))

    def dedupe_expenses(self, group, dry_run):
        rows_by_key = defaultdict(list)
        expenses = (
            Expense.objects.filter(group=group, status__in=[LedgerStatus.POSTED, LedgerStatus.REVIEW_REQUIRED])
            .select_related("paid_by", "import_batch")
            .prefetch_related("splits__person")
            .order_by("id")
        )
        for expense in expenses:
            split_key = tuple(
                sorted(
                    (split.person.canonical_name, str(split.amount_owed_inr), split.basis)
                    for split in expense.splits.all()
                )
            )
            key = (
                expense.date,
                expense.normalized_description,
                expense.paid_by.canonical_name,
                str(expense.amount_original),
                expense.currency,
                expense.split_type,
                expense.split_with_raw,
                expense.split_details_raw,
                split_key,
            )
            rows_by_key[key].append(expense)
        return self.mark_duplicates(rows_by_key, dry_run)

    def dedupe_settlements(self, group, dry_run):
        rows_by_key = defaultdict(list)
        settlements = (
            Settlement.objects.filter(group=group, status__in=[LedgerStatus.POSTED, LedgerStatus.REVIEW_REQUIRED])
            .select_related("paid_by", "paid_to", "import_batch")
            .order_by("id")
        )
        for settlement in settlements:
            key = (
                settlement.date,
                settlement.paid_by.canonical_name,
                settlement.paid_to.canonical_name,
                str(settlement.amount_original),
                settlement.currency,
            )
            rows_by_key[key].append(settlement)
        return self.mark_duplicates(rows_by_key, dry_run)

    def mark_duplicates(self, rows_by_key, dry_run):
        skipped = 0
        for rows in rows_by_key.values():
            if len(rows) < 2:
                continue
            keep = self.choose_canonical(rows)
            for row in rows:
                if row.id == keep.id:
                    continue
                skipped += 1
                if not dry_run:
                    row.status = LedgerStatus.SKIPPED
                    row.save(update_fields=["status", "updated_at"])
                    self.clear_duplicate_review(row)
        return skipped

    def choose_canonical(self, rows):
        posted = [row for row in rows if row.status == LedgerStatus.POSTED]
        candidates = posted or rows
        return max(candidates, key=lambda row: ((row.import_batch_id or 0), row.id))

    def clear_duplicate_review(self, row):
        filters = {}
        if isinstance(row, Expense):
            filters["expense"] = row
        else:
            filters["settlement"] = row
        ImportAnomaly.objects.filter(**filters).update(
            requires_review=False,
            status=ImportAnomaly.ReviewStatus.NOT_REQUIRED,
            action_taken="Skipped duplicate row.",
        )

    def clear_skipped_reviews(self, group, dry_run):
        if dry_run:
            return
        skipped_expenses = Expense.objects.filter(group=group, status=LedgerStatus.SKIPPED)
        skipped_settlements = Settlement.objects.filter(group=group, status=LedgerStatus.SKIPPED)
        ImportAnomaly.objects.filter(expense__in=skipped_expenses).update(
            requires_review=False,
            status=ImportAnomaly.ReviewStatus.NOT_REQUIRED,
            action_taken="Skipped duplicate row.",
        )
        ImportAnomaly.objects.filter(settlement__in=skipped_settlements).update(
            requires_review=False,
            status=ImportAnomaly.ReviewStatus.NOT_REQUIRED,
            action_taken="Skipped duplicate row.",
        )

    def recalculate_batches(self, group, dry_run):
        for batch in ImportBatch.objects.filter(group=group):
            posted_rows = (
                batch.expenses.filter(status=LedgerStatus.POSTED).count()
                + batch.settlements.filter(status=LedgerStatus.POSTED).count()
            )
            review_rows = (
                batch.expenses.filter(status=LedgerStatus.REVIEW_REQUIRED).count()
                + batch.settlements.filter(status=LedgerStatus.REVIEW_REQUIRED).count()
            )
            skipped_rows = max(batch.total_rows - posted_rows - review_rows, 0)
            if not dry_run:
                batch.posted_rows = posted_rows
                batch.review_rows = review_rows
                batch.skipped_rows = skipped_rows
                if isinstance(batch.report_json, dict):
                    batch.report_json["posted_rows"] = posted_rows
                    batch.report_json["review_rows"] = review_rows
                    batch.report_json["skipped_rows"] = skipped_rows
                batch.save(update_fields=["posted_rows", "review_rows", "skipped_rows", "report_json", "updated_at"])
