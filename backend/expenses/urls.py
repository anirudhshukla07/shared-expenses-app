from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    BalanceSummaryView,
    ExpenseGroupViewSet,
    ExpenseImportView,
    ExpenseViewSet,
    GroupMembershipViewSet,
    ImportAnomalyViewSet,
    ImportBatchViewSet,
    PersonViewSet,
    SettlementViewSet,
)

router = DefaultRouter()
router.register("people", PersonViewSet, basename="people")
router.register("groups", ExpenseGroupViewSet, basename="groups")
router.register("memberships", GroupMembershipViewSet, basename="memberships")
router.register("expenses", ExpenseViewSet, basename="expenses")
router.register("settlements", SettlementViewSet, basename="settlements")
router.register("imports", ImportBatchViewSet, basename="imports")
router.register("anomalies", ImportAnomalyViewSet, basename="anomalies")

urlpatterns = [
    path("", include(router.urls)),
    path("groups/<int:group_id>/import/", ExpenseImportView.as_view(), name="expense-import"),
    path("groups/<int:group_id>/balances/", BalanceSummaryView.as_view(), name="balance-summary"),
]
