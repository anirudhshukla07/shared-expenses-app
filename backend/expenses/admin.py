from django.contrib import admin
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

admin.site.register(Person)
admin.site.register(ExpenseGroup)
admin.site.register(GroupMembership)
admin.site.register(ImportBatch)
admin.site.register(Expense)
admin.site.register(ExpenseSplit)
admin.site.register(Settlement)
admin.site.register(ImportAnomaly)
