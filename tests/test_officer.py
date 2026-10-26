"""WK23 officer-platform tests, one function per feature (no pytest). Runs the real pipeline on the synthetic demo apps
(python -m pramaan.synth.bundles first) in one temporary folder, in order, so cross-application checks see earlier apps.
  python -m tests.test_officer            -> all
  python -m tests.test_officer lod seal   -> only those"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback
from datetime import date

TODAY = date(2026, 10, 26)
TMP = tempfile.mkdtemp()
DB, REUSE = os.path.join(TMP, "audit.db"), os.path.join(TMP, "reuse.db")
_RES: dict = {}


def results(*app_ids):
    """Pipeline results for these demo apps; every app up to the highest one asked is run once, in order."""
    from pramaan.pipeline import run_application
    last = max(int(a.split("-")[1]) for a in app_ids)
    for k in range(1, last + 1):
        a = f"APP-{k:02d}"
        if a not in _RES:
            _RES[a] = run_application(f"data/demo/apps/{a}.json", TMP, TODAY, DB, reuse_db=REUSE)
    return [_RES[a] for a in app_ids]


def t_lod():
    from pramaan.letters import build_lod, export_docx, save_final
    from pramaan.audit import AuditLog
    (r2, r1, r9) = results("APP-02", "APP-01", "APP-09")
    lod = build_lod(r2, today=TODAY)
    assert [d["rule_id"] for d in lod["deficiencies"]] == ["R-MISS-fire_cert"], lod["deficiencies"]
    assert "ANNEXURE-2 2.1 v." in lod["text"] and "1. Fire Safety Certificate missing" in lod["text"], lod["text"]
    assert "To be reviewed and signed by the competent officer." in lod["text"]
    assert "No deficiencies were found" in build_lod(r1)["text"]                         # review focus 1
    lod9 = build_lod(r9)                                                                # human_review only -> annex, not letter
    assert not lod9["deficiencies"] and lod9["notes"] and not any(n["rule_id"] in lod9["text"] for n in lod9["notes"])
    assert export_docx(lod["text"], os.path.join(TMP, "lod.docx")) and os.path.getsize(os.path.join(TMP, "lod.docx")) > 1000
    with AuditLog(DB) as log:
        h = save_final(log, {"id": "officer.demo", "role": "scrutiny_officer"}, "APP-02", lod["text"] + "\nEdited by officer.")
        row = [x for x in log.rows("APP-02") if x["action"] == "letter of deficiency finalised"][-1]
    assert row["hash"] == h and "Edited by officer." in row["detail"], row


def t_resubmit():
    from pramaan.resubmit import compare
    r2, r19 = results("APP-02", "APP-19")
    d = compare(r2, r19)
    assert d["summary"] == "1 of 1 deficiencies resolved; 0 still open; 1 new", d["summary"]
    assert {x["rule_id"]: x["status"] for x in d["deficiencies"]} == {"R-MISS-fire_cert": "resolved", "R-FLD-affidavit_2-stamp_value": "new"}
    st = {x["slot"]: x["status"] for x in d["documents"]}
    assert st["fire_cert"] == "added" and st["affidavit_2"] == "replaced", st
    assert all(x["status"] != "unchanged" for x in d["changed_documents"])
    assert compare(r19, r19)["summary"] == "0 of 1 deficiencies resolved; 1 still open; 0 new"      # still-open path
    assert compare(None, r19)["summary"] == "0 of 0 deficiencies resolved; 0 still open; 1 new"     # review focus 2


def t_checklist():
    from pramaan.checklist import counts, tick
    r1, r2 = results("APP-01", "APP-02")
    rows1 = tick(r1)
    assert {r["status"] for r in rows1} == {"green", "grey"} and counts(rows1) == "11 green, 0 amber, 0 red, 3 grey", counts(rows1)
    rows2 = {r["id"]: r for r in tick(r2)}
    assert rows2["R05"]["status"] == "red" and rows2["R05"]["finding_ids"], rows2["R05"]
    assert sum(r["status"] == "red" for r in rows2.values()) == 1, counts(list(rows2.values()))
    assert all(r["evidence"] for r in rows1 if r["status"] == "green" and r["id"] in ("R01", "R05")), "green ticks link to the document"


def t_queue():
    from pramaan.audit import AuditLog
    from pramaan.queue import SpotCheckIncomplete, approve_batch, batch_seed, clear_queue, spot_sample
    rs = results(*[f"APP-{k:02d}" for k in range(1, 22)])
    q = clear_queue(rs)
    assert {"APP-01", "APP-11", "APP-21"} <= {r.app_id for r in q} and all(r.lane == "clear" for r in q), [r.app_id for r in q]
    assert not {"APP-02", "APP-09", "APP-12"} & {r.app_id for r in q}
    q = [r for r in q if r.app_id in ("APP-01", "APP-11", "APP-21")]              # the three apps clear by design
    seed = batch_seed([r.app_id for r in q], "2026-10-26")
    s1 = spot_sample([r.app_id for r in q], seed)
    assert len(s1) == 1 and s1 == spot_sample([r.app_id for r in q], seed)            # max(1, 10%), repeatable
    assert len(spot_sample([f"A{i}" for i in range(25)], "x")) == 3                    # ceil(10% of 25)
    assert spot_sample(["APP-01"], "y") == ["APP-01"]                                  # review focus 3
    user = {"id": "officer.demo", "role": "scrutiny_officer"}
    with AuditLog(DB) as log:
        try:
            approve_batch(log, user, q, set(), seed); raise AssertionError("approved without the spot check")
        except SpotCheckIncomplete:
            pass
        hs = approve_batch(log, user, q, set(s1), seed)
        rows = [x for x in log.rows() if x["hash"] in hs]
    assert len(rows) == 3 and all("auto-cleared, spot-checked 1 of 3" in x["detail"] and x["actor"] == "officer.demo" for x in rows)


def t_trust():
    from pramaan.trust import LABEL, app_score, doc_score
    r1, r16 = results("APP-01", "APP-16")
    clean, _ = doc_score(r1, "APP-01-fire_cert")
    edited, why = doc_score(r16, "APP-16-fire_cert")
    assert clean > edited and any(f.severity == "high" and f.source == "pdf_forensics" for f in r16.findings), (clean, edited)
    assert len(why) <= 3 and all("(-" in w for w in why), why
    a16 = app_score(r16)
    assert a16["score"] == min(s for s, _ in a16["documents"].values()) and a16["label"] == LABEL
    assert app_score(r1)["score"] >= 90 and 0 <= a16["score"] <= 100


TESTS = {"lod": t_lod, "resubmit": t_resubmit, "checklist": t_checklist, "queue": t_queue, "trust": t_trust}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    failed = 0
    for name in want:
        try:
            TESTS[name](); print(f"PASS {name}")
        except Exception:
            failed += 1; print(f"FAIL {name}"); traceback.print_exc(limit=3)
    print("ALL TESTS PASSED" if not failed else f"{failed} FAILED")
    sys.exit(1 if failed else 0)
