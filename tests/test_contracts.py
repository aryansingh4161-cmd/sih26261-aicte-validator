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

from pramaan.schemas import Application, ApplicationResult, DocumentRecord, ExtractedField, Finding, VerificationResult
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


def t_signature(m):
    """forensics.signature_check: 4 cases (designed in WK1). Needs pyHanko; SKIPs cleanly without it."""
    from pramaan.synth import demo_pki
    if not demo_pki.can_sign():
        raise _Skip("pyhanko not installed: pip install pyhanko")
    pki = demo_pki.make_pki(os.path.join(TMP, "pki"), root_copy=os.path.join(TMP, "root.pem"))
    src = SAMPLES["affidavit_2"]["path"]
    signed = os.path.join(TMP, "signed.pdf"); demo_pki.sign_pdf(src, signed, pki)
    raw = open(signed, "rb").read(); assert b"SYNTH-PORTAL" in raw
    edited = os.path.join(TMP, "edited.pdf"); open(edited, "wb").write(raw.replace(b"SYNTH-PORTAL", b"SYNTX-PORTAL", 1))
    doc = lambda p: DocumentRecord(doc_id="T1-affidavit_2", filename=os.path.basename(p), path=p, sha256="0", pages=1)
    cases = [(signed, [pki["root"]], "verified"), (edited, [pki["root"]], "mismatch_detected"),
             (signed, [], "manual_review_required"), (src, [pki["root"]], "manual_review_required")]
    for path, roots, want in cases:
        r = m.signature_check(doc(path), roots)
        assert r.status == want and r.method == "digital_signature" and r.mock is False, (path, roots, r.status, r.note)
        if path == src:
            assert "no digital signature found" in r.note, r.note



def t_priority(m):
    """priority.score: designed weights from settings, reasons for every term, capped at 1.0 (F10)."""
    from pramaan.schemas import Alert, ApplicationResult
    def f(i, sev):
        return Finding(finding_id=f"T1-R-X{i}-APP", app_id="T1", source="rule", rule_id=f"R-X{i}", title="t", reason="t",
                       severity=sev, lane="human_review")
    base = dict(app_id="T1", category="eoa_existing_regular", academic_year="2026-27", run_at="2026-10-26T00:00:00",
                lane="clear", documents=[], findings=[], verifications=[], alerts=[], audit_head_hash="h", seconds_taken=0.1)
    w = {"priority_weights": {"high": 0.25, "medium": 0.1, "low": 0.03, "suspected_anomaly": 0.2, "old_building": 0.1,
                              "old_building_years": 30, "noc_intake_above_approved": 0.15}}
    assert m.score(ApplicationResult(**base), None, w, TODAY) == (0.0, [])
    rec = {"building_completion_date": "1980-06-01", "approved_programs": [{"course": "CSE", "intake_prev": "90"}, {"course": "CSE", "intake_prev": "60"}]}
    noc = DocumentRecord(doc_id="T1-noc", filename="n.pdf", path="n.pdf", sha256="0", doc_type="noc_format2",
                         tables={"programs": [{"course": "CSE", "intake_curr": "90"}, {"course": "CSE", "intake_curr": "60"}]})
    r = ApplicationResult(**{**base, "documents": [noc], "findings": [f(1, "high"), f(2, "medium"), f(3, "low")]})
    s, why = m.score(r, rec, w, TODAY)
    assert abs(s - 0.48) < 1e-9 and len(why) == 4, (s, why)          # 0.25 + 0.1 + 0.03 + old building 0.1; equal intakes not flagged
    noc.tables["programs"][1]["intake_curr"] = "120"
    al = Alert(alert_id="T1-AL1", app_id="T1", kind="suspected_anomaly", message="m", created_at="x", due_by="2026-10-28")
    r = ApplicationResult(**{**base, "documents": [noc], "alerts": [al], "findings": [f(i, "high") for i in range(4)]})
    s, why = m.score(r, rec, w, TODAY)
    assert s == 1.0 and any("NOC" in x for x in why) and any("capped" in x for x in why), (s, why)


def t_reuse(m):
    """reuse.check_reuse: certificate number and photo reused by a DIFFERENT app; re-run never matches itself (F8)."""
    from PIL import Image
    db = os.path.join(TMP, "reuse.db")
    if os.path.exists(db):
        os.remove(db)
    img = Image.new("RGB", (64, 64), (200, 200, 200)); img.paste((30, 30, 30), (0, 0, 32, 64))
    ph = os.path.join(TMP, "campus.jpg"); img.save(ph)
    def doc(app_id, no, sha):
        return DocumentRecord(doc_id=f"{app_id}-fire_cert", filename="f.pdf", path="f.pdf", sha256=sha, doc_type="fire_cert",
                              fields={"certificate_no": ExtractedField(name="certificate_no", value=no)})
    a = APP.model_copy(update={"app_id": "TA", "photos": [ph]}); b = APP.model_copy(update={"app_id": "TB", "photos": [ph]})
    assert m.check_reuse(a, [doc("TA", "FS/1", "s1")], db) == []
    assert m.check_reuse(a, [doc("TA", "FS/1", "s1")], db) == []          # same app again: no self-match
    out = m.check_reuse(b, [doc("TB", "FS/1", "s2")], db)
    ids = sorted(f.rule_id for f in out)
    assert ids == ["X-REUSE-CERT", "X-REUSE-PHOTO"], ids
    assert all(f.lane == "human_review" and f.severity == "high" and "TA" in f.evidence[0].text for f in out)
    assert m.check_reuse(a, [doc("TA", "FS/1", "s1")], db) == []          # earlier app re-run: unchanged
    assert m.check_reuse(b, [doc("TB", "FS/9", "s3")], db)[0].rule_id == "X-REUSE-PHOTO"   # cert changed, photo still shared


def t_area(m):
    """rules area_min (F9) on a real synthetic area_statement + tools/norms_to_yaml uses ONLY rows with checked = ok."""
    import yaml
    from pramaan.classify_extract import classify_and_extract
    from pramaan.ingest import ingest
    from tools.norms_to_yaml import convert
    csvp = os.path.join(TMP, "norms.csv")
    with open(csvp, "w") as f:
        f.write("room_type,min_rooms_rule_as_printed,min_rooms_number,min_area_per_room_sqm,programme,clause_as_printed,page,checked\n"
                "Classroom,one per division,4,66,UG Engineering,CLAUSE TEXT A,12,ok\n"
                "Drawing Hall,one,1,132,UG Engineering,CLAUSE TEXT B,12,ok\n"
                "Seminar Hall,,,132,UG Engineering,CLAUSE TEXT C,13,\n")
    nf = convert(csvp)
    assert [n["room_type"] for n in nf["norms"]] == ["classroom", "drawing_hall"] and nf["norms"][0]["clause_verified"] is True, nf
    normp, rp = os.path.join(TMP, "norms.yaml"), os.path.join(TMP, "rp_area.yaml")
    yaml.safe_dump(nf, open(normp, "w"))
    yaml.safe_dump({"rules": [{"id": "R-AREA", "type": "area_min", "applies_to": ["eoa_existing_regular"],
                               "params": {"doc_type": "area_statement", "norms_file": normp}, "severity": "medium",
                               "lane": "return_for_rectification", "title": "t", "message": "m"}]}, open(rp, "w"))
    det = D.default_details(random.Random(9), INST)
    det["areas"] = [{"room_type": "Classroom", "count": 5, "area_sqm": 300}, {"room_type": "Library", "count": 1, "area_sqm": 400}]
    path = D.render_pdf("area_statement", "C", INST, det, os.path.join(TMP, "area.pdf"))["path"]
    doc = classify_and_extract(ingest(path, "T1-area_statement"))
    assert doc.doc_type == "area_statement" and len(doc.tables.get("areas", [])) == 2, (doc.doc_type, doc.tables)
    out = m.run_rules(APP, [doc], [], None, rp, TODAY)
    ids = sorted(f.rule_id for f in out)          # classroom 60 < 66 per room; drawing hall absent -> 0 < 1
    assert ids == ["R-AREA-COUNT-drawing_hall", "R-AREA-classroom"], ids
    assert all(f.lane == "return_for_rectification" and f.severity == "medium" and f.clause_verified for f in out)
    assert next(f for f in out if f.rule_id == "R-AREA-classroom").aph_clause == "CLAUSE TEXT A"
    det["areas"][0]["area_sqm"] = 330                                            # exactly 66 per room: passes
    D.render_pdf("area_statement", "A", INST, det, path)
    assert sorted(f.rule_id for f in m.run_rules(APP, [classify_and_extract(ingest(path, "T1-a"))], [], None, rp, TODAY)) == ["R-AREA-COUNT-drawing_hall"]
    assert m.run_rules(APP, [], [], None, rp, TODAY) == []                        # no area statement: nothing (required_doc reports it)


def t_issuer_webhook(m):
    """issuer_async (WK9, MOCK): signed reply pending -> verified, chain intact; bad signature 401; duplicate 409, no change."""
    try:
        from starlette.testclient import TestClient
    except Exception:
        raise _Skip("starlette TestClient needs httpx: pip install httpx")
    from pramaan.audit import AuditLog
    from pramaan.pipeline import run_application
    if not os.path.exists("data/demo/apps/APP-11.json"):
        raise RuntimeError("run: python -m pramaan.synth.bundles  first")
    out, db = os.path.join(TMP, "wh"), os.path.join(TMP, "wh", "audit.db")
    r0 = run_application("data/demo/apps/APP-11.json", out, TODAY, db)
    v0 = next(v for v in r0.verifications if v.method == "issuer_portal")
    assert v0.status == "verification_pending" and any(a.kind == "pending_verification" for a in r0.alerts), v0.status
    c = TestClient(m.create_app(out, db, "data/demo/apps", today=TODAY, secret="test-secret"))
    doc = next(d for d in r0.documents if d.doc_id == v0.doc_id)
    body = {"doc_id": v0.doc_id, "method": "issuer_portal", "reference": v0.reference, "status": "verified",
            "returned": {"valid_until": doc.fields["valid_until"].value}, "timestamp": "2026-10-27T10:00:00+05:30"}
    n0 = len(AuditLog(db).rows())
    assert c.post("/webhook/issuer", json={**body, "signature": "00" * 32}).status_code == 401
    assert c.post("/webhook/issuer", json={**body, "signature": m.sign(body, "wrong")}).status_code == 401
    assert len(AuditLog(db).rows()) == n0                                     # rejected: nothing written
    good = {**body, "signature": m.sign(body, "test-secret")}
    resp = c.post("/webhook/issuer", json=good)
    assert resp.status_code == 200 and resp.json()["status"] == "verified", resp.text
    r1 = ApplicationResult.model_validate_json(open(os.path.join(out, "APP-11.result.json")).read())
    v1 = next(v for v in r1.verifications if v.method == "issuer_portal")
    assert v1.status == "verified" and v1.mock and v1.source.startswith("MOCK ") and v1.payload_hash
    assert not any(a.kind == "pending_verification" for a in r1.alerts) and r1.lane == "clear"
    log = AuditLog(db); rows = log.rows("APP-11")
    assert log.verify_chain() == (True, None) and r1.audit_head_hash == rows[-1]["hash"]
    assert any(x["action"] == "source response" and v1.payload_hash in x["detail"] for x in rows)
    n1 = len(log.rows())
    assert c.post("/webhook/issuer", json=good).status_code == 409 and len(AuditLog(db).rows()) == n1   # duplicate ignored
    bad = {**body, "status": "mismatch_detected", "timestamp": "2026-10-28T10:00:00+05:30"}
    assert c.post("/webhook/issuer", json={**bad, "signature": m.sign(bad, "test-secret")}).json()["lane"] == "human_review"


def t_retention(m):
    """tools/retention (WK11): dry run lists only OLD in-scope files, deletes nothing, never lists audit.db, writes one audit row."""
    import time
    from tools.retention import run
    out = os.path.join(TMP, "ret"); os.makedirs(os.path.join(out, "heatmaps"), exist_ok=True)
    old = time.time() - 40 * 86400
    files = {"A.result.json": old, "A.report.html": old, "heatmaps/A_p1.png": old, "B.result.json": time.time(),
             "audit.db": None, "reuse.db": old, "notes.txt": old}
    for rel, t in files.items():
        if rel != "audit.db":
            open(os.path.join(out, rel), "w").write("x")
            os.utime(os.path.join(out, rel), (t, t))
    db = os.path.join(out, "audit.db")
    m.AuditLog(db).append("t", "system", "seed", None, {}); os.utime(db, (old, old))
    s = run(out, days=30, apply=False)
    assert sorted(s["sample"]) == ["A.report.html", "A.result.json", os.path.join("heatmaps", "A_p1.png")], s["sample"]
    assert s["deleted"] == 0 and all(os.path.exists(os.path.join(out, r)) for r in files)
    rows = m.AuditLog(db).rows()
    assert rows[-1]["action"] == "retention dry-run" and m.AuditLog(db).verify_chain() == (True, None)
    s = run(out, days=30, apply=True)
    assert s["deleted"] == 3 and os.path.exists(db) and os.path.exists(os.path.join(out, "B.result.json"))
    assert m.AuditLog(db).rows()[-1]["action"] == "retention applied"


def t_masking(m):
    """privacy (WK11): personal values masked in audit details and the HTML report, full value kept in the result JSON."""
    from pramaan.audit import AuditLog
    from pramaan.pipeline import run_application
    from pramaan.report import render_html
    assert m.mask("Kavya Verma") == "K**** V****" and m.mask("IN-DL57") == "I******" and m.mask(None) is None
    db = os.path.join(TMP, "mask.db")
    AuditLog(db).append("t", "system", "x", None, {"values": {"signatory_name": "Kavya Verma", "institute_name": "Demo Inst"},
                                                   "items": [{"stamp_no": "IN-DL57"}]})
    d = AuditLog(db).rows()[-1]["detail"]
    assert "Kavya" not in d and "K**** V****" in d and "I******" in d and "Demo Inst" in d, d
    if not os.path.exists("data/demo/apps/APP-10.json"):
        raise RuntimeError("run: python -m pramaan.synth.bundles  first")
    out = os.path.join(TMP, "mask_out"); r = run_application("data/demo/apps/APP-10.json", out, TODAY, os.path.join(out, "a.db"))
    aff = next(x for x in r.documents if x.doc_type == "affidavit_2")
    name, stamp = aff.fields["signatory_name"].value, aff.fields["stamp_no"].value
    assert name in open(os.path.join(out, "APP-10.result.json")).read()          # officer's JSON keeps the full value
    details = " ".join(x["detail"] for x in AuditLog(os.path.join(out, "a.db")).rows("APP-10"))
    assert name not in details and stamp not in details and m.mask(name) in details
    f = r.findings[0].model_copy(update={"reason": f"Signed by {name}, stamp {stamp}."})
    html = render_html(r.model_copy(update={"findings": [f]}))
    assert name not in html and stamp not in html and m.mask(name) in html

class _Skip(Exception):
    pass


MODULE = {"signature": "forensics", "priority": "priority", "reuse": "reuse", "area": "rules", "issuer_webhook": "issuer_async", "retention": "audit", "masking": "privacy"}   # test name -> module in pramaan/


TESTS = {"ingest": t_ingest, "classify_extract": t_classify_extract, "rules": t_rules, "crosscheck": t_crosscheck,
         "triage": t_triage, "audit": t_audit, "report": t_report, "pipeline": t_pipeline,
         "signature": t_signature, "priority": t_priority, "reuse": t_reuse,
         "area": t_area, "issuer_webhook": t_issuer_webhook,
         "retention": t_retention, "masking": t_masking}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    failed = 0
    for name in want:
        try:
            mod = importlib.import_module(f"pramaan.{MODULE.get(name, name)}")
        except ModuleNotFoundError as e:
            print(f"SKIP {name} (not in pramaan/ yet: {e.name})"); continue
        try:
            TESTS[name](mod); print(f"PASS {name}")
        except _Skip as e:
            print(f"SKIP {name} ({e})")
        except Exception:
            failed += 1; print(f"FAIL {name}"); traceback.print_exc(limit=2)
    print("ALL TESTS PASSED" if not failed else f"{failed} FAILED")
