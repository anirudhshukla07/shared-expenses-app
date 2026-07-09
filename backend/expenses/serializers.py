from rest_framework import serializers
from .models import (
    Expense,
    ExpenseGroup,
    ExpenseSplit,
    GroupMembership,
    ImportAnomaly,
    ImportBatch,
    Person,
    Settlement,
)


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
    person_name = serializers.CharField(source="person.name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = GroupMembership
        fields = ["id", "group", "group_name", "person", "person_name", "starts_on", "ends_on", "role"]


class ExpenseSplitSerializer(serializers.ModelSerializer):
    person_name = serializers.CharField(source="person.name", read_only=True)

    class Meta:
        model = ExpenseSplit
        fields = ["id", "person", "person_name", "amount_owed_inr", "basis"]


class ExpenseSerializer(serializers.ModelSerializer):
    paid_by_name = serializers.CharField(source="paid_by.name", read_only=True)
    splits = ExpenseSplitSerializer(many=True, read_only=True)

    class Meta:
        model = Expense
        fields = [
            "id", "group", "import_batch", "raw_row_number", "date", "description",
            "paid_by", "paid_by_name", "amount_original", "currency", "fx_rate_to_inr",
            "amount_inr", "split_type", "split_with_raw", "split_details_raw", "notes",
            "status", "splits",
        ]


class SettlementSerializer(serializers.ModelSerializer):
    paid_by_name = serializers.CharField(source="paid_by.name", read_only=True)
    paid_to_name = serializers.CharField(source="paid_to.name", read_only=True)

    class Meta:
        model = Settlement
        fields = [
            "id", "group", "import_batch", "raw_row_number", "date", "paid_by", "paid_by_name",
            "paid_to", "paid_to_name", "amount_original", "currency", "fx_rate_to_inr",
            "amount_inr", "notes", "status",
        ]


class ImportAnomalySerializer(serializers.ModelSerializer):
    class Meta:
        model = ImportAnomaly
        fields = [
            "id", "batch", "row_number", "code", "severity", "message", "policy",
            "action_taken", "requires_review", "status", "expense", "settlement", "suggested_payload",
            "created_at",
        ]


class ImportBatchSerializer(serializers.ModelSerializer):
    anomalies = ImportAnomalySerializer(many=True, read_only=True)

    class Meta:
        model = ImportBatch
        fields = [
            "id", "group", "uploaded_by", "source_filename", "status", "total_rows", "posted_rows",
            "review_rows", "skipped_rows", "report_json", "anomalies", "created_at", "updated_at",
        ]
        read_only_fields = ["uploaded_by", "status", "report_json", "created_at", "updated_at"]
