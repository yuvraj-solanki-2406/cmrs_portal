from django.contrib import admin

from apps.common.admin import ReadOnlyAdmin

from .models import Collection


@admin.register(Collection)
class CollectionAdmin(ReadOnlyAdmin):
    list_display = ("receipt_number", "loan", "agent", "amount", "status", "collection_date")
    list_filter = ("status", "branch")
    search_fields = ("receipt_number",)
