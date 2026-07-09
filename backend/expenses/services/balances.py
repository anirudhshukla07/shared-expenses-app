from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP

from expenses.models import Expense, LedgerStatus, Settlement

PAISE = Decimal("0.01")


def q(amount: Decimal) -> Decimal:
    return Decimal(amount).quantize(PAISE, rounding=ROUND_HALF_UP)


def calculate_group_balances(group):
    balances = defaultdict(lambda: Decimal("0.00"))

    expenses = (
        Expense.objects.filter(group=group, status=LedgerStatus.POSTED)
        .select_related("paid_by")
        .prefetch_related("splits__person")
    )
    for expense in expenses:
        balances[expense.paid_by.name] += Decimal(expense.amount_inr)
        for split in expense.splits.all():
            balances[split.person.name] -= Decimal(split.amount_owed_inr)

    settlements = Settlement.objects.filter(group=group, status=LedgerStatus.POSTED).select_related("paid_by", "paid_to")
    for settlement in settlements:
        balances[settlement.paid_by.name] += Decimal(settlement.amount_inr)
        balances[settlement.paid_to.name] -= Decimal(settlement.amount_inr)

    return {name: q(amount) for name, amount in sorted(balances.items())}


def suggest_settlements(balances):
    debtors = []
    creditors = []
    for name, amount in balances.items():
        amount = q(Decimal(amount))
        if amount < 0:
            debtors.append([name, -amount])
        elif amount > 0:
            creditors.append([name, amount])

    debtors.sort(key=lambda x: x[1], reverse=True)
    creditors.sort(key=lambda x: x[1], reverse=True)

    suggestions = []
    i = j = 0
    while i < len(debtors) and j < len(creditors):
        debtor_name, debt = debtors[i]
        creditor_name, credit = creditors[j]
        pay = q(min(debt, credit))
        if pay > 0:
            suggestions.append({"from": debtor_name, "to": creditor_name, "amount_inr": str(pay)})
        debtors[i][1] = q(debt - pay)
        creditors[j][1] = q(credit - pay)
        if debtors[i][1] == 0:
            i += 1
        if creditors[j][1] == 0:
            j += 1
    return suggestions
