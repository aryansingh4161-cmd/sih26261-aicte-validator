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
    import re
    from streamlit.testing.v1 import AppTest
    src = open(path, encoding="utf-8").read()            # Streamlit "magic" renders bare expressions; AppTest does not show it
    assert not re.search(r"\) if .+ else st\.", src), f"{path}: use if/else, not a conditional expression statement"
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


def t_expiry():
    from pramaan.expiry import days_left, expiries, overdue, reminders, to_ics
    rs = results(*[f"APP-{k:02d}" for k in range(1, 24)])
    rows = expiries(rs)
    kinds = {r["doc_type"] for r in rows}
    assert {"fire_cert", "structural_cert"} <= kinds and all(r["how"] for r in rows), kinds
    od = overdue(rows, TODAY)
    assert {r["app_id"] for r in od} >= {"APP-03"} and all(days_left(r, TODAY) < 0 for r in od), od      # APP-03 fire expired
    box = os.path.join(TMP, "outbox")
    soon = [r for r in rows if 0 <= days_left(r, TODAY) <= 60]
    sent = reminders(rows, TODAY, outbox=box)
    assert len(sent) == len(soon) and reminders(rows, TODAY, outbox=box) == sent              # once per threshold
    fake = [{"app_id": "APP-X", "doc_id": "APP-X-fire_cert", "doc_type": "fire_cert", "expires": "2026-11-02", "how": "test"}]
    p = reminders(fake, TODAY, outbox=box)[0]
    assert p.endswith("reminder-APP-X-fire_cert-7d.json") and '"channel": "email (MOCK)"' in open(p).read()
    ics = to_ics(rows)
    assert ics.startswith("BEGIN:VCALENDAR") and ics.count("BEGIN:VEVENT") == len(rows) and "DTSTART;VALUE=DATE:" in ics


def t_feedback():
    import csv
    from pramaan.audit import AuditLog
    from pramaan.feedback import export_csv, false_alarm_rate, record
    r9, r17 = results("APP-09", "APP-17")
    u = {"id": "officer.demo", "role": "scrutiny_officer"}
    db = os.path.join(TMP, "fb.db")
    with AuditLog(db) as log:
        for f in r17.findings:
            record(db, f, "false alarm" if f.rule_id == "F-META-JPEG-QT" else "correct", u, "weak signal" if "QT" in f.rule_id else "", log)
        f9 = r9.findings[0]
        record(db, f9, "false alarm", u, log=log); record(db, f9, "correct", u, "changed my mind", log)      # latest verdict counts
        assert log.verify_chain() == (True, None) and sum(x["action"].startswith("feedback") for x in log.rows()) == len(r17.findings) + 2
    rate = false_alarm_rate(db)
    assert rate["F-META-JPEG-QT"] == {"false_alarms": 1, "n": 1, "rate": 1.0} and rate[f9.rule_id]["false_alarms"] == 0, rate
    out = export_csv(db, os.path.join(TMP, "feedback.csv"))
    assert len(list(csv.DictReader(open(out)))) == len(r17.findings) + 2
    try:
        record(db, f9, "maybe", u); raise AssertionError("bad verdict accepted")
    except ValueError:
        pass


def t_assign():
    import json, yaml
    from pramaan.assign import assign, due_date, my_queue
    rs = results(*[f"APP-{k:02d}" for k in range(1, 24)])
    mans = {r.app_id: json.load(open(f"data/demo/apps/{r.app_id}.json")) for r in rs}
    users = yaml.safe_load(open("config/users.yaml"))["users"]
    a = assign(rs, mans, users)
    region_of = {u["id"]: set(u.get("regions", [])) for u in users}
    assert all(mans[x]["declared"]["region"] in region_of[o] for x, o in a.items() if o != "unassigned"), a
    west = sorted((r for r in rs if mans[r.app_id]["declared"]["region"] == "West"), key=lambda r: (-r.priority, r.app_id))
    if len(west) >= 2:                                               # two West officers alternate, highest priority first
        assert a[west[0].app_id] == "officer.west" and a[west[1].app_id] == "officer.west2", [(r.app_id, a[r.app_id]) for r in west]
    q = my_queue(a, "officer.nw", rs)
    assert [r.priority for r in q] == sorted([r.priority for r in q], reverse=True)
    r = rs[0]
    assert (due_date(r, TODAY, {"assignment_sla_days": {r.lane: 3}}) - TODAY).days == 3
    assert assign(rs, mans, [u for u in users if u["id"] != "officer.central"])[next(x for x in a if mans[x]["declared"]["region"] == "Central")] == "unassigned"


def t_export_case():
    import hashlib, json, zipfile
    from pramaan.export_case import export_case
    from pramaan.seal import verify_sealed
    results("APP-06")
    zp = export_case("APP-06", TMP, DB, zip_path=os.path.join(TMP, "APP-06_case.zip"))
    with zipfile.ZipFile(zp) as z:
        names = set(z.namelist())
        assert {"manifest.json", "hashes.json", "result.json", "letter_of_deficiency.txt", "decisions.json", "audit_slice.json",
                "VERIFY.txt", "report.html"} <= names, names
        hashes = json.loads(z.read("hashes.json"))
        inside = {n.split("/", 1)[1]: hashlib.sha256(z.read(n)).hexdigest() for n in names if n.startswith("documents/")}
        assert inside and all(inside[h["file"]] == h["sha256"] for h in hashes.values() if h["file"] in inside), "hashes match"
        assert any(n.startswith("evidence/") and n.endswith(".png") for n in names)
        assert verify_sealed(z.read("report.html").decode(), DB).startswith("VALID")
        assert all(r["app_id"] == "APP-06" for r in json.loads(z.read("audit_slice.json")))


def t_checks_pages():
    results(*[f"APP-{k:02d}" for k in range(1, 24)])
    os.environ["PRAMAAN_OUTBOX"] = os.path.join(TMP, "outbox")
    at = _page("dashboard/pages/3_Checks.py")
    assert at.title[0].value == "Checks" and any("APP-22" in str(d.value) for d in at.dataframe), "serial table shows APP-22"
    at = _page("dashboard/pages/4_Calendar_Exports.py")
    assert at.title[0].value == "Calendar & Exports" and any("Overdue" in m.value for m in at.markdown), [m.value for m in at.markdown][:5]


def t_geo():
    from pramaan.geo import geo_check
    rs = results(*[f"APP-{k:02d}" for k in range(1, 24)])
    hits = {r.app_id: [f for f in r.findings if f.rule_id == "X-GEO"] for r in rs}
    assert len(hits["APP-23"]) == 1 and hits["APP-23"][0].lane == "human_review" and "15." in hits["APP-23"][0].reason, hits["APP-23"]
    assert not {a for a, v in hits.items() if v and a != "APP-23"}, "no X-GEO on the other 22 apps"
    assert "MOCK" in hits["APP-23"][0].evidence[0].text


def t_selfcheck():
    from pramaan.audit import AuditLog
    from pramaan.selfcheck import MARK, precheck, todo
    results("APP-01")
    with AuditLog(DB) as log:
        n0 = len(log.rows())
    work = os.path.join(TMP, "selfcheck")
    r4 = precheck("data/demo/apps/APP-04.json", work, TODAY)
    items = todo(r4, TODAY)
    assert r4.notes[0] == MARK and any("Structural Stability Certificate is 4 years old: upload one issued after 2023-10-26" in i
                                       for i in items), items
    assert todo(precheck("data/demo/apps/APP-01.json", work, TODAY), TODAY) == ["Nothing to fix was found. You can submit."]
    with AuditLog(DB) as log:
        assert len(log.rows()) == n0                      # nothing reached the officer's audit log
    assert os.path.exists(os.path.join(work, "selfcheck_audit.db"))


def t_selfcheck_page():
    at = _page("dashboard/pages/5_Institute_SelfCheck.py")
    assert at.title[0].value == "Institute self-check" and "SELF-CHECK" in at.warning[0].value
    sel = next(s for s in at.selectbox if s.label == "Application")
    assert sorted(sel.options) == ["APP-02", "APP-19"], sel.options          # only its own Permanent Id
    sel.set_value("APP-02").run()
    next(b for b in at.button if b.label == "Run self-check").click().run()
    assert not at.exception and any("Fire Safety Certificate missing" in m.value for m in at.markdown), [m.value for m in at.markdown]


def t_evc_pack():
    import json
    from pramaan.audit import AuditLog
    from pramaan.evc_pack import evc_pack, items
    from pramaan.seal import verify_sealed
    rs = {r.app_id: r for r in results(*[f"APP-{k:02d}" for k in range(1, 24)])}
    rec = json.load(open("data/aicte_records.json"))
    pid = lambda a: json.load(open(f"data/demo/apps/{a}.json"))["permanent_id"]
    i15 = items(rs["APP-15"], rec[pid("APP-15")], TODAY)
    assert any(x["what"].startswith("Measure the rooms") and "norm" in x["why"] for x in i15), i15
    i05 = items(rs["APP-05"], rec[pid("APP-05")], TODAY)
    assert any("over 30 years" in x["what"] and "ANNEXURE-2 2.1 iv." in x["clause"] for x in i05), i05
    assert any("sworn after submission" in x["what"] for x in items(rs["APP-10"], rec[pid("APP-10")], TODAY))
    assert any("photos" in x["what"] for x in items(rs["APP-09"], rec[pid("APP-09")], TODAY))
    with AuditLog(DB) as log:
        page = evc_pack(rs["APP-15"], rec[pid("APP-15")], log, TODAY)
    assert verify_sealed(page, DB).startswith("VALID") and "Expert Visit Committee" in page


def t_analytics():
    import json
    from pramaan import analytics as A
    from pramaan.audit import AuditLog
    rs = results(*[f"APP-{k:02d}" for k in range(1, 24)])
    mans = {r.app_id: json.load(open(f"data/demo/apps/{r.app_id}.json")) for r in rs}
    top = A.top_deficiencies(rs)
    assert top and top[0][1] >= top[-1][1] and len(top) <= 10
    reg = A.by_region(rs, mans)
    assert sum(v["applications"] for v in reg.values()) == 23
    assert sum(A.lane_split(rs).values()) == 23
    with AuditLog(DB) as log:
        rows = log.rows()
    k, n = A.auto_cleared_share(rs, rows)
    assert n == 23 and 0 <= k <= n
    assert A.median_processing_days(rs, mans) is not None
    assert isinstance(A.sla_breaches(rs, rows, TODAY), list)
    at = _page("dashboard/pages/2_Analytics.py")
    assert any("Leadership view" in m.value for m in at.markdown), "leadership section rendered"


TESTS = {"lod": t_lod, "resubmit": t_resubmit, "checklist": t_checklist, "queue": t_queue, "trust": t_trust, "seal": t_seal, "desk_page": t_desk_page, "yoy": t_yoy, "serial": t_serial, "verify_board": t_verify_board, "expiry": t_expiry, "feedback": t_feedback, "assign": t_assign, "export_case": t_export_case, "checks_pages": t_checks_pages, "geo": t_geo, "selfcheck": t_selfcheck, "selfcheck_page": t_selfcheck_page, "evc_pack": t_evc_pack, "analytics": t_analytics}

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
