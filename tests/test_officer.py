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


TESTS = {"lod": t_lod}

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
