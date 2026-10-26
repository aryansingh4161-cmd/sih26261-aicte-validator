"""WK26 API tests (no pytest): FastAPI TestClient over the real pipeline output of the 23 demo apps (tests/test_officer runner).
  python -m tests.test_api"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback

from tests.test_officer import TMP, results

os.environ["PRAMAAN_OUT"], os.environ["PRAMAAN_TODAY"] = TMP, "2026-10-26"
_C = None


def client():
    global _C
    if _C is None:
        results(*[f"APP-{k:02d}" for k in range(1, 24)])
        from fastapi.testclient import TestClient
        from api.main import app
        _C = TestClient(app)
    return _C


def ok(path, **kw):
    r = client().get(path, **kw)
    assert r.status_code == 200, (path, r.status_code, r.text[:300])
    return r


def t_reads():
    c = client()
    assert ok("/api/health").json()["cases"] == 23
    q = ok("/api/queue").json()
    assert q["count"] == 23 and q["items"][0]["priority"] >= q["items"][-1]["priority"] and "summary" in q
    for a in ("APP-02", "APP-07"):
        cs = ok(f"/api/cases/{a}").json()
        assert cs["app_id"] == a and cs["documents"] and cs["timeline"] and cs["lane_label"] in ("Return for rectification", "Human review", "Clear")
        assert len(ok(f"/api/cases/{a}/checklist").json()) == 14
        src = ok(f"/api/cases/{a}/sources").json()
        assert src["rows"] and any(x["demo"] for x in src["rows"]) and any(x["source"] == "Registrar of Societies" for x in src["rows"])
        pv = ok(f"/api/cases/{a}/sources/0/preview").json()
        assert pv["kv"] and pv["kv"][-1]["v"].startswith("#")
        assert ok(f"/api/cases/{a}/changes").json()["rows"]
        ok(f"/api/cases/{a}/resubmission")
        ok(f"/api/cases/{a}/notes")
        lt = ok(f"/api/cases/{a}/letter").json()
        assert "text" in lt and lt["quotes"]["label"] == "measured"
        ok(f"/api/cases/{a}/evc")
        d = cs["documents"][0]
        img = ok(d["page_urls"][0])
        assert img.headers["content-type"] == "image/png" and img.content[:4] == b"\x89PNG"
    assert ok("/api/cases/APP-19/resubmission").json()["available"]
    for p in ("/api/letters", "/api/outbox", "/api/calendar", "/api/appeals", "/api/batch", "/api/roles", "/api/docs/privacy",
              "/api/search?q=fire%20expired", "/api/cases/APP-02/zip"):
        ok(p)
    for role in ("regulation_bureau", "scrutiny", "evc", "shc", "ec", "sac"):
        an = ok(f"/api/analytics?role={role}").json()
        assert an["synthetic"] and len(an["kpis"]) == 4 and "11 of 59" not in str(an)
    assert c.get("/api/cases/APP-99").status_code == 404
    assert ok("/api/queue?role=scrutiny").json()["count"] < 23
    hi = ok("/api/cases/APP-02?lang=hi").json()
    assert any(ord(ch) > 127 for ch in hi["lane_label"]), hi["lane_label"]


def t_seal_round_trip():
    c = client()
    secret = "Internal: principal phoned about the fire NOC, check @officer.nw"
    assert c.post("/api/cases/APP-07/notes", json={"text": secret}).status_code == 200
    draft = ok("/api/cases/APP-07/letter").json()
    assert "principal phoned" not in draft["text"]
    s = c.post("/api/cases/APP-07/letter/seal", json={"include": [i["finding_id"] for i in draft["items"] if i["include"]]})
    assert s.status_code == 200, s.text
    j = s.json()
    assert j["seal"].startswith("VALID") and j["appeal"]["state"] == "open"
    sealed = ok(f"/api/letters/file/{j['file']}").text
    assert "principal phoned" not in sealed and "Internal notes" not in sealed
    assert c.post("/api/letters/verify", json={"file": j["file"]}).json()["valid"]
    p = os.path.join(TMP, "letters", j["file"])
    cli = subprocess.run([sys.executable, "-m", "tools.verify_report", p, "--audit", os.path.join(TMP, "audit.db")], capture_output=True, text=True)
    assert cli.returncode == 0 and cli.stdout.startswith("VALID"), cli.stdout
    altered = sealed.replace("Letter", "Lettre", 1)
    assert not c.post("/api/letters/verify", json={"html": altered}).json()["valid"]
    assert any(x["app_id"] == "APP-07" and x["status"] in ("sealed", "sent") for x in ok("/api/letters").json()["letters"])
    assert any(x["app_id"] == "APP-07" for x in ok("/api/appeals").json()["appeals"])


def t_actions():
    c = client()
    cs = ok("/api/cases/APP-02").json()
    fid = cs["findings"][0]["finding_id"]
    assert c.post("/api/cases/APP-02/feedback", json={"finding_id": fid, "verdict": "maybe"}).status_code == 422
    assert c.post("/api/cases/APP-02/feedback", json={"finding_id": fid, "verdict": "correct"}).status_code == 200
    assert ok("/api/cases/APP-02").json()["findings"][0]["feedback"] == "correct"
    a = c.post("/api/cases/APP-02/assign", json={"officer": "officer.nw"}).json()
    assert a["officer"] == "officer.nw" and any(e["type"] == "assigned" and e["hash"] != "-" for e in ok("/api/cases/APP-02").json()["timeline"])
    b = ok("/api/batch").json()
    assert b["files"] and len(b["spot"]) == 1
    assert c.post("/api/batch/approve", json={"opened": []}).json()["error"]
    done = c.post("/api/batch/approve", json={"opened": b["spot"]}).json()
    assert sorted(done["approved"]) == sorted(f["app_id"] for f in b["files"])
    assert any(o["kind"] == "loa_draft" for o in ok("/api/outbox").json())
    assert c.post("/api/cases/APP-07/sources/reask").status_code == 200
    assert c.post("/api/search/filters", json={"name": "fire", "query": "fire expired"}).status_code == 200
    assert any(f["name"] == "fire" for f in ok("/api/search?q=fire").json()["saved"])


TESTS = {"reads": t_reads, "seal_round_trip": t_seal_round_trip, "actions": t_actions}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    failed = 0
    for name in want:
        try:
            TESTS[name](); print(f"PASS {name}")
        except Exception:
            failed += 1; print(f"FAIL {name}"); traceback.print_exc(limit=4)
    print("ALL TESTS PASSED" if not failed else f"{failed} FAILED")
    sys.exit(1 if failed else 0)
