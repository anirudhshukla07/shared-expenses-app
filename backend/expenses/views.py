import tempfile
from decimal import Decimal

from django.db import transaction
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
from .services.balances import calculate_group_balances, suggest_settlements
from .services.importer import ExpenseImportService, canonical_key


class PersonViewSet(viewsets.ModelViewSet):
    queryset = Person.objects.all().order_by("name")
    serializer_class = PersonSerializer

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
    queryset = GroupMembership.objects.select_related("group", "person").all()
    serializer_class = GroupMembershipSerializer


class ExpenseViewSet(viewsets.ModelViewSet):
    queryset = Expense.objects.select_related("group", "paid_by").prefetch_related("splits").all()
    serializer_class = ExpenseSerializer


class SettlementViewSet(viewsets.ModelViewSet):
    queryset = Settlement.objects.select_related("group", "paid_by", "paid_to").all()
    serializer_class = SettlementSerializer


class ImportBatchViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ImportBatch.objects.prefetch_related("anomalies").all().order_by("-created_at")
    serializer_class = ImportBatchSerializer


class ImportAnomalyViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = ImportAnomaly.objects.all().order_by("row_number", "id")
    serializer_class = ImportAnomalySerializer

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        anomaly = self.get_object()
        anomaly.status = ImportAnomaly.ReviewStatus.APPROVED
        anomaly.save(update_fields=["status", "updated_at"])
        self._maybe_post_related_ledger_row(anomaly)
        return Response(ImportAnomalySerializer(anomaly).data)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        anomaly = self.get_object()
        anomaly.status = ImportAnomaly.ReviewStatus.REJECTED
        anomaly.save(update_fields=["status", "updated_at"])
        if anomaly.expense:
            anomaly.expense.status = LedgerStatus.SKIPPED
            anomaly.expense.save(update_fields=["status", "updated_at"])
        if anomaly.settlement:
            anomaly.settlement.status = LedgerStatus.SKIPPED
            anomaly.settlement.save(update_fields=["status", "updated_at"])
        return Response(ImportAnomalySerializer(anomaly).data)

    def _maybe_post_related_ledger_row(self, anomaly):
        related_filter = {}
        ledger_obj = None
        if anomaly.expense_id:
            related_filter["expense"] = anomaly.expense
            ledger_obj = anomaly.expense
        elif anomaly.settlement_id:
            related_filter["settlement"] = anomaly.settlement
            ledger_obj = anomaly.settlement
        if not ledger_obj:
            return
        pending_count = ImportAnomaly.objects.filter(
            requires_review=True,
            status=ImportAnomaly.ReviewStatus.PENDING,
            **related_filter,
        ).count()
        rejected_count = ImportAnomaly.objects.filter(
            requires_review=True,
            status=ImportAnomaly.ReviewStatus.REJECTED,
            **related_filter,
        ).count()
        if pending_count == 0 and rejected_count == 0:
            ledger_obj.status = LedgerStatus.POSTED
            ledger_obj.save(update_fields=["status", "updated_at"])


class ExpenseImportView(APIView):
    def post(self, request, group_id):
        group = get_object_or_404(ExpenseGroup, id=group_id, created_by=request.user)
        uploaded = request.FILES.get("file")
        if not uploaded:
            return Response({"detail": "Upload a file field named 'file'."}, status=status.HTTP_400_BAD_REQUEST)
        suffix = "." + uploaded.name.split(".")[-1].lower()
        if suffix not in {".csv", ".xlsx", ".xlsm"}:
            return Response({"detail": "Only CSV and XLSX files are supported."}, status=status.HTTP_400_BAD_REQUEST)

        fx_rates = {"INR": Decimal("1.00")}
        fx_rates["USD"] = Decimal(str(request.data.get("usd_inr_rate", "83.00")))

        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            for chunk in uploaded.chunks():
                tmp.write(chunk)
            tmp_path = tmp.name

        batch = ImportBatch.objects.create(group=group, uploaded_by=request.user, source_filename=uploaded.name)
        service = ExpenseImportService(group=group, batch=batch, file_path=tmp_path, fx_rates=fx_rates)
        batch = service.run()
        return Response(ImportBatchSerializer(batch).data, status=status.HTTP_201_CREATED)


class BalanceSummaryView(APIView):
    def get(self, request, group_id):
        group = get_object_or_404(ExpenseGroup, id=group_id, created_by=request.user)
        balances = calculate_group_balances(group)
        suggestions = suggest_settlements(balances)
        return Response({
            "group_id": group.id,
            "group_name": group.name,
            "balances": {name: str(amount) for name, amount in balances.items()},
            "settlement_suggestions": suggestions,
        })
