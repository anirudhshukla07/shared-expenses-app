from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.db.models import Q
from rest_framework import serializers

from .models import (
    Expense,
    ExpenseGroup,
    ExpenseSplit,
    GroupMembership,
    ImportAnomaly,
    ImportBatch,
    LedgerStatus,
    Person,
    Settlement,
)
from .services.importer import canonical_key, normalize_description


PAISE = Decimal("0.01")


def q(value):
    return Decimal(value).quantize(PAISE, rounding=ROUND_HALF_UP)


class PersonSerializer(serializers.ModelSerializer):
    class Meta:
        model = Person
        fields = ["id", "name", "canonical_name", "email", "created_at", "updated_at"]
        read_only_fields = ["canonical_name", "created_at", "updated_at"]


class ExpenseGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = ExpenseGroup
        fields = ["id", "name", "created_by", "created_at", "updated_at"]
        read_only_fields = ["created_by", "created_at", "updated_at"]


class GroupMembershipSerializer(serializers.ModelSerializer):
    person = serializers.PrimaryKeyRelatedField(queryset=Person.objects.all(), required=False)
    person_name = serializers.CharField(source="person.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)
    person_name_input = serializers.CharField(write_only=True, required=False)

    class Meta:
        model = GroupMembership
        fields = [
            "id",
            "group",
            "group_name",
            "person",
            "person_name",
            "person_name_input",
            "starts_on",
            "ends_on",
            "role",
        ]

    def validate(self, attrs):
        starts_on = attrs.get("starts_on", getattr(self.instance, "starts_on", None))
        ends_on = attrs.get("ends_on", getattr(self.instance, "ends_on", None))
        if starts_on and ends_on and ends_on < starts_on:
            raise serializers.ValidationError({"ends_on": "Leave date cannot be before join date."})

        group = attrs.get("group", getattr(self.instance, "group", None))
        request = self.context.get("request")
        if request and group and group.created_by_id != request.user.id:
            raise serializers.ValidationError({"group": "You do not manage this group."})
        if not attrs.get("person") and not attrs.get("person_name_input") and not self.instance:
            raise serializers.ValidationError({"person_name_input": "Enter a member name."})
        return attrs

    def create(self, validated_data):
        raw_name = validated_data.pop("person_name_input", "").strip()
        if not validated_data.get("person"):
            key = canonical_key(raw_name)
            person, _ = Person.objects.get_or_create(
                canonical_name=key,
                defaults={"name": raw_name},
            )
            validated_data["person"] = person
        return super().create(validated_data)


class ExpenseSplitSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source="person.name", read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ["id", "person", "person_name", "amount_owed_inr", "basis"]


class ExpenseSerializer(serializers.ModelSerializer):
    paid_by_name = serializers.CharField(source="paid_by.name", read_only=True)
    splits = ExpenseSplitSerializer(many=True, required=False)

    class Meta:
        model = Expense
        fields = [
            "id",
            "group",
            "import_batch",
            "raw_row_number",
            "date",
            "description",
            "paid_by",
            "paid_by_name",
            "amount_original",
            "currency",
            "fx_rate_to_inr",
            "amount_inr",
            "split_type",
            "split_with_raw",
            "split_details_raw",
            "notes",
            "status",
            "splits",
        ]

        read_only_fields = ["import_batch", "raw_row_number", "amount_inr", "status"]

    def validate(self, attrs):
        instance = self.instance
        group = attrs.get("group", getattr(instance, "group", None))
        day = attrs.get("date", getattr(instance, "date", None))
        payer = attrs.get("paid_by", getattr(instance, "paid_by", None))
        request = self.context.get("request")
        if request and group and group.created_by_id != request.user.id:
            raise serializers.ValidationError({"group": "You do not manage this group."})

        currency = str(attrs.get("currency", getattr(instance, "currency", "INR"))).upper()
        rate = Decimal(attrs.get("fx_rate_to_inr", getattr(instance, "fx_rate_to_inr", 1)))
        amount = Decimal(attrs.get("amount_original", getattr(instance, "amount_original", 0)))
        if amount <= 0:
            raise serializers.ValidationError({"amount_original": "Expense amount must be positive."})
        if rate <= 0:
            raise serializers.ValidationError({"fx_rate_to_inr": "Exchange rate must be positive."})
        attrs["currency"] = currency
        attrs["amount_inr"] = q(amount * rate)

        splits = attrs.get("splits")
        if not instance and not splits:
            raise serializers.ValidationError({"splits": "Add at least one split allocation."})
        if splits is not None:
            split_total = q(sum((Decimal(item["amount_owed_inr"]) for item in splits), Decimal("0")))
            if split_total != attrs["amount_inr"]:
                raise serializers.ValidationError(
                    {"splits": f"Split allocations total {split_total}, expected {attrs['amount_inr']} INR."}
                )
            people = [item["person"] for item in splits]
            if len({person.id for person in people}) != len(people):
                raise serializers.ValidationError({"splits": "Each member can appear only once."})
            for person in set(people + ([payer] if payer else [])):
                active = GroupMembership.objects.filter(
                    group=group,
                    person=person,
                    starts_on__lte=day,
                ).filter(Q(ends_on__isnull=True) | Q(ends_on__gte=day))
                if not active.exists():
                    raise serializers.ValidationError(
                        {"splits": f"{person.name} is not an active member on {day}."}
                    )
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        splits = validated_data.pop("splits")
        validated_data["normalized_description"] = normalize_description(validated_data["description"])
        expense = Expense.objects.create(**validated_data)
        self._replace_splits(expense, splits)
        return expense

    @transaction.atomic
    def update(self, instance, validated_data):
        splits = validated_data.pop("splits", None)
        if "description" in validated_data:
            validated_data["normalized_description"] = normalize_description(validated_data["description"])
        instance = super().update(instance, validated_data)
        if splits is not None:
            instance.splits.all().delete()
            self._replace_splits(instance, splits)
        return instance

    @staticmethod
    def _replace_splits(expense, splits):
        ExpenseSplit.objects.bulk_create(
            [ExpenseSplit(expense=expense, **split) for split in splits]
        )


class SettlementSerializer(serializers.ModelSerializer):
    paid_by_name = serializers.CharField(source="paid_by.name", read_only=True)
    paid_to_name = serializers.CharField(source="paid_to.name", read_only=True)

    class Meta:
        model = Settlement
        fields = [
            "id",
            "group",
            "import_batch",
            "raw_row_number",
            "date",
            "paid_by",
            "paid_by_name",
            "paid_to",
            "paid_to_name",
            "amount_original",
            "currency",
            "fx_rate_to_inr",
            "amount_inr",
            "notes",
            "status",
        ]
        read_only_fields = ["import_batch", "raw_row_number", "amount_inr", "status"]

    def validate(self, attrs):
        instance = self.instance
        group = attrs.get("group", getattr(instance, "group", None))
        request = self.context.get("request")
        if request and group and group.created_by_id != request.user.id:
            raise serializers.ValidationError({"group": "You do not manage this group."})
        paid_by = attrs.get("paid_by", getattr(instance, "paid_by", None))
        paid_to = attrs.get("paid_to", getattr(instance, "paid_to", None))
        if paid_by == paid_to:
            raise serializers.ValidationError("Payer and recipient must be different people.")
        amount = Decimal(attrs.get("amount_original", getattr(instance, "amount_original", 0)))
        rate = Decimal(attrs.get("fx_rate_to_inr", getattr(instance, "fx_rate_to_inr", 1)))
        if amount <= 0 or rate <= 0:
            raise serializers.ValidationError("Amount and exchange rate must be positive.")
        attrs["currency"] = str(attrs.get("currency", getattr(instance, "currency", "INR"))).upper()
        attrs["amount_inr"] = q(amount * rate)
        return attrs


class ImportAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportAnomaly
        fields = [
            "id",
            "batch",
            "row_number",
            "code",
            "severity",
            "message",
            "policy",
            "action_taken",
            "requires_review",
            "status",
            "expense",
            "settlement",
            "suggested_payload",
            "created_at",
        ]


class ImportBatchSerializer(serializers.ModelSerializer):
    anomalies = ImportAnomalySerializer(many=True, read_only=True)
    processed_rows = serializers.SerializerMethodField()
    pending_review_rows = serializers.SerializerMethodField()
    counts_are_consistent = serializers.SerializerMethodField()

    class Meta:
        model = ImportBatch
        fields = [
            "id",
            "group",
            "uploaded_by",
            "source_filename",
            "status",
            "total_rows",
            "posted_rows",
            "review_rows",
            "skipped_rows",
            "processed_rows",
            "pending_review_rows",
            "counts_are_consistent",
            "report_json",
            "anomalies",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "uploaded_by",
            "status",
            "report_json",
            "created_at",
            "updated_at",
        ]

    def get_processed_rows(self, obj):
        return obj.posted_rows + obj.review_rows + obj.skipped_rows

    def get_pending_review_rows(self, obj):
        """Count input rows awaiting a decision, not individual anomalies."""
        expense_rows = Expense.objects.filter(
            import_batch=obj,
            status=LedgerStatus.REVIEW_REQUIRED,
        ).values_list("raw_row_number", flat=True)
        settlement_rows = Settlement.objects.filter(
            import_batch=obj,
            status=LedgerStatus.REVIEW_REQUIRED,
        ).values_list("raw_row_number", flat=True)
        return len(set(expense_rows) | set(settlement_rows))

    def get_counts_are_consistent(self, obj):
        return self.get_processed_rows(obj) == obj.total_rows
