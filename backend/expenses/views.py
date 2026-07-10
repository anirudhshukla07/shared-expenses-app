import hashlib
import csv
import json
import os
import tempfile
from collections import Counter
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import (
    Expense,
    ExpenseGroup,
    GroupMembership,
    ImportAnomaly,
    ImportBatch,
    LedgerStatus,
    Person,
    Settlement,
)
from .serializers import (
    ExpenseGroupSerializer,
    ExpenseSerializer,
    GroupMembershipSerializer,
    ImportAnomalySerializer,
    ImportBatchSerializer,
    PersonSerializer,
    SettlementSerializer,
)
from .services.balances import (
    calculate_group_balance_details,
    calculate_group_balances,
    suggest_settlements,
)
from .services.importer import ExpenseImportService, canonical_key


def _as_bool(value, default=False):
    if value is None:
        return default
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _sync_batch_report(batch):
    """Keep stored row counters aligned with current ledger decisions.

    Import counters are row counters, not anomaly counters. A single input row can
    generate several anomalies, but it must always have exactly one row status.
    """

    report = dict(batch.report_json or {})
    rows = [dict(row) for row in report.get("rows", [])]

    expense_statuses = {
        row_number: row_status
        for row_number, row_status in Expense.objects.filter(
            import_batch=batch,
            raw_row_number__isnull=False,
        ).values_list("raw_row_number", "status")
    }
    settlement_statuses = {
        row_number: row_status
        for row_number, row_status in Settlement.objects.filter(
            import_batch=batch,
            raw_row_number__isnull=False,
        ).values_list("raw_row_number", "status")
    }

    for row in rows:
        row_number = row.get("row_number")
        if row_number in expense_statuses:
            row["status"] = expense_statuses[row_number]
        elif row_number in settlement_statuses:
            row["status"] = settlement_statuses[row_number]

    counts = Counter(row.get("status") for row in rows)
    batch.posted_rows = counts[LedgerStatus.POSTED]
    batch.review_rows = counts[LedgerStatus.REVIEW_REQUIRED]
    batch.skipped_rows = counts[LedgerStatus.SKIPPED]

    report.update(
        {
            "posted_rows": batch.posted_rows,
            "review_rows": batch.review_rows,
            "skipped_rows": batch.skipped_rows,
            "processed_rows": (
                batch.posted_rows + batch.review_rows + batch.skipped_rows
            ),
            "rows": rows,
        }
    )
    batch.report_json = report
    batch.save(
        update_fields=[
            "posted_rows",
            "review_rows",
            "skipped_rows",
            "report_json",
            "updated_at",
        ]
    )


class PersonViewSet(viewsets.ModelViewSet):
    serializer_class = PersonSerializer

    def get_queryset(self):
        return Person.objects.filter(
            memberships__group__created_by=self.request.user
        ).distinct().order_by("name")

    def perform_create(self, serializer):
        name = serializer.validated_data["name"]
        serializer.save(canonical_name=canonical_key(name))


class ExpenseGroupViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseGroupSerializer

    def get_queryset(self):
        return ExpenseGroup.objects.filter(created_by=self.request.user).order_by("name")

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class GroupMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = GroupMembershipSerializer

    def get_queryset(self):
        queryset = GroupMembership.objects.select_related("group", "person").filter(
            group__created_by=self.request.user
        )
        group_id = self.request.query_params.get("group")
        return queryset.filter(group_id=group_id) if group_id else queryset


class ExpenseViewSet(viewsets.ModelViewSet):
    serializer_class = ExpenseSerializer

    def get_queryset(self):
        queryset = (
            Expense.objects.select_related("group", "paid_by")
            .prefetch_related("splits__person")
            .filter(group__created_by=self.request.user)
        )
        group_id = self.request.query_params.get("group")
        return queryset.filter(group_id=group_id) if group_id else queryset


class SettlementViewSet(viewsets.ModelViewSet):
    serializer_class = SettlementSerializer

    def get_queryset(self):
        queryset = Settlement.objects.select_related("group", "paid_by", "paid_to").filter(
            group__created_by=self.request.user
        )
        group_id = self.request.query_params.get("group")
        return queryset.filter(group_id=group_id) if group_id else queryset


class ImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ImportBatchSerializer

    def get_queryset(self):
        return (
            ImportBatch.objects.prefetch_related("anomalies")
            .filter(uploaded_by=self.request.user)
            .order_by("-created_at")
        )

    @action(detail=True, methods=["get"])
    def report(self, request, pk=None):
        """Download the row-level import audit as CSV or JSON."""

        batch = self.get_object()
        # Avoid DRF's reserved ``format`` query parameter (renderer override).
        export_format = request.query_params.get("export", "csv").lower()
        row_statuses = {
            row.get("row_number"): row.get("status")
            for row in (batch.report_json or {}).get("rows", [])
        }
        anomalies_by_row = {}
        for anomaly in batch.anomalies.all():
            anomalies_by_row.setdefault(anomaly.row_number, []).append(anomaly)

        rows = []
        for row_number in sorted(set(row_statuses) | set(anomalies_by_row)):
            anomalies = anomalies_by_row.get(row_number, [])
            rows.append(
                {
                    "csv_row": row_number,
                    "detected_problem": " | ".join(a.code for a in anomalies) or "NONE",
                    "reason": " | ".join(a.message for a in anomalies) or "No anomaly detected",
                    "policy": " | ".join(a.policy for a in anomalies) or "Post valid row",
                    "chosen_action": " | ".join(a.action_taken for a in anomalies) or "Posted as supplied",
                    "review_decision": " | ".join(a.status for a in anomalies if a.requires_review) or "NOT_REQUIRED",
                    "final_status": row_statuses.get(row_number, LedgerStatus.SKIPPED),
                }
            )

        if export_format == "json":
            response = HttpResponse(
                json.dumps({"batch_id": batch.id, "rows": rows}, indent=2),
                content_type="application/json",
            )
            response["Content-Disposition"] = f'attachment; filename="import-{batch.id}-report.json"'
            return response
        if export_format != "csv":
            return Response(
                {"detail": "format must be csv or json."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="import-{batch.id}-report.csv"'
        writer = csv.DictWriter(
            response,
            fieldnames=[
                "csv_row",
                "detected_problem",
                "reason",
                "policy",
                "chosen_action",
                "review_decision",
                "final_status",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
        return response


class ImportAnomalyViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ImportAnomalySerializer

    def get_queryset(self):
        return ImportAnomaly.objects.filter(
            batch__uploaded_by=self.request.user
        ).order_by("row_number", "id")

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        anomaly = self.get_object()
        with transaction.atomic():
            ledger_obj, related = self._related_row(anomaly)
            if ledger_obj is None:
                return Response(
                    {
                        "detail": (
                            "This row was skipped because required source data is missing. "
                            "Correct the file and import it again."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            related.filter(
                requires_review=True,
                status=ImportAnomaly.ReviewStatus.PENDING,
            ).update(status=ImportAnomaly.ReviewStatus.APPROVED)

            has_rejection = related.filter(
                requires_review=True,
                status=ImportAnomaly.ReviewStatus.REJECTED,
            ).exists()
            if not has_rejection:
                ledger_obj.status = LedgerStatus.POSTED
                ledger_obj.save(update_fields=["status", "updated_at"])

            _sync_batch_report(anomaly.batch)

        anomaly.refresh_from_db()
        return Response(ImportAnomalySerializer(anomaly).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        anomaly = self.get_object()
        with transaction.atomic():
            ledger_obj, related = self._related_row(anomaly)
            if ledger_obj is None:
                return Response(
                    {
                        "detail": (
                            "This row is already skipped. Correct the source file and import it again."
                        )
                    },
                    status=status.HTTP_400_BAD_REQUEST,
                )

            related.filter(requires_review=True).update(
                status=ImportAnomaly.ReviewStatus.REJECTED
            )
            ledger_obj.status = LedgerStatus.SKIPPED
            ledger_obj.save(update_fields=["status", "updated_at"])
            _sync_batch_report(anomaly.batch)

        anomaly.refresh_from_db()
        return Response(ImportAnomalySerializer(anomaly).data)

    @staticmethod
    def _related_row(anomaly):
        if anomaly.expense_id:
            return anomaly.expense, ImportAnomaly.objects.filter(expense=anomaly.expense)
        if anomaly.settlement_id:
            return anomaly.settlement, ImportAnomaly.objects.filter(
                settlement=anomaly.settlement
            )
        return None, ImportAnomaly.objects.filter(batch=anomaly.batch, row_number=anomaly.row_number)


class ExpenseImportView(APIView):
    """Import a complete expense export for a group.

    By default, an upload replaces earlier *imported* rows for that group. This is
    appropriate for the assignment, where the spreadsheet is a full ledger export,
    and prevents repeated clicks from multiplying balances. Manually-created ledger
    rows (those without an import batch) are preserved.

    Send ``replace_existing=false`` to use append mode. In append mode, uploading
    the exact same file returns the previous batch instead of creating a duplicate.
    """

    def post(self, request, group_id):
        group = get_object_or_404(
            ExpenseGroup,
            id=group_id,
            created_by=request.user,
        )
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response(
                {"detail": "Upload a file field named 'file'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        suffix = os.path.splitext(uploaded.name)[1].lower()
        if suffix not in {".csv", ".xlsx", ".xlsm"}:
            return Response(
                {"detail": "Only CSV and XLSX files are supported."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            usd_rate = Decimal(str(request.data.get("usd_inr_rate", "83.00")))
            if usd_rate <= 0:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            return Response(
                {"detail": "usd_inr_rate must be a positive number."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        replace_existing = _as_bool(
            request.data.get("replace_existing"),
            default=True,
        )

        hasher = hashlib.sha256()
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                for chunk in uploaded.chunks():
                    hasher.update(chunk)
                    tmp.write(chunk)
                tmp_path = tmp.name

            source_sha256 = hasher.hexdigest()

            if not replace_existing:
                previous = self._find_same_file(group, source_sha256)
                if previous:
                    payload = dict(ImportBatchSerializer(previous).data)
                    payload["already_imported"] = True
                    return Response(payload, status=status.HTTP_200_OK)

            fx_rates = {"INR": Decimal("1.00"), "USD": usd_rate}

            with transaction.atomic():
                if replace_existing:
                    self._delete_previous_imported_ledger(group)

                batch = ImportBatch.objects.create(
                    group=group,
                    uploaded_by=request.user,
                    source_filename=uploaded.name,
                )
                service = ExpenseImportService(
                    group=group,
                    batch=batch,
                    file_path=tmp_path,
                    fx_rates=fx_rates,
                    source_sha256=source_sha256,
                    import_mode="replace" if replace_existing else "append",
                )
                batch = service.run()

            payload = dict(ImportBatchSerializer(batch).data)
            payload["already_imported"] = False
            return Response(payload, status=status.HTTP_201_CREATED)
        finally:
            if tmp_path:
                try:
                    os.unlink(tmp_path)
                except FileNotFoundError:
                    pass

    @staticmethod
    def _find_same_file(group, source_sha256):
        candidates = ImportBatch.objects.filter(
            group=group,
            status=ImportBatch.Status.COMPLETED,
        ).order_by("-created_at")
        for batch in candidates:
            if (batch.report_json or {}).get("source_sha256") == source_sha256:
                return batch
        return None

    @staticmethod
    def _delete_previous_imported_ledger(group):
        previous_batches = ImportBatch.objects.filter(group=group)
        Expense.objects.filter(group=group, import_batch__in=previous_batches).delete()
        Settlement.objects.filter(group=group, import_batch__in=previous_batches).delete()
        previous_batches.delete()

        # The importer may create one-day guest memberships (for example Kabir).
        # Remove only those generated one-day rows so replacing an import produces
        # exactly the same result every time. Seeded/normal membership windows are
        # preserved because their start and end dates differ (or end is null).
        one_day_guests = GroupMembership.objects.filter(
            group=group,
            role="guest",
            ends_on__isnull=False,
        )
        for membership in one_day_guests:
            if membership.starts_on == membership.ends_on:
                membership.delete()


class BalanceSummaryView(APIView):
    def get(self, request, group_id):
        group = get_object_or_404(
            ExpenseGroup,
            id=group_id,
            created_by=request.user,
        )
        balances = calculate_group_balances(group)
        breakdown = calculate_group_balance_details(group)
        suggestions = suggest_settlements(balances)
        return Response(
            {
                "group_id": group.id,
                "group_name": group.name,
                "balances": {name: str(amount) for name, amount in balances.items()},
                "breakdown": breakdown,
                "settlement_suggestions": suggestions,
            }
        )
