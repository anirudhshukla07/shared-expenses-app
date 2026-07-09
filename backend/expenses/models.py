from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Person(TimeStampedModel):
    name = models.CharField(max_length=120)
    canonical_name = models.CharField(max_length=120, unique=True)
    email = models.EmailField(blank=True)

    def __str__(self):
        return self.name


class ExpenseGroup(TimeStampedModel):
    name = models.CharField(max_length=160)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)

    def __str__(self):
        return self.name


class GroupMembership(TimeStampedModel):
    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE, related_name="memberships")
    person = models.ForeignKey(Person, on_delete=models.CASCADE, related_name="memberships")
    starts_on = models.DateField()
    ends_on = models.DateField(null=True, blank=True)
    role = models.CharField(max_length=50, default="member")

    class Meta:
        ordering = ["starts_on", "person__name"]

    def is_active_on(self, day):
        return self.starts_on <= day and (self.ends_on is None or day <= self.ends_on)

    def __str__(self):
        end = self.ends_on.isoformat() if self.ends_on else "present"
        return f"{self.person} in {self.group} from {self.starts_on} to {end}"


class ImportBatch(TimeStampedModel):
    class Status(models.TextChoices):
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE, related_name="imports")
    uploaded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    source_filename = models.CharField(max_length=255)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PROCESSING)
    total_rows = models.PositiveIntegerField(default=0)
    posted_rows = models.PositiveIntegerField(default=0)
    review_rows = models.PositiveIntegerField(default=0)
    skipped_rows = models.PositiveIntegerField(default=0)
    report_json = models.JSONField(default=dict, blank=True)

    def __str__(self):
        return f"Import {self.id}: {self.source_filename}"


class LedgerStatus(models.TextChoices):
    POSTED = "POSTED", "Posted"
    REVIEW_REQUIRED = "REVIEW_REQUIRED", "Review required"
    SKIPPED = "SKIPPED", "Skipped"


class Expense(TimeStampedModel):
    class SplitType(models.TextChoices):
        EQUAL = "equal", "Equal"
        UNEQUAL = "unequal", "Unequal"
        PERCENTAGE = "percentage", "Percentage"
        SHARE = "share", "Share"

    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE, related_name="expenses")
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="expenses")
    raw_row_number = models.PositiveIntegerField(null=True, blank=True)
    date = models.DateField()
    description = models.CharField(max_length=255)
    normalized_description = models.CharField(max_length=255, db_index=True)
    paid_by = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="expenses_paid")
    amount_original = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    fx_rate_to_inr = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    amount_inr = models.DecimalField(max_digits=14, decimal_places=2)
    split_type = models.CharField(max_length=20, choices=SplitType.choices)
    split_with_raw = models.TextField(blank=True)
    split_details_raw = models.TextField(blank=True)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=LedgerStatus.choices, default=LedgerStatus.POSTED)

    class Meta:
        ordering = ["date", "id"]

    def __str__(self):
        return f"{self.date} {self.description} {self.amount_inr} INR"


class ExpenseSplit(TimeStampedModel):
    expense = models.ForeignKey(Expense, on_delete=models.CASCADE, related_name="splits")
    person = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="expense_splits")
    amount_owed_inr = models.DecimalField(max_digits=14, decimal_places=2)
    basis = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("expense", "person")]


class Settlement(TimeStampedModel):
    group = models.ForeignKey(ExpenseGroup, on_delete=models.CASCADE, related_name="settlements")
    import_batch = models.ForeignKey(ImportBatch, on_delete=models.SET_NULL, null=True, blank=True, related_name="settlements")
    raw_row_number = models.PositiveIntegerField(null=True, blank=True)
    date = models.DateField()
    paid_by = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="settlements_paid")
    paid_to = models.ForeignKey(Person, on_delete=models.PROTECT, related_name="settlements_received")
    amount_original = models.DecimalField(max_digits=14, decimal_places=2)
    currency = models.CharField(max_length=3, default="INR")
    fx_rate_to_inr = models.DecimalField(max_digits=12, decimal_places=4, default=1)
    amount_inr = models.DecimalField(max_digits=14, decimal_places=2)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=LedgerStatus.choices, default=LedgerStatus.POSTED)

    class Meta:
        ordering = ["date", "id"]


class ImportAnomaly(TimeStampedModel):
    class Severity(models.TextChoices):
        INFO = "INFO", "Info"
        WARNING = "WARNING", "Warning"
        ERROR = "ERROR", "Error"

    class ReviewStatus(models.TextChoices):
        NOT_REQUIRED = "NOT_REQUIRED", "Not required"
        PENDING = "PENDING", "Pending"
        APPROVED = "APPROVED", "Approved"
        REJECTED = "REJECTED", "Rejected"

    batch = models.ForeignKey(ImportBatch, on_delete=models.CASCADE, related_name="anomalies")
    row_number = models.PositiveIntegerField(null=True, blank=True)
    code = models.CharField(max_length=80, db_index=True)
    severity = models.CharField(max_length=20, choices=Severity.choices)
    message = models.TextField()
    policy = models.TextField()
    action_taken = models.TextField()
    requires_review = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=ReviewStatus.choices, default=ReviewStatus.NOT_REQUIRED)
    expense = models.ForeignKey(Expense, on_delete=models.SET_NULL, null=True, blank=True, related_name="anomalies")
    settlement = models.ForeignKey(Settlement, on_delete=models.SET_NULL, null=True, blank=True, related_name="anomalies")
    suggested_payload = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["row_number", "id"]

    def save(self, *args, **kwargs):
        if self.requires_review and self.status == self.ReviewStatus.NOT_REQUIRED:
            self.status = self.ReviewStatus.PENDING
        super().save(*args, **kwargs)
