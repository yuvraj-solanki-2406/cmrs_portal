from django.db.models import QuerySet

from apps.common.scoping import scope_queryset

from .models import Collection


def collections_for(user) -> QuerySet[Collection]:
    qs = Collection.objects.select_related("loan", "loan__customer", "agent", "branch")
    return scope_queryset(qs, user, branch_field="branch", agent_field="agent")


def is_in_active_submission(collection: Collection) -> bool:
    """True while the collection sits in a live (non-rejected) cash submission.
    Uses the `submission_items` reverse relation by name, so this app never imports `cash`."""
    return collection.submission_items.filter(is_active=True).exists()
