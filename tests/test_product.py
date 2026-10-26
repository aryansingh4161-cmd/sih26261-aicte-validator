"""WK25 product back-end tests, one function per item (no pytest). Reuses the officer-test pipeline run (tests/test_officer.py:
same temporary folder, audit DB and outbox).  python -m tests.test_product [name ...]"""
from __future__ import annotations

import os
import subprocess
import sys
import traceback

from tests.test_officer import DB, TMP, TODAY, results


def t_case_timeline():
    from pramaan.audit import AuditLog
    from pramaan.case_timeline import build_timeline, case_summary
    from pramaan.letters import build_lod, save_final
    r2, _ = results("APP-02", "APP-19")
    with AuditLog(DB) as log:
        save_final(log, {"id": "officer.demo", "role": "scrutiny_officer"}, "APP-02", build_lod(r2)["text"])
        hashes = {r["hash"][:12] for r in log.rows()}
    tl = build_timeline("APP-02", TMP, DB, today=TODAY)
    types = [e["type"] for e in tl]
    assert types.index("letter issued") > types.index("auto-checked") > types.index("submitted"), types
    assert "resubmitted" in types and any("APP-19" in e["refs"] for e in tl if e["type"] == "resubmitted"), tl
    assert [e["ts"] for e in tl] == sorted(e["ts"] for e in tl)
    assert all(e["hash"] in hashes for e in tl if e["hash"] != "-"), "every hash is an audit row"
    assert "R-MISS-fire_cert" in " ".join(next(e for e in tl if e["type"] == "letter issued")["refs"])
    t1 = [e["type"] for e in build_timeline("APP-01", TMP, DB, today=TODAY)]                 # review focus 1: nothing invented
    assert "letter issued" not in t1 and "appeal window" not in t1 and "decision" not in t1, t1
    s = case_summary("APP-02", TMP, DB, today=TODAY)
    assert s["open_deficiencies"] == ["Fire Safety Certificate missing"] and s["appeal"]["state"] == "open" and s["trust_score"] <= 100
    cli = subprocess.run([sys.executable, "-m", "pramaan.case_timeline", "APP-02", "--out", TMP, "--today", str(TODAY)],
                         capture_output=True, text=True)
    assert cli.returncode == 0 and "letter issued" in cli.stdout, cli.stderr[-300:]


TESTS = {"case_timeline": t_case_timeline}

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
