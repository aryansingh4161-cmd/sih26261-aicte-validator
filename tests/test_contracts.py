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
    fd, p = tempfile.mkstemp(suffix=".db", dir=TMP); os.close(fd)     # fresh file per call: the test tampers row 2
    log = m.AuditLog(p)
    for i in range(3):
        log.append("sys", "system", "x", "T1", {"i": i})
    assert log.verify_chain() == (True, None)
    import sqlite3
    c = sqlite3.connect(p); c.execute("UPDATE audit SET detail='{\"i\": 99}' WHERE id=2"); c.commit(); c.close()
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
    def doc(app_id, no, sha, auth="Demo City Fire Service (synthetic)"):
        return DocumentRecord(doc_id=f"{app_id}-fire_cert", filename="f.pdf", path="f.pdf", sha256=sha, doc_type="fire_cert",
                              fields={"certificate_no": ExtractedField(name="certificate_no", value=no),
                                      "issuing_authority": ExtractedField(name="issuing_authority", value=auth)})
    a = APP.model_copy(update={"app_id": "TA", "photos": [ph]}); b = APP.model_copy(update={"app_id": "TB", "photos": [ph]})
    NO = "FS/2026/4711"
    assert m.check_reuse(a, [doc("TA", NO, "s1")], db) == []
    assert m.check_reuse(a, [doc("TA", NO, "s1")], db) == []          # same app again: no self-match
    out = m.check_reuse(b, [doc("TB", NO, "s2")], db)
    ids = sorted(f.rule_id for f in out)
    assert ids == ["X-REUSE-CERT", "X-REUSE-PHOTO"], ids
    assert all(f.lane == "human_review" and f.severity == "high" and "TA" in f.evidence[0].text for f in out)
    assert m.check_reuse(a, [doc("TA", NO, "s1")], db) == []          # earlier app re-run: unchanged
    assert m.check_reuse(b, [doc("TB", "FS/2026/9999", "s3")], db)[0].rule_id == "X-REUSE-PHOTO"   # cert changed, photo still shared
    # WK16: short numbers and a different issuer never match
    c = APP.model_copy(update={"app_id": "TC"}); e = APP.model_copy(update={"app_id": "TE"})
    m.check_reuse(c, [doc("TC", "585", "s4")], db)
    assert m.check_reuse(e, [doc("TE", "585", "s5")], db) == []                                    # < 6 characters
    assert m.check_reuse(e, [doc("TE", NO, "s6", auth="Other District Fire Office (synthetic)")], db) == []   # other issuer

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
    try:
        import pyhanko  # noqa: F401  (APP-11 can only reach lane "clear" when its affidavit is really signed)
    except ImportError:
        raise _Skip("pyHanko not installed, demo affidavits are unsigned: pip install pyhanko, then rebuild bundles")
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


def t_metadata(m):
    """metadata_forensics (WK14): revision diff (1), EXIF software (4), EXIF thumbnail (5) on synthetic files, and
    NO false alarm on every clean demo document and photo."""
    import glob
    from datetime import datetime
    from PIL import Image, ImageDraw
    from pramaan.ingest import ingest
    from pramaan.synth.pdf_edit import incremental_text_edit
    from pramaan.synth.photos import photo
    rng = random.Random(8); inst = C.make_institute(rng, 2026); det = D.default_details(rng, inst)
    p = D.render_pdf("fire_cert", "B", INST, det, os.path.join(TMP, "meta_fire.pdf"))["path"]
    assert m.check_metadata("T1", ingest(p, "T1-fire_cert"), "2026-12-31") == []
    old = C.fmt_dmy(det["valid_until"]); incremental_text_edit(p, old, "31-12-2030", datetime(2026, 10, 1, 11))
    f = [x for x in m.check_metadata("T1", ingest(p, "T1-fire_cert"), "2026-12-31") if x.rule_id == "F-META-REVISION-DIFF"]
    assert len(f) == 1 and old in f[0].evidence[0].text and "31-12-2030" in f[0].evidence[0].text and f[0].evidence[0].bbox
    assert f[0].lane == "human_review" and f[0].source == "pdf_forensics" and "forged" not in f[0].reason.lower()
    ph = os.path.join(TMP, "cam.jpg"); photo(ph, random.Random(1), 28.6, 77.2, taken=datetime(2026, 10, 1, 10))
    doc = lambda q: DocumentRecord(doc_id="photo:x", filename="x.jpg", path=q, sha256="")
    assert m.check_metadata("T1", doc(ph), "2026-10-20", photo=True) == []                    # clean camera photo
    from pramaan.image_meta import exif_thumbnail, with_thumbnail
    im = Image.open(ph); ex = im.getexif(); ex[0x0131] = "GIMP 2.10"                          # same pixels, thumbnail, tables
    sw = os.path.join(TMP, "gimp.jpg"); im.save(sw, exif=with_thumbnail(ex.tobytes(), exif_thumbnail(im)), qtables=im.quantization)
    ids = [x.rule_id for x in m.check_metadata("T1", doc(sw), "2026-10-20", photo=True)]
    assert ids == ["F-META-EXIF-SOFTWARE"], ids
    ed = Image.open(ph).convert("RGB"); ImageDraw.Draw(ed).rectangle([300, 100, 620, 400], fill=(250, 250, 250))
    th = exif_thumbnail(Image.open(ph)); ep = os.path.join(TMP, "edited.jpg")
    ed.save(ep, exif=with_thumbnail(Image.open(ph).getexif().tobytes(), th), qtables=Image.open(ph).quantization)
    assert [x.rule_id for x in m.check_metadata("T1", doc(ep), "2026-10-20", photo=True)] == ["F-META-EXIF-THUMB"]
    if not os.path.exists("data/demo/apps/APP-17.json"):
        raise RuntimeError("run: python -m pramaan.synth.bundles  first")
    injected = {("APP-10", "affidavit_2"), ("APP-16", "fire_cert"), ("APP-17", "campus_1.jpg")}
    n = 0
    for mp in sorted(glob.glob("data/demo/apps/*.json")):
        a = Application(**json.load(open(mp)))
        for s in a.documents:
            if (a.app_id, s.slot) not in injected:
                got = m.check_metadata(a.app_id, ingest(s.path, f"{a.app_id}-{s.slot}", s.slot), a.submitted_on); n += 1
                assert got == [], (a.app_id, s.slot, [(x.rule_id, x.reason) for x in got])
        for q in a.photos:
            if (a.app_id, os.path.basename(q)) not in injected:
                got = m.check_metadata(a.app_id, doc(q), a.submitted_on, photo=True); n += 1
                assert got == [], (a.app_id, q, [(x.rule_id, x.reason) for x in got])
    assert n > 100, n


def t_table_borderless(m):
    """classify_extract (WK15 regression): layout B (no grid lines) EoA table with wrapped Level / Program / University cells.
    Before the fix the course came out as 'POST MBA Sample' (APP-17) -> X-PROG-NOT-APPROVED."""
    from pramaan.ingest import ingest
    from pramaan.util import norm_name
    for k in range(3):                                          # fresh synthetic layout-B letters
        rng = random.Random(500 + k); inst = C.make_institute(rng); det = D.default_details(rng, inst)
        r = D.render_pdf("eoa_letter", "B", inst, det, os.path.join(TMP, f"eoaB{k}.pdf"))
        got = m.classify_and_extract(ingest(r["path"], "T1-eoa_letter")).tables.get("programs")
        assert [{c: norm_name(v) for c, v in x.items()} for x in got] == [{c: norm_name(v) for c, v in x.items()} for x in r["tables"]["programs"]], got
    p = "data/demo/docs/APP-17/eoa_letter.pdf"                  # the exact letter from the bug report
    if not os.path.exists(p):
        raise RuntimeError("run: python -m pramaan.synth.bundles  first")
    got = m.classify_and_extract(ingest(p, "APP-17-eoa_letter")).tables["programs"]
    assert [x["course"] for x in got] == ["CIVIL ENGINEERING", "MBA"] and all(x["intake_curr"] == "120" for x in got), got


def t_reuse_photo_strict(m):
    """reuse (WK15): two DIFFERENT synthetic campus photos -> no X-REUSE-PHOTO; a re-saved JPEG copy -> X-REUSE-PHOTO."""
    from PIL import Image
    from pramaan.synth.photos import photo
    db = os.path.join(TMP, "reuse_strict.db")
    if os.path.exists(db):
        os.remove(db)
    p1, p2, p3 = (os.path.join(TMP, f"rs{i}.jpg") for i in range(3))
    photo(p1, random.Random(11), 28.6, 77.2); photo(p2, random.Random(12), 28.6, 77.2)
    Image.open(p1).convert("RGB").save(p3, quality=60)                     # re-saved copy of p1: different bytes
    assert open(p1, "rb").read() != open(p3, "rb").read()
    a = APP.model_copy(update={"app_id": "RA", "photos": [p1]})
    b = APP.model_copy(update={"app_id": "RB", "photos": [p2]})
    c = APP.model_copy(update={"app_id": "RC", "photos": [p3]})
    assert m.check_reuse(a, [], db) == []
    assert [f.rule_id for f in m.check_reuse(b, [], db)] == []              # unrelated photo: no match
    out = m.check_reuse(c, [], db)
    assert [f.rule_id for f in out] == ["X-REUSE-PHOTO"] and "RA" in out[0].evidence[0].text, [(f.rule_id, f.reason) for f in out]


def t_reference_sync(m):
    """WK16: every module that exists in BOTH pramaan/ and reference/pramaan/ (and dashboard/app.py) must be identical,
    so python -m tools.use_reference can never silently undo work. Prints which files differ."""
    import filecmp
    pairs = [(os.path.join("pramaan", f), os.path.join("reference", "pramaan", f))
             for f in sorted(os.listdir(os.path.join("reference", "pramaan"))) if f.endswith(".py")]
    pairs.append((os.path.join("dashboard", "app.py"), os.path.join("reference", "dashboard", "app.py")))
    bad = [a for a, b in pairs if os.path.exists(a) and os.path.exists(b) and not filecmp.cmp(a, b, shallow=False)]
    if bad:
        print("  differ from reference/: " + ", ".join(bad) + "  (copy the working version into reference/)")
    assert not bad, bad


def t_audit_close(m):
    """WK17 (Windows WinError 32): AuditLog leaves no open SQLite handle - close(), `with`, and deleting the folder
    right after must not raise, and no 'unclosed database' ResourceWarning may be emitted."""
    import gc, shutil, warnings
    d = tempfile.mkdtemp()
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        log = m.AuditLog(os.path.join(d, "audit.db")); log.append("t", "system", "x", None, {"i": 1}); log.close(); log.close()
        with m.AuditLog(os.path.join(d, "audit.db")) as l2:
            l2.append("t", "system", "y", None, {}); assert l2.verify_chain() == (True, None) and len(l2.rows()) == 2
        shutil.rmtree(d)                                            # must not raise (fails on Windows if a handle is open)
        del log, l2; gc.collect()
    leaks = [str(x.message) for x in w if issubclass(x.category, ResourceWarning)]
    assert not leaks and not os.path.exists(d), leaks

class _Skip(Exception):
    pass


def t_occupancy(m):
    """WK21: occupancy_cert renders in all 3 layouts, classifies, every field extracts; the pipeline-facing rules fire."""
    from pramaan.classify_extract import classify_and_extract
    from pramaan.ingest import ingest
    rng = random.Random(21); inst = C.make_institute(rng, 2026); det = D.default_details(rng, inst)
    for lay in D.LAYOUTS:
        r = D.render_pdf("occupancy_cert", lay, inst, det, os.path.join(TMP, f"occ_{lay}.pdf"))
        d = classify_and_extract(ingest(r["path"], f"T1-occ{lay}"))
        assert d.doc_type == "occupancy_cert", (lay, d.doc_type)
        got = {k: (d.fields[k].value if k in d.fields else None) for k in r["truth"]}
        assert got == r["truth"], (lay, got, r["truth"])
    rp = "config/rulepack_eoa_existing.yaml"
    assert any(x.rule_id == "R-MISS-occupancy_cert" for x in m.run_rules(APP, [], [], None, rp, TODAY))
    old = _doc("occupancy_cert", certificate_kind="Provisional", issue_date="2023-10-26")
    assert [x.rule_id for x in m.run_rules(APP, [old], [], None, rp, TODAY) if "occupancy" in x.rule_id] == ["R-PROV-occupancy_cert"]


def t_fuzzy(m):
    """WK22 fuzzy labels (OCR only): up to 2 errors on long labels, 1 on short, 0 below 4 chars; separators; date chars."""
    assert m.label_matches("perod", "period") and m.label_matches("Date of lssue:", "Date of Issue")
    assert m.label_matches("Valid Untl", "Valid Until") and not m.label_matches("Issued by", "Valid Until")
    assert not m.label_matches("Na", "No") and not m.label_matches("Datum of Iss", "Date of Issue")    # 0 errors / 3 errors
    assert m.repair_line("Certificate No:: FS/2025/1", ["Certificate No"]) == "Certificate No: FS/2025/1"
    assert m.repair_line("Certifcate Na: FS/1", ["Certificate No"]) == "Certificate No: FS/1"
    assert m.repair_line("No.= 138 Date: 20-07-2025", []) == "No.: 138 Date: 20-07-2025"
    alts = ["Valid Until", "Valid up to", "Valid upto"]           # an exact label must never be swapped for a near one
    assert m.repair_line("Valid Until: 19-07-2028", alts) == "Valid Until: 19-07-2028"
    assert m.repair_line("Vaiid Untll: 19-07-2028", alts) == "Valid Until: 19-07-2028"
    assert m.fix_date_chars("2O-ll-2025") == "20-11-2025" and m.fix_date_chars("09-Nov-2025") == "09-Nov-2025"
    assert m.fix_date_chars("Office of the Chief Fire Officer") == "Office of the Chief Fire Officer"
    from pramaan.classify_extract import _norm_value
    assert _norm_value("2O-1l-2O25", "date")[0] == "2025-11-20"


MODULE = {"signature": "forensics", "priority": "priority", "reuse": "reuse", "area": "rules", "issuer_webhook": "issuer_async", "retention": "audit", "masking": "privacy",
          "metadata": "metadata_forensics", "table_borderless": "classify_extract",
          "reuse_photo_strict": "reuse", "reference_sync": "schemas",
          "audit_close": "audit", "occupancy": "rules", "fuzzy": "fuzzy"}   # test name -> module in pramaan/


TESTS = {"ingest": t_ingest, "classify_extract": t_classify_extract, "rules": t_rules, "crosscheck": t_crosscheck,
         "triage": t_triage, "audit": t_audit, "report": t_report, "pipeline": t_pipeline,
         "signature": t_signature, "priority": t_priority, "reuse": t_reuse,
         "area": t_area, "issuer_webhook": t_issuer_webhook,
         "retention": t_retention, "masking": t_masking,
         "metadata": t_metadata, "table_borderless": t_table_borderless,
         "reuse_photo_strict": t_reuse_photo_strict,
         "reference_sync": t_reference_sync, "audit_close": t_audit_close,
         "occupancy": t_occupancy, "fuzzy": t_fuzzy}

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
