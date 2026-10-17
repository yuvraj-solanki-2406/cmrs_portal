from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import CashSubmission, CashSubmissionItem


class ItemInline(admin.TabularInline):
    model = CashSubmissionItem
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(CashSubmission)
class CashSubmissionAdmin(ReadOnlyAdmin):
    list_display = ("reference_no", "agent", "status", "expected_amount", "received_amount", "discrepancy_amount")
    list_filter = ("status", "branch")
    inlines = [ItemInline]
