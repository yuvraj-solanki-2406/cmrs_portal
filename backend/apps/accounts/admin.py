from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Branch, Role, User

admin.site.register(Branch)
admin.site.register(Role)


@admin.register(User)
class CmrsUserAdmin(UserAdmin):
    list_display = ("username", "full_name", "role", "branch", "is_active")
    fieldsets = UserAdmin.fieldsets + (("CMRS", {"fields": ("full_name", "role", "branch")}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("CMRS", {"fields": ("full_name", "role", "branch")}),)
