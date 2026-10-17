from rest_framework.permissions import BasePermission

from apps.accounts import roles


class HasRole(BasePermission):
    """Role gate. Subclass or use `has_role(...)` to build one. Backend is the source of truth."""

    allowed_roles: tuple[str, ...] = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.is_active and user.role_code in self.allowed_roles)


def has_role(*codes: str) -> type[HasRole]:
    return type("HasRole_" + "_".join(codes), (HasRole,), {"allowed_roles": tuple(codes)})


IsAdmin = has_role(roles.ADMIN)
IsAgent = has_role(roles.AGENT)
IsBranchManager = has_role(roles.BRANCH_MANAGER)
IsFinance = has_role(roles.FINANCE)
IsAdminOrFinance = has_role(roles.ADMIN, roles.FINANCE)
