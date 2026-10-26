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


def t_search():
    import json
    from pramaan.search import delete_filter, list_filters, run_filter, save_filter, search
    results(*[f"APP-{k:02d}" for k in range(1, 24)])
    reg = json.load(open("data/demo/apps/APP-03.json"))["declared"]["region"]
    hits = search("fire", {"region": reg}, TMP)
    assert "APP-03" in [h["app_id"] for h in hits] and all(
        json.load(open(f"data/demo/apps/{h['app_id']}.json"))["declared"]["region"] == reg for h in hits), hits
    top = search("fire expired", {"region": reg}, TMP)
    assert top and top[0]["app_id"] == "APP-03", top[:3]
    name = json.load(open("data/demo/apps/APP-07.json"))["declared"]["institute_name"]
    word = max(name.split(), key=len); typo = word[:2] + word[3:]                  # one letter dropped
    assert any(h["app_id"] == "APP-07" for h in search(typo, None, TMP)), (typo, name)
    assert search("zzzz-nothing", None, TMP) == []                                  # review focus 2
    assert len(search("", {"region": reg}, TMP)) >= 1                               # filters only
    assert [h["app_id"] for h in search("serial", None, TMP)] == ["APP-22"]
    db = os.path.join(TMP, "audit.db")
    save_filter(db, "officer.nw", "fire expired here", "fire expired", {"region": reg})
    assert [f["name"] for f in list_filters(db, "officer.nw")] == ["fire expired here"]
    assert run_filter(db, "officer.nw", "fire expired here", out_dir=TMP)[0]["app_id"] == "APP-03"
    assert delete_filter(db, "officer.nw", "fire expired here") and list_filters(db, "officer.nw") == []


def t_notes():
    import zipfile
    from pramaan.audit import AuditLog
    from pramaan.export_case import export_case
    from pramaan.letters import build_lod
    from pramaan.notes import add_note, list_notes, mentions_for
    from pramaan.selfcheck import todo
    r2, = results("APP-02")
    secret = "Internal: the principal called twice; @officer.nw please check the fire NOC history. @nobody.here"
    out = add_note(DB, "APP-02", {"id": "officer.demo", "role": "scrutiny_officer"}, secret, r2.findings[0].finding_id)
    assert out["mentions"] == ["officer.nw"] and len(out["warnings"]) == 1, out                    # review focus 3
    assert [n["text"] for n in list_notes(DB, "APP-02")][-1] == secret
    assert any(n["note_id"] == out["note_id"] for n in mentions_for(DB, "officer.nw")) and not mentions_for(DB, "nobody.here")
    with AuditLog(DB) as log:
        row = [r for r in log.rows("APP-02") if r["action"] == "internal note"][-1]
    assert str(out["note_id"]) in row["detail"] and "principal" not in row["detail"]                # audit holds a hash, not the text
    assert "principal" not in build_lod(r2)["text"] and "principal" not in build_lod(r2)["html"]
    assert not any("principal" in x for x in todo(r2, TODAY))
    inst = export_case("APP-02", TMP, DB, zip_path=os.path.join(TMP, "APP-02_institute.zip"), institute_copy=True)
    with zipfile.ZipFile(inst) as z:
        assert "notes.json" not in z.namelist() and not any(b"principal" in z.read(n) for n in z.namelist())
        assert b"internal note" not in z.read("audit_slice.json")
    off = export_case("APP-02", TMP, DB, zip_path=os.path.join(TMP, "APP-02_officer.zip"))
    with zipfile.ZipFile(off) as z:
        assert b"principal" in z.read("notes.json")


def t_rule_admin():
    import shutil
    from pramaan.audit import AuditLog
    from pramaan.rule_admin import apply_edit, check_clause, coverage, propose_edit
    real = check_clause("ANNEXURE-3 3.1 c. - In case of partial/ provisional Occupancy Certificate issued by the State Government "
                        "authority, the same shall be considered only for 2 consecutive Academic Years.")
    assert real["found"] and real["page"] == 102, real
    fake = check_clause("Every institute shall plant forty-two mango trees before the Expert Visit Committee arrives.")
    assert not fake["found"]
    rp = os.path.join(TMP, "rulepack_copy.yaml"); shutil.copy("config/rulepack_eoa_existing.yaml", rp)
    before = open(rp, "rb").read()
    new = {"id": "R-MISS-noc_format2", "type": "required_doc", "applies_to": ["eoa_existing_regular"], "params": {"doc_type": "noc_format2"},
           "severity": "high", "lane": "return_for_rectification", "title": "University NOC missing",
           "message": "A No Objection Certificate from the affiliating University is required.",
           "aph_clause": "Every institute shall plant forty-two mango trees before the Expert Visit Committee arrives.", "clause_verified": True}
    p = propose_edit(new, rp)
    assert p["ok"] and p["rule"]["clause_verified"] is False and p["warnings"], p                 # made-up quote: not verified + warning
    bad = dict(new, type="magic_rule", title="Application rejected")
    pb = propose_edit(bad, rp)
    assert not pb["ok"] and any("unsupported rule type" in e for e in pb["errors"]) and any("never says" in e for e in pb["errors"])
    assert not apply_edit(bad, {"id": "admin.demo", "role": "admin"}, rp, DB)["applied"] and open(rp, "rb").read() == before
    out = apply_edit(new, {"id": "admin.demo", "role": "admin"}, rp, DB)
    assert out["applied"] and out["version"] == 2 and "version: 2" in open(rp).read() and "R-MISS-noc_format2" in open(rp).read()
    assert "# Rule pack v0" in open(rp).read()                                                     # comments kept
    with AuditLog(DB) as log:
        row = [r for r in log.rows() if r["action"] == "rule pack edited"][-1]
    assert row["hash"] == out["audit_hash"] and "R-MISS-noc_format2" in row["detail"]
    cov = coverage(rulepack=rp)
    assert cov["total"] == 59 and cov["covered"] == 8, cov


TESTS = {"case_timeline": t_case_timeline, "search": t_search, "notes": t_notes, "rule_admin": t_rule_admin}

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
