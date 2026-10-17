from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import Customer, Installment, Loan


@admin.register(Customer)
class CustomerAdmin(ReadOnlyAdmin):
    list_display = ("customer_code", "full_name", "branch", "assigned_agent", "is_active")
    search_fields = ("customer_code", "full_name", "phone")


@admin.register(Loan)
class LoanAdmin(ReadOnlyAdmin):
    list_display = ("loan_number", "customer", "principal", "total_payable", "status")
    search_fields = ("loan_number",)


@admin.register(Installment)
class InstallmentAdmin(ReadOnlyAdmin):
    list_display = ("loan", "installment_no", "due_date", "amount_due")
