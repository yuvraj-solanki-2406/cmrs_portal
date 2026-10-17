from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import BankDeposit, Settlement


@admin.register(BankDeposit)
class BankDepositAdmin(ReadOnlyAdmin):
    list_display = ("deposit_no", "branch", "bank_name", "amount", "reconciled_amount", "variance_amount", "deposit_date")
    search_fields = ("deposit_no", "reference_number")


@admin.register(Settlement)
class SettlementAdmin(ReadOnlyAdmin):
    list_display = ("deposit", "status", "settled_amount", "variance_amount", "settled_on")
    list_filter = ("status",)
