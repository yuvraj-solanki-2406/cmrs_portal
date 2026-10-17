"""N+1 review: query count of each list endpoint at page_size=1 vs page_size=100 must be (about) equal.
Run: python manage.py shell < scripts/query_counts.py"""
from django.core.cache import cache
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.accounts.models import User

cache.clear()
ENDPOINTS = ["/customers/", "/loans/", "/collections/", "/submissions/", "/deposits/", "/audit-events/", "/users/"]
fixed = ["/dashboard/summary/", "/dashboard/branch-summary/", "/dashboard/records/?stage=COLLECTED", "/reports/mismatches/",
         "/reports/discrepancies/", "/agents/", "/submissions/pending-collections/"]
bad = 0
for username, paths in (("finance1", ENDPOINTS[:-1] + fixed[:-2]), ("admin", ["/users/"]), ("agent_mum1", ["/submissions/pending-collections/", "/collections/", "/loans/"])):
    client = APIClient(HTTP_HOST="localhost"); client.force_authenticate(User.objects.get(username=username))
    for path in paths:
        counts = []
        for size in ([1, 100] if path in ENDPOINTS else [None]):
            url = path + (("&" if "?" in path else "?") + f"page_size={size}" if size else "")
            with CaptureQueriesContext(connection) as ctx:
                resp = client.get("/api/v1" + url)
            counts.append(len(ctx))
            assert resp.status_code == 200, (url, resp.status_code)
        flat = counts[-1] <= counts[0]  # must not grow with page size (a smaller count is a paginator quirk)
        bad += not flat
        print(f"  {'OK  ' if flat else 'N+1?'} {username:10} {path:42} queries: {counts}")
print("\nno N+1 detected" if not bad else f"\n{bad} endpoint(s) scale with rows")
