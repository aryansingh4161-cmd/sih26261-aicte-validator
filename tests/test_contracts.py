"""Contract tests: the gate for merging ANY version of a module (yours, an AI's, or reference/).
  python -m tests.test_contracts                 -> tests every module present in pramaan/
  python -m tests.test_contracts rules triage    -> only those
Prints PASS/FAIL/SKIP per module and ALL TESTS PASSED if nothing failed. OWNER: Aryan."""
import importlib
import json
import os
import random
import sys
import tempfile
import traceback
from datetime import date

from pramaan.schemas import Application, DocumentRecord, ExtractedField, Finding, VerificationResult
from pramaan.synth import content as C, docs as D

TODAY = date(2026, 10, 26)
TMP = tempfile.mkdtemp()


def _samples():
    rng = random.Random(5); inst = C.make_institute(rng, 2026); det = D.default_details(rng, inst)
    out = {}
    for dt in D.BUILDERS:
        out[dt] = D.render_pdf(dt, "A", inst, det, os.path.join(TMP, f"{dt}.pdf"))
    return inst, out


INST, SAMPLES = _samples()
APP = Application(app_id="T1", category="eoa_existing_regular", academic_year="2026-27", permanent_id=INST["permanent_id"],
                  submitted_on="2026-10-01", declared={"institute_name": INST["institute_name"]})


def t_ingest(m):
    r = m.ingest(SAMPLES["fire_cert"]["path"], "T1-fire", "fire_cert")
    assert r.pages == 1 and len(r.blocks) > 5 and not r.is_scanned
    assert all(0 <= b.bbox.x0 <= b.bbox.x1 <= 1 and 0 <= b.bbox.y0 <= b.bbox.y1 <= 1 for b in r.blocks)
    bad = os.path.join(TMP, "bad.pdf"); open(bad, "w").write("not a pdf")
    b = m.ingest(bad, "x"); assert b.pages == 0 and "error" in b.metadata


def t_classify_extract(m):
    from pramaan.ingest import ingest
    for dt, s in SAMPLES.items():
        d = m.classify_and_extract(ingest(s["path"], "d"), "config/doc_specs")
        assert d.doc_type == dt, (dt, d.doc_type)
        ok = sum(1 for k, v in s["truth"].items() if k in d.fields and str(d.fields[k].value).lower() == str(v).lower())
        assert ok >= len(s["truth"]) - 1, (dt, ok, len(s["truth"]))


def _doc(dt, **fields):
    return DocumentRecord(doc_id=f"T1-{dt}", filename=f"{dt}.pdf", path="x", sha256="0", doc_type=dt, pages=1,
                          fields={k: ExtractedField(name=k, value=v) for k, v in fields.items()})


def t_rules(m):
    rp = "config/rulepack_eoa_existing.yaml"
    f = m.run_rules(APP, [], [], None, rp, TODAY)
    assert any(x.rule_id == "R-MISS-fire_cert" for x in f)
    f = m.run_rules(APP, [_doc("fire_cert", valid_until="2026-01-01")], [], None, rp, TODAY)
    assert any(x.rule_id == "R-EXP-fire_cert" for x in f)
    f = m.run_rules(APP, [_doc("fire_cert", valid_until="2027-01-01")], [], None, rp, TODAY)
    assert not any(x.rule_id.startswith(("R-EXP-fire", "R-MISS-fire")) for x in f)
    s = _doc("structural_cert", issue_date="2022-09-01", validity_years="3")
    assert any(x.rule_id == "R-EXP-structural_cert" for x in m.run_rules(APP, [s], [], None, rp, TODAY))
    old = {"building_completion_date": "1985-01-01", "ter_paid": True}
    assert any(x.rule_id == "R-MISS-structural_cert" for x in m.run_rules(APP, [], [], old, rp, TODAY))
    assert all("reject" not in (x.title + x.reason).lower() for x in f)


def t_crosscheck(m):
    a = _doc("fire_cert", institute_name="Totally Different Name College")
    f = m.run_crosscheck(APP, [a], None, TODAY)
    assert any(x.rule_id == "X-NAME" and x.lane == "human_review" for x in f)


def t_triage(m):
    mk = lambda i, lane, rid, sev="high": Finding(finding_id=i, app_id="T1", source="rule", rule_id=rid, title=i, reason="r", severity=sev, lane=lane)
    assert m.assign_lane([]) == "clear"
    assert m.assign_lane([mk("a", "return_for_rectification", "R-MISS-x"), mk("b", "human_review", "X-NAME")]) == "human_review"
    al = m.make_alerts(APP, [mk("a", "return_for_rectification", "R-MISS-x"), mk("b", "return_for_rectification", "R-MISS-y", "low")], [], TODAY)
    assert len(al) == 1 and al[0].kind == "missing_document" and al[0].due_by == "2026-10-28"


def t_audit(m):
    p = os.path.join(TMP, "a.db"); log = m.AuditLog(p)
    for i in range(3):
        log.append("sys", "system", "x", "T1", {"i": i})
    assert log.verify_chain() == (True, None)
    import sqlite3
    c = sqlite3.connect(p); c.execute("UPDATE audit SET detail='{\"i\": 99}' WHERE id=2"); c.commit()
    assert m.AuditLog(p).verify_chain() == (False, 2)


def t_report(m):
    from pramaan.schemas import ApplicationResult
    bad = Finding(finding_id="f", app_id="T1", source="rule", rule_id="R", title="<script>x</script>", reason="r", severity="high", lane="human_review")
    r = ApplicationResult(app_id="T1", category="eoa_existing_regular", academic_year="2026-27", run_at="now", lane="human_review",
                          documents=[], findings=[bad], verifications=[], alerts=[], audit_head_hash="h", seconds_taken=0.1)
    out = m.build_report(r, TMP); html = open(out["html"]).read()
    assert "<script>x" not in html and "AI advisory only" in html and os.path.exists(out["json"])


def t_pipeline(m):
    if not os.path.exists("data/demo/apps/APP-02.json"):
        raise RuntimeError("run: python -m pramaan.synth.bundles  first")
    r = m.run_application("data/demo/apps/APP-02.json", TMP, TODAY, os.path.join(TMP, "p.db"))
    assert any(f.rule_id == "R-MISS-fire_cert" for f in r.findings) and r.lane in ("return_for_rectification", "human_review")


TESTS = {"ingest": t_ingest, "classify_extract": t_classify_extract, "rules": t_rules, "crosscheck": t_crosscheck,
         "triage": t_triage, "audit": t_audit, "report": t_report, "pipeline": t_pipeline}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    failed = 0
    for name in want:
        try:
            mod = importlib.import_module(f"pramaan.{name}")
        except ModuleNotFoundError as e:
            print(f"SKIP {name} (not in pramaan/ yet: {e.name})"); continue
        try:
            TESTS[name](mod); print(f"PASS {name}")
        except Exception:
            failed += 1; print(f"FAIL {name}"); traceback.print_exc(limit=2)
    print("ALL TESTS PASSED" if not failed else f"{failed} FAILED")
