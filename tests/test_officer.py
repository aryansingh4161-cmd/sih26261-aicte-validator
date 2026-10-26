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


def t_seal():
    import subprocess
    from pramaan.audit import AuditLog
    from pramaan.letters import build_lod
    from pramaan.seal import seal_html, verify_sealed
    results("APP-02")
    path = os.path.join(TMP, "APP-02.report.html")
    text = open(path, encoding="utf-8").read()
    assert verify_sealed(text, DB).startswith("VALID: matches audit entry #"), verify_sealed(text, DB)
    i = text.index("<body") + 10
    changed = text[:i] + ("X" if text[i] != "X" else "Y") + text[i + 1:]                 # one byte changed
    assert verify_sealed(changed, DB) == "ALTERED: content does not match its seal"
    with AuditLog(DB) as log:                                                           # an LoD is sealed the same way
        lod = seal_html(build_lod(results("APP-02")[0])["html"], "APP-02", log, kind="letter of deficiency")
    assert verify_sealed(lod, DB).startswith("VALID") and "data:image/png;base64," in lod
    other = os.path.join(TMP, "other_audit.db")                                         # review focus 4: no matching entry
    with AuditLog(other) as log:
        foreign = seal_html("<p>x</p>", "APP-02", log)
    assert verify_sealed(foreign, DB) == "ALTERED: no matching audit entry"
    assert verify_sealed("<p>no seal</p>", DB) == "ALTERED: no seal found"
    open(os.path.join(TMP, "changed.html"), "w", encoding="utf-8").write(changed)
    cli = subprocess.run([sys.executable, "-m", "tools.verify_report", os.path.join(TMP, "changed.html"), "--audit", DB],
                         capture_output=True, text=True)
    assert cli.returncode == 1 and cli.stdout.startswith("ALTERED"), cli.stdout


def _page(path, **state):
    """Run a dashboard page headless (streamlit AppTest) on this test's output folder; returns the AppTest."""
    from streamlit.testing.v1 import AppTest
    os.environ["PRAMAAN_OUT"] = TMP
    at = AppTest.from_file(os.path.abspath(path), default_timeout=120)
    for k, v in state.items():
        at.session_state[k] = v
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def t_desk_page():
    results(*[f"APP-{k:02d}" for k in range(1, 24)])
    at = _page("dashboard/pages/1_Desk.py")
    assert at.title[0].value == "Desk" and len(at.dataframe[0].value) == 23
    assert any("Letter of Deficiency" in s.value for s in at.subheader)
    sel = next(s for s in at.selectbox if s.label == "Open application")
    sel.set_value("APP-19").run()
    assert not at.exception and any("Resubmission of APP-02" in s.value for s in at.subheader)
    assert any("1 of 1 deficiencies resolved" in i.value for i in at.info)


def t_yoy():
    import json
    from pramaan.schemas import Application
    from pramaan.yoy import yoy_check
    rs = results(*[f"APP-{k:02d}" for k in range(1, 21)])
    hits = {r.app_id: [f.rule_id for f in r.findings if f.rule_id.startswith("X-YOY")] for r in rs}
    assert hits["APP-20"] == ["X-YOY-INTAKE"], hits["APP-20"]
    assert not any(v for a, v in hits.items() if a != "APP-20"), {a: v for a, v in hits.items() if v}
    f = next(f for f in rs[-1].findings if f.rule_id == "X-YOY-INTAKE")
    assert f.lane == "human_review" and "+50%" in f.reason, f.reason
    m = json.load(open("data/demo/apps/APP-01.json")); rec = json.load(open("data/aicte_records.json"))[m["permanent_id"]]
    app = Application(**{**m, "declared": {**m["declared"], "institute_name": "Completely Renamed Institute"}})
    assert [x.rule_id for x in yoy_check(app, [], rec, {})] == ["X-YOY-NAME"]


def t_serial():
    rs = results(*[f"APP-{k:02d}" for k in range(1, 24)])
    hits = {r.app_id: [f for f in r.findings if f.rule_id == "X-SERIAL"] for r in rs}
    assert len(hits["APP-22"]) == 1 and "APP-21" in hits["APP-22"][0].reason and hits["APP-22"][0].lane == "human_review", hits["APP-22"]
    assert "% identical to the one submitted by APP-21" in hits["APP-22"][0].reason, hits["APP-22"][0].reason
    false = {a: len(v) for a, v in hits.items() if v and a != "APP-22"}
    assert not false, false                                      # 0 false matches on the other 22 apps (APP-01..18 included)


def t_verify_board():
    import json
    from pramaan.schemas import Application
    from pramaan.verify_board import board
    r1, r3 = results("APP-01", "APP-03")
    app = lambda a: Application(**json.load(open(f"data/demo/apps/{a}.json")))
    b1 = board(r1, app("APP-01"))
    src = {x["source"]: x["status"] for x in b1}
    assert src["MOCK municipal occupancy register"] == "verified" and src["MOCK NBA accreditation"] == "verified", src
    assert src["MOCK DigiLocker issued documents"] == "verified" and src["MOCK AICTE records"] == "verified", src
    assert all(x["source"].startswith("MOCK") for x in b1 if x["mock"]) and any(not x["mock"] for x in b1)   # pyHanko row is real
    b3 = board(r3, app("APP-03"))                                    # APP-03: no DigiLocker consent in its manifest
    assert {x["status"] for x in b3 if "DigiLocker" in x["source"]} == {"consent not given"}, b3
    assert all(set(x) >= {"document", "source", "status", "checked_at", "compared"} for x in b1 + b3)


TESTS = {"lod": t_lod, "resubmit": t_resubmit, "checklist": t_checklist, "queue": t_queue, "trust": t_trust, "seal": t_seal, "desk_page": t_desk_page, "yoy": t_yoy, "serial": t_serial, "verify_board": t_verify_board}

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
