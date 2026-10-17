"""Queryset scoping by role. Every list/detail view must pass its queryset through here.

- ADMIN / FINANCE: all rows
- BRANCH_MANAGER: rows of their branch
- AGENT: rows belonging to them (`agent_field`), else none
Out-of-scope objects are simply absent, so detail lookups return 404 (no enumeration).
"""
from apps.accounts import roles


def scope_queryset(queryset, user, *, branch_field: str | None = "branch", agent_field: str | None = None):
    code = getattr(user, "role_code", None)  # anonymous users (e.g. schema generation) see nothing
    if code in (roles.ADMIN, roles.FINANCE):
        return queryset
    if code == roles.BRANCH_MANAGER and branch_field:
        return queryset.filter(**{branch_field: user.branch_id})
    if code == roles.AGENT and agent_field:
        return queryset.filter(**{agent_field: user.pk})
    return queryset.none()


class ScopedQuerysetMixin:
    """For DRF views: set `branch_field` / `agent_field`; get_queryset() is scoped automatically."""

    branch_field: str | None = "branch"
    agent_field: str | None = None

    def get_queryset(self):
        return scope_queryset(
            super().get_queryset(), self.request.user, branch_field=self.branch_field, agent_field=self.agent_field
        )
