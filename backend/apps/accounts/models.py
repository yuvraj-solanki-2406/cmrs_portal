from django.contrib.auth.models import AbstractUser
from django.db import models


class Branch(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=120)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "branches"
        ordering = ["code"]

    def __str__(self):
        return f"{self.code} - {self.name}"


class Role(models.Model):
    code = models.CharField(max_length=30, unique=True)
    name = models.CharField(max_length=60)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = "roles"
        ordering = ["id"]

    def __str__(self):
        return self.code


class User(AbstractUser):
    full_name = models.CharField(max_length=150, blank=True)
    role = models.ForeignKey(Role, on_delete=models.PROTECT, related_name="users")
    # Null only for FINANCE / ADMIN; branch-bound roles are validated in apps.accounts.services.
    branch = models.ForeignKey(Branch, on_delete=models.PROTECT, null=True, blank=True, related_name="users")

    class Meta:
        db_table = "users"
        indexes = [models.Index(fields=["branch", "role"], name="users_branch_role_idx")]

    @property
    def role_code(self) -> str:
        return self.role.code

    def __str__(self):
        return self.username
