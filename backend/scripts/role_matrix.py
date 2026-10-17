"""Role x endpoint walkthrough. Every role tries every action; results must match the permission matrix.

Forbidden roles must get exactly 403. Allowed roles must get past the role gate: anything except 401/403
(requests carry deliberately invalid bodies so nothing is mutated). Unauthenticated calls must get 401.
Usage: python scripts/role_matrix.py   (server on :8000 with seeded data, ideally `seed_demo --with-activity`)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import Report, call, login  # noqa: E402

ALL = {"admin", "finance1", "manager_mum", "manager_del", "agent_mum1"}
ADMIN, FIN, MGR_ANY, AGENT = {"admin"}, {"finance1"}, {"manager_mum", "manager_del"}, {"agent_mum1"}
OVERSIGHT = ADMIN | FIN | MGR_ANY
tokens = {u: login(u) for u in sorted(ALL)}
fin = tokens["finance1"]

def first(path, key="results"):
    _, body, _ = call("GET", path, fin)
    items = body[key] if isinstance(body, dict) else body
    return items[0]["id"] if items else 1

CUST, LOAN, COLL, SUB, DEP = (first("/customers/"), first("/loans/"), first("/collections/"), first("/submissions/"), first("/deposits/"))
EP = [  # (method, path, allowed roles, body)
    ("GET", "/auth/me/", ALL, None), ("GET", "/users/", ADMIN, None), ("GET", "/roles/", ADMIN, None),
    ("POST", "/users/", ADMIN, {}), ("GET", "/branches/", ALL, None), ("POST", "/branches/", ADMIN, {}),
    ("GET", "/agents/", OVERSIGHT, None),
    ("GET", "/customers/", ALL, None), ("POST", "/customers/", ADMIN | MGR_ANY, {}),
    ("PATCH", f"/customers/{CUST}/", ADMIN | MGR_ANY, {"full_name": ""}),
    ("POST", f"/customers/{CUST}/assign-agent/", ADMIN | MGR_ANY, {}),
    ("GET", "/loans/", ALL, None), ("POST", "/loans/", ADMIN | MGR_ANY, {}), ("GET", f"/loans/{LOAN}/installments/", ALL, None),
    ("GET", f"/loans/{LOAN}/repayments/", ALL, None), ("PATCH", f"/loans/{LOAN}/", set(), {"principal": "1"}),
    ("GET", "/collections/", ALL, None), ("GET", "/collections/summary/", ALL, None),
    ("POST", "/collections/", AGENT, {}), ("POST", f"/collections/{COLL}/void/", MGR_ANY, {"reason": ""}),
    ("GET", "/submissions/", ALL, None), ("GET", "/submissions/pending-collections/", AGENT, None),
    ("POST", "/submissions/", AGENT, {}), ("POST", f"/submissions/{SUB}/approve/", MGR_ANY, {}),
    ("POST", f"/submissions/{SUB}/reject/", MGR_ANY, {}), ("PATCH", f"/submissions/{SUB}/", set(), {"status": "APPROVED"}),
    ("DELETE", f"/submissions/{SUB}/", set(), None),
    ("GET", "/deposits/", OVERSIGHT, None), ("GET", "/deposits/eligible-submissions/", MGR_ANY, None),
    ("POST", "/deposits/", MGR_ANY, {}), ("POST", f"/deposits/{DEP}/settlement/confirm/", FIN, {}),
    ("POST", f"/deposits/{DEP}/settlement/fail/", FIN, {}), ("PATCH", f"/deposits/{DEP}/", set(), {"amount": "1"}),
    ("GET", "/dashboard/summary/", ALL, None), ("GET", "/dashboard/records/?stage=HELD", ALL, None),
    ("GET", "/dashboard/branch-summary/", OVERSIGHT, None), ("GET", "/reports/discrepancies/", OVERSIGHT, None),
    ("GET", "/reports/mismatches/", OVERSIGHT, None), ("GET", f"/reports/lifecycle/collection/{COLL}/", ALL, None),
    ("GET", "/export/collections.csv", ALL, None), ("GET", "/export/submissions.csv", ALL, None),
    ("GET", "/export/deposits.csv", OVERSIGHT, None), ("GET", "/reports/discrepancies.csv", OVERSIGHT, None),
    ("GET", "/reports/mismatches.csv", OVERSIGHT, None), ("GET", "/audit-events/", OVERSIGHT, None),
]
report = Report()
print(f"{'endpoint':58} " + " ".join(f"{u[:9]:>9}" for u in sorted(ALL)) + "  anon")
for method, path, allowed, body in EP:
    cells, ok = [], True
    for user in sorted(ALL):
        status, _, _ = call(method, path, tokens[user], body, key="00000000-0000-4000-8000-000000000000" if method == "POST" and "collections/" == path[-12:] else None, raw=path.endswith(".csv"))
        if method == "PATCH" and not allowed or method == "DELETE" and not allowed:
            good = status in (403, 404, 405)  # not routed: the role gate may answer first
        elif user in allowed:
            good = status not in (401, 403)
        else:
            good = status == 403
        ok &= good
        cells.append(f"{status:>8}{'' if good else '!'}" if not good else f"{status:>9}")
    anon, _, _ = call(method, path, None, body, raw=path.endswith(".csv"))
    ok &= anon == 401 if method != "PATCH" or True else True
    print(f"{method:6}{path[:51]:52} " + " ".join(cells) + f"  {anon}{'' if anon == 401 else '!'}")
    report.check(f"{method} {path}", ok)
report.finish()
