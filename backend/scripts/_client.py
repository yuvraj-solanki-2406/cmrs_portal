"""Tiny HTTP helper for the verification scripts (stdlib only). Not part of the application."""
import json
import os
import time
import urllib.error
import urllib.request

BASE = os.environ.get("CMRS_API", "http://localhost:8000/api/v1")
PASSWORD = os.environ.get("CMRS_DEMO_PASSWORD", "Cmrs@12345")


def call(method, path, token=None, body=None, key=None, raw=False):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if key:
        headers["Idempotency-Key"] = key
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, method=method, data=data, headers=headers)
    try:
        resp = urllib.request.urlopen(req)
        payload = resp.read()
        return resp.status, (payload.decode() if raw else json.loads(payload or "null")), dict(resp.headers)
    except urllib.error.HTTPError as err:
        payload = err.read()
        try:
            return err.code, json.loads(payload), dict(err.headers)
        except Exception:
            return err.code, payload[:80].decode(errors="replace"), dict(err.headers)


def login(username):
    """Log in, waiting out the login throttle (429) if needed."""
    for _ in range(12):
        status, body, _ = call("POST", "/auth/login/", body={"username": username, "password": PASSWORD})
        if status == 200:
            return body["access"]
        if status == 429:
            time.sleep(10)
            continue
        raise SystemExit(f"login failed for {username}: {status} {body}")
    raise SystemExit(f"login throttled for {username}")


class Report:
    def __init__(self):
        self.passed = self.failed = 0

    def check(self, label, ok, detail=""):
        if ok:
            self.passed += 1
        else:
            self.failed += 1
        print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + str(detail)) if detail else ''}")

    def finish(self):
        print(f"\n{self.passed} passed, {self.failed} failed")
        raise SystemExit(1 if self.failed else 0)
