"""
End-to-end checks of the student journey against staging, through nginx,
the way the campaign will use it. Each check prints PASS, FAIL or FINDING
(the behaviour is as the code says, and the audit records it as a problem).

Run from the api container so it reaches the proxy by name:

    docker compose --env-file .state/compose.env exec -T api \
        python staging-env/tests/journey.py

Results are also written to staging-env/.state/results/journey.json.
"""
import io
import json
import os
import re
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests
import urllib3

urllib3.disable_warnings()

API = os.environ.get("STAGING_API", "https://proxy/api/v1")
ROOT = API.rsplit("/api/", 1)[0]
FAKES = os.environ.get("STAGING_FAKES", "http://fakes:9000")
ADMIN_PASSWORD = os.environ["STAGING_ADMIN_PASSWORD"]
MERCHANT_PASSWORD = os.environ["STAGING_MERCHANT_PASSWORD"]
RESULTS = os.environ.get("RESULTS_DIR", "staging-env/.state/results")

results = []


def record(status, name, detail=""):
    results.append({"status": status, "check": name, "detail": detail})
    print(f"{status:8} {name}" + (f" — {detail}" if detail else ""), flush=True)


def check(name, ok, detail="", finding=False):
    record("PASS" if ok else ("FINDING" if finding else "FAIL"), name, detail)
    return ok


def session():
    s = requests.Session()
    s.verify = False
    return s


def jpeg(size_bytes):
    """A file with a JPEG header, padded to the given size."""
    head = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
    return io.BytesIO(head + b"\x00" * (size_bytes - len(head) - 2) + b"\xff\xd9")


def mail_to(address):
    return requests.get(f"{FAKES}/mail", params={"to": address}, timeout=10).json()


def submit_verification(s, size_mb):
    files = [("documents", (f"student-id-{size_mb}mb.jpg", jpeg(int(size_mb * 1024 * 1024)), "image/jpeg"))]
    form = {
        "personalInfo": json.dumps({"dateOfBirth": "2004-05-17", "phone": "+254712345678"}),
        "academicInfo": json.dumps({"university": "University of Nairobi", "studentId": "S123"}),
        "documentsMeta": json.dumps([{"type": "student_id", "size": int(size_mb * 1024 * 1024)}]),
    }
    started = time.monotonic()
    r = s.post(f"{API}/user/verification/student/submit", files=files, data=form, timeout=180)
    return r, time.monotonic() - started


def main():
    run = uuid.uuid4().hex[:8]
    email = f"student-{run}@staging.invalid"
    password = "Staging-pass-1"
    student = session()

    # Health and revision
    h = student.get(f"{ROOT}/healthz", timeout=10).json()
    check("API healthy behind nginx, reports its revision", h.get("status") == "ok", h.get("revision", "")[:12])

    # Sign-up, as the student site sends it (the site collects a phone too)
    r = student.post(f"{API}/auth/user/check-email", json={"email": email}, timeout=10)
    check("Email check for a new address", r.status_code == 200 and r.json().get("exists") is False, f"HTTP {r.status_code}")
    r = student.post(f"{API}/auth/user/consumer/register", timeout=10, json={
        "first_name": "Wanjiru", "last_name": f"Test{run}", "email": email,
        "password": password, "school": "University of Nairobi",
        "phone": "+254712345678", "date_of_birth": "2004-05-17",
    })
    check("Registration creates the account and signs the student in",
          r.status_code == 201 and "access_token" in student.cookies, f"HTTP {r.status_code}")
    me = student.get(f"{API}/user/me", timeout=10).json()
    user = me.get("data", me)
    student_id = user.get("id")
    check("Phone number given at sign-up is stored (F-20)", bool(user.get("phone")),
          f"stored phone: {user.get('phone')!r}", finding=True)
    check("New student is not verified", user.get("isVerified") is False, f"isVerified={user.get('isVerified')}")
    body = json.dumps(me)
    check("Profile shows no invented figures (F-07)", "1247" not in body and "4.8" not in body,
          "totalSavings 1247 / rating 4.8 present" if "1247" in body else "", finding=True)
    time.sleep(1)
    check("Welcome email sent", any("Welcome" in (m["subject"] or "") for m in mail_to(email)))

    # Entering before verification
    admin = session()
    r = admin.post(f"{API}/auth/admin/login", json={"username": "staging-admin", "password": ADMIN_PASSWORD}, timeout=10)
    check("Admin signs in", r.status_code == 200, f"HTTP {r.status_code}")
    merchants = admin.get(f"{API}/admin/users", params={"search": "shopzetu", "type": "merchants"}, timeout=10)
    found = re.search(r'"id":\s*"([^"]+)"[^{}]*?shopzetu@staging\.invalid|shopzetu@staging\.invalid[^{}]*?"id":\s*"([^"]+)"',
                      merchants.text)
    merchant_id = (found.group(1) or found.group(2)) if found else None
    if not merchant_id:
        record("FAIL", "Find the staging ShopZetu merchant", f"HTTP {merchants.status_code}: {merchants.text[:200]}")
        return

    now = datetime.now(timezone.utc)
    r = admin.post(f"{API}/admin/offers", timeout=60, json={
        "merchant_id": merchant_id, "offer_kind": "event",
        "title": f"Staging test offer {run}", "description": "Created by the staging journey test",
        "slug": f"staging-test-offer-{run}", "cover_image": "https://staging-cdn.invalid/cover.jpg",
        "event_url": "https://studentx.co.ke/festive", "coupon_limit": 1000,
        "start_date": (now - timedelta(minutes=5)).isoformat(),
        "end_date": (now + timedelta(days=3)).isoformat(),
    })
    offer_id = (r.json().get("data") or {}).get("id") if r.headers.get("content-type", "").startswith("application/json") else None
    check("Admin publishes an offer for an approved merchant", r.status_code == 201 and bool(offer_id), f"HTTP {r.status_code} {r.text[:160] if r.status_code != 201 else ''}")
    latest = student.get(f"{API}/offer/latest", timeout=10).json().get("data", [])
    check("Published offer appears in the public list", any(o.get("id") == offer_id for o in latest))

    r = student.post(f"{API}/offer/{offer_id}/coupons/create", timeout=10)
    check("Unverified student cannot enter (F-24)", r.status_code == 403, f"HTTP {r.status_code} {r.json().get('message', '')}")

    # Verification uploads, through nginx's 10 MB limit
    r, took = submit_verification(student, 4)
    check("4 MB ID photo accepted", r.status_code == 201, f"HTTP {r.status_code} in {took:.1f}s")
    request_id = (r.json().get("data") or {}).get("requestId") if r.status_code == 201 else None
    r, took = submit_verification(student, 9)
    check("9 MB ID photo accepted by the API (the site refuses over 5 MB, F-25)", r.status_code == 201, f"HTTP {r.status_code} in {took:.1f}s")
    if r.status_code == 201:
        request_id = r.json()["data"]["requestId"]
    r, took = submit_verification(student, 11)
    check("11 MB upload refused by nginx with 413", r.status_code == 413, f"HTTP {r.status_code}")

    # Admin finds the student and approves
    r = admin.get(f"{API}/admin/users", params={"search": email, "type": "students"}, timeout=10)
    check("Admin can find a student by email", r.status_code == 200 and email in r.text, f"HTTP {r.status_code}")
    r = admin.get(f"{API}/admin/users", params={"search": "@wanjiru_ig", "type": "students"}, timeout=10)
    check("Admin can find a student by Instagram handle (F-21)", r.status_code == 200 and email in r.text,
          "no handle is stored", finding=True)
    r = admin.post(f"{API}/user/verification/student/action", timeout=10,
                   json={"requestId": request_id, "action": "approve", "feedback": "Staging approval"})
    check("Admin approves the ID", r.status_code == 200, f"HTTP {r.status_code} {r.text[:120] if r.status_code != 200 else ''}")
    user = student.get(f"{API}/user/me", timeout=10).json()
    user = user.get("data", user)
    check("Student shows as verified after approval", user.get("isVerified") is True, f"isVerified={user.get('isVerified')}")

    # Entering and the entrant list
    r = student.post(f"{API}/offer/{offer_id}/coupons/create", timeout=10)
    check("Verified student can enter", r.status_code in (200, 201), f"HTTP {r.status_code} {r.text[:120] if r.status_code >= 300 else ''}")
    r = student.post(f"{API}/offer/{offer_id}/coupons/create", timeout=10)
    check("Entering twice returns the existing entry", r.status_code == 200 and r.json().get("message") == "Already registered",
          f"HTTP {r.status_code} {r.json().get('message', '')}")
    merchant = session()
    r = merchant.post(f"{API}/auth/merchant/login", json={"email": "shopzetu@staging.invalid", "password": MERCHANT_PASSWORD}, timeout=10)
    check("Merchant signs in", r.status_code == 200, f"HTTP {r.status_code}")
    r = merchant.get(f"{API}/user/merchant/coupons", timeout=10)
    check("Entrant appears once in the merchant's coupon list, with name and email",
          r.status_code == 200 and r.text.count(f'"{email}"') == 1, f"HTTP {r.status_code}, listed {r.text.count(chr(34) + email + chr(34))} time(s)")

    # Password reset signs out old sessions; links work once
    old_cookie = student.cookies.get("access_token")
    r = session().post(f"{API}/auth/user/reset-password", json={"email": email}, timeout=10)
    check("Password reset email requested", r.status_code == 200, f"HTTP {r.status_code}")
    time.sleep(1)
    links = [m for m in mail_to(email) if "token=" in (m.get("html") or "")]
    token = re.search(r"token=([^\"'&<\s]+)", links[-1]["html"]).group(1) if links else None
    check("Reset email contains a link", bool(token))
    r = session().post(f"{API}/auth/user/confirm-reset-password", params={"token": token}, json={"password": "Staging-pass-2"}, timeout=10)
    check("Reset link sets a new password", r.status_code == 200, f"HTTP {r.status_code}")
    r = session().post(f"{API}/auth/user/confirm-reset-password", params={"token": token}, json={"password": "Staging-pass-3"}, timeout=10)
    check("Reset link cannot be used twice", r.status_code == 400, f"HTTP {r.status_code}")
    stale = session()
    stale.cookies.set("access_token", old_cookie)
    r = stale.get(f"{API}/user/me", timeout=10)
    check("Session from before the reset is rejected", r.status_code == 401, f"HTTP {r.status_code}")

    # Merchant self-registration is closed
    r = session().post(f"{API}/admin/merchants/register", json={"email": f"m-{run}@staging.invalid", "name": "Anyone"}, timeout=10)
    check("Merchant registration without an admin login is refused", r.status_code == 401, f"HTTP {r.status_code}")

    # Home page route the site calls
    r = session().get(f"{API}/merchants/featured", timeout=10)
    check("Home page providers route exists (F-26)", r.status_code == 200, f"HTTP {r.status_code}", finding=True)

    # Many students behind one address (last: it uses up this address's limit)
    codes = [session().post(f"{API}/auth/user/check-email", json={"email": f"n{i}-{run}@staging.invalid"}, timeout=10).status_code
             for i in range(8)]
    refused = sum(c == 429 for c in codes)
    check("8 students on one network can all start sign-up within a minute (F-23)", refused == 0,
          f"{refused} of 8 refused with 429: {codes}", finding=True)


if __name__ == "__main__":
    try:
        main()
    finally:
        os.makedirs(RESULTS, exist_ok=True)
        with open(os.path.join(RESULTS, "journey.json"), "w") as out:
            json.dump(results, out, indent=2)
        failed = [r for r in results if r["status"] == "FAIL"]
        print(f"\n{len(results)} checks: {sum(r['status'] == 'PASS' for r in results)} pass, "
              f"{sum(r['status'] == 'FINDING' for r in results)} confirm audit findings, {len(failed)} fail")
        sys.exit(1 if failed else 0)
