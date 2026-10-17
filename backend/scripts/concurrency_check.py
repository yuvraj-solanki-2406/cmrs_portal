"""Throw-away parallel-request script (not part of the app, not a test suite).
Fires competing requests at the money-moving paths and asserts the invariants hold. Creates its own data
(a large loan and a few collections) in whatever database the server uses: run against dev, then
`python manage.py reset_activity && python manage.py seed_demo --with-activity` to get a clean demo state.
Usage: python scripts/concurrency_check.py
"""
import datetime
import sys
import threading
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from _client import Report, call, login  # noqa: E402

AG, MM, FIN = login("agent_mum1"), login("manager_mum"), login("finance1")
today = datetime.date.today().isoformat()
report = Report()
counter = [0]


def race(*jobs):
    """Run the callables at the same instant; return their (status, body) results in order."""
    barrier, out = threading.Barrier(len(jobs)), [None] * len(jobs)

    def run(i, job):
        barrier.wait()
        out[i] = job()
    threads = [threading.Thread(target=run, args=(i, j)) for i, j in enumerate(jobs)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    return out


def codes(results):
    return sorted(r[0] for r in results)


def new_loan(total):
    cust = call("GET", "/customers/?search=Bhavna", MM)[1]["results"][0]["id"]
    s, loan, _ = call("POST", "/loans/", MM, {"customer": cust, "principal": str(total), "total_payable": str(total),
                                              "installment_count": 4, "frequency": "WEEKLY", "start_date": today})
    assert s == 201, loan
    return loan["id"]


BIG = new_loan(1_000_000)


def pay(amount=None, loan=None):
    counter[0] += 1
    amount = amount or 100 + counter[0]  # distinct amounts avoid the soft-duplicate guard
    s, c, _ = call("POST", "/collections/", AG, {"loan": loan or BIG, "amount": str(amount)}, str(uuid.uuid4()))
    assert s == 201, c
    return c["id"]


def submit(ids):
    s, sub, _ = call("POST", "/submissions/", AG, {"collection_ids": ids}, str(uuid.uuid4()))
    assert s == 201, sub
    return sub["id"]


def approved_submission():
    sid = submit([pay()])
    s, d, _ = call("POST", f"/submissions/{sid}/approve/", MM, {"received_amount": call("GET", f"/submissions/{sid}/", MM)[1]["expected_amount"]})
    assert s == 200, d
    return sid


def deposit(sub_ids, ref, amount=None):
    if amount is None:
        amount = str(sum(float(call("GET", f"/submissions/{i}/", MM)[1]["received_amount"]) for i in sub_ids))
    return call("POST", "/deposits/", MM, {"submission_ids": sub_ids, "bank_name": "HDFC", "amount": amount,
                                           "deposit_date": today, "reference_number": ref})[:2]


print("1. Over-collection: two ₹6,000 payments (different keys) on a ₹10,000 loan")
loan = new_loan(10_000)
res = race(*[lambda: call("POST", "/collections/", AG, {"loan": loan, "amount": "6000"}, str(uuid.uuid4()))[:2]] * 2)
out = call("GET", f"/loans/{loan}/outstanding/", MM)[1]["outstanding"]
report.check("exactly one succeeds, other OVER_COLLECTION", codes(res) == [201, 400] and any(r[1].get("code") == "OVER_COLLECTION" for r in res))
report.check("outstanding is ₹4,000.00 (never overpaid)", out == "4000.00", out)

print("2. Idempotency: same key, four parallel requests")
key = str(uuid.uuid4()); amount = 300 + counter[0]
res = race(*[lambda: call("POST", "/collections/", AG, {"loan": BIG, "amount": str(amount)}, key)[:2]] * 4)
report.check("one 201 and three 200 replays", codes(res) == [200, 200, 200, 201], codes(res))
report.check("all return the same receipt", len({r[1]["receipt_number"] for r in res}) == 1)
s, d, _ = call("POST", "/collections/", AG, {"loan": BIG, "amount": str(amount + 1)}, key)
report.check("same key, different amount -> 422", s == 422, s)

print("3. Submit race: one collection, two parallel submissions")
cid = pay()
res = race(*[lambda: call("POST", "/submissions/", AG, {"collection_ids": [cid]}, str(uuid.uuid4()))[:2]] * 2)
report.check("one 201, one 409 ALREADY_SUBMITTED", codes(res) == [201, 409] and any(r[1].get("code") == "ALREADY_SUBMITTED" for r in res), codes(res))
cid = pay(); key = str(uuid.uuid4())
res = race(*[lambda: call("POST", "/submissions/", AG, {"collection_ids": [cid]}, key)[:2]] * 3)
report.check("same-key submit x3 -> one submission", len({r[1]["id"] for r in res}) == 1 and codes(res) == [200, 200, 201], codes(res))

print("4. Void vs submit race on the same collection")
cid = pay()
res = race(lambda: call("POST", f"/collections/{cid}/void/", MM, {"reason": "race"})[:2],
           lambda: call("POST", "/submissions/", AG, {"collection_ids": [cid]}, str(uuid.uuid4()))[:2])
ok = [r[0] for r in res]
report.check("exactly one of void / submit succeeds", sum(1 for c in ok if c in (200, 201)) == 1, ok)

print("5. Reconciliation races")
sid = submit([pay()]); exp = call("GET", f"/submissions/{sid}/", MM)[1]["expected_amount"]
res = race(lambda: call("POST", f"/submissions/{sid}/approve/", MM, {"received_amount": exp})[:2],
           lambda: call("POST", f"/submissions/{sid}/approve/", MM, {"received_amount": "1.00", "discrepancy_reason": "x"})[:2])
final = call("GET", f"/submissions/{sid}/", MM)[1]
report.check("double approve: one 200, one 409", codes(res) == [200, 409], codes(res))
report.check("stored result equals the winner's", final["status"] == "APPROVED" and final["received_amount"] in (exp, "1.00"))
sid = submit([pay()]); exp = call("GET", f"/submissions/{sid}/", MM)[1]["expected_amount"]
res = race(lambda: call("POST", f"/submissions/{sid}/approve/", MM, {"received_amount": exp})[:2],
           lambda: call("POST", f"/submissions/{sid}/reject/", MM, {"reason": "race"})[:2])
report.check("approve vs reject: exactly one wins", codes(res) == [200, 409], codes(res))

print("6. Deposit races")
sid = approved_submission(); ref = f"RACE-{uuid.uuid4().hex[:8]}"
res = race(lambda: deposit([sid], ref + "-A"), lambda: deposit([sid], ref + "-B"))
report.check("two deposits, one submission: one 201, one 409", codes(res) == [201, 409] and any(r[1].get("code") == "SUBMISSION_NOT_ELIGIBLE" for r in res), codes(res))
s1, s2 = approved_submission(), approved_submission(); ref = f"RACE-{uuid.uuid4().hex[:8]}"
res = race(lambda: deposit([s1], ref), lambda: deposit([s2], ref.lower()))
report.check("same bank reference (case variant): one 201, one DUPLICATE_BANK_REFERENCE", codes(res) == [201, 409] and any(r[1].get("code") == "DUPLICATE_BANK_REFERENCE" for r in res), codes(res))
left = s2 if res[0][0] == 201 else s1
report.check("losing submission stays deposit-free (rolled back)", call("GET", "/deposits/eligible-submissions/", MM)[1] and left in [e["id"] for e in call("GET", "/deposits/eligible-submissions/", MM)[1]])

print("7. Settlement races")
def fresh_deposit():
    sid = approved_submission(); s, d = deposit([sid], f"RACE-{uuid.uuid4().hex[:8]}"); assert s == 201, d
    return d["id"], d["amount"]
did, amt = fresh_deposit()
res = race(lambda: call("POST", f"/deposits/{did}/settlement/confirm/", FIN, {"settled_amount": amt, "settled_on": today})[:2],
           lambda: call("POST", f"/deposits/{did}/settlement/confirm/", FIN, {"settled_amount": amt, "settled_on": today})[:2])
report.check("double confirm: one 200, one 409", codes(res) == [200, 409], codes(res))
did, amt = fresh_deposit()
res = race(lambda: call("POST", f"/deposits/{did}/settlement/confirm/", FIN, {"settled_amount": amt, "settled_on": today})[:2],
           lambda: call("POST", f"/deposits/{did}/settlement/fail/", FIN, {"reason": "race"})[:2])
final = call("GET", f"/deposits/{did}/", FIN)[1]["settlement"]["status"]
report.check("confirm vs fail: consistent final state", final in ("SETTLED", "FAILED") and (codes(res) == [200, 409] or (final == "SETTLED" and codes(res) == [200, 200])), (codes(res), final))

print("8. Invariants after the storm (SQL)")
import subprocess
sql = """select 'overpaid', count(*) from (select l.id from loans l join collections c on c.loan_id=l.id and c.status='VALID' group by l.id,l.total_payable having sum(c.amount)>l.total_payable) x
union all select 'double_live_item', count(*) from (select collection_id from cash_submission_items where is_active group by 1 having count(*)>1) y
union all select 'expected_ne_items', count(*) from cash_submissions s where s.status in ('SUBMITTED','APPROVED') and s.expected_amount <> (select coalesce(sum(amount),0) from cash_submission_items i where i.submission_id=s.id and i.is_active)
union all select 'deposit_ne_sum', count(*) from bank_deposits d where d.reconciled_amount <> (select coalesce(sum(received_amount),0) from cash_submissions s where s.deposit_id=d.id)
union all select 'deposit_wo_one_settlement', count(*) from bank_deposits d where (select count(*) from settlements s where s.deposit_id=d.id) <> 1
union all select 'dup_bank_ref', count(*) from (select upper(trim(reference_number)) from bank_deposits group by 1 having count(*)>1) z;"""
try:
    r = subprocess.run(["docker", "compose", "-f", str(Path(__file__).parents[2] / "docker-compose.yml"), "exec", "-T", "db",
                        "psql", "-U", "cmrs", "-d", "cmrs", "-At", "-c", sql], capture_output=True, text=True, timeout=60)
    rows = [line.split("|") for line in r.stdout.strip().splitlines()]
    report.check("all invariant queries return 0", rows and all(c == "0" for _, c in rows), rows)
except Exception as exc:  # docker not available: skip rather than fail
    print("  SKIP  invariants (docker/psql unavailable):", exc)
report.finish()
