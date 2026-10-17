from django.contrib import admin


class ReadOnlyAdmin(admin.ModelAdmin):
    """Financial records are written only by the service layer; the admin is a viewer."""

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
