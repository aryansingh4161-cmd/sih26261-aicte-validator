"""MOCK fire department that answers LATER: sends one signed webhook reply to pramaan/issuer_async.py.
  python -m tools.mock_issuer_sender                      # APP-11 fire certificate -> verified, after 3 s
  python -m tools.mock_issuer_sender --mismatch           # same, but the issuer returns a different valid-until date
  python -m tools.mock_issuer_sender --app APP-11 --delay 10 --url http://127.0.0.1:8601/webhook/issuer
Reads the pending verification from output/<app>.result.json. Simulated issuer, DEMO secret. OWNER: Nishchal / Aryan."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, timedelta

from pramaan.issuer_async import sign
from pramaan.pipeline import _settings
from pramaan.util import now_iso


def build_reply(result: dict, mismatch: bool, secret: str) -> dict:
    v = next((x for x in result["verifications"] if x["method"] == "issuer_portal" and x["doc_id"].endswith("fire_cert")), None)
    if v is None:
        raise SystemExit(f"{result['app_id']}: no fire certificate verification in the stored result")
    doc = next(d for d in result["documents"] if d["doc_id"] == v["doc_id"])
    fv = {k: (doc["fields"].get(k) or {}).get("value") for k in ("valid_until", "institute_name")}
    if mismatch and fv["valid_until"]:
        fv["valid_until"] = (date.fromisoformat(fv["valid_until"]) - timedelta(days=400)).isoformat()   # issuer's own record differs
    body = {"doc_id": v["doc_id"], "method": "issuer_portal", "reference": v["reference"] or "",
            "status": "mismatch_detected" if mismatch else "verified", "returned": {k: x for k, x in fv.items() if x},
            "timestamp": now_iso()}
    body["signature"] = sign(body, secret)
    return body


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--app", default="APP-11"); ap.add_argument("--out", default="output"); ap.add_argument("--delay", type=float, default=3.0)
    ap.add_argument("--mismatch", action="store_true"); ap.add_argument("--url", default="http://127.0.0.1:8601/webhook/issuer")
    a = ap.parse_args()
    with open(f"{a.out}/{a.app}.result.json") as f:
        res = json.load(f)
    body = build_reply(res, a.mismatch, str(_settings().get("issuer_webhook_secret", "")))
    print(f"MOCK fire department: replying for {body['doc_id']} ({body['reference']}) with '{body['status']}' in {a.delay:g} s ...")
    time.sleep(a.delay)
    req = urllib.request.Request(a.url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(r.status, r.read().decode())
    except urllib.error.HTTPError as e:
        print(e.code, e.read().decode()); sys.exit(1)
    except urllib.error.URLError as e:
        sys.exit(f"cannot reach {a.url} ({e.reason}). Start it first: python -m pramaan.issuer_async --today 2026-10-26")
