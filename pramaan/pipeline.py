"""run_application(manifest) -> ApplicationResult, plus report files and audit-log rows. The one entry point.
CLI:  python -m pramaan.pipeline data/demo/apps/*.json --today 2026-10-26
OWNER: Aryan (reference version)."""
from __future__ import annotations

import argparse
import glob
import json
import os
import time
from contextlib import contextmanager
from datetime import date

import yaml

from .audit import AuditLog
from .classify_extract import classify_and_extract, load_specs
from .crosscheck import run_crosscheck
from .forensics import pdf_structure_checks, signature_check
from .ingest import ingest
from .issuer import load_records, verify_document
from .photo_check import check_photos
from .priority import score as priority_score
from .report import build_report
from .reuse import check_reuse
from .rules import run_rules
from .schemas import DOC_TYPES, Application, ApplicationResult, Evidence, Finding
from .tamper_model import available, tamper_check
from .triage import assign_lane, make_alerts
from .util import now_iso, sha256_file

SYSTEM = ("pramaan-pipeline", "system")


@contextmanager
def _step(timings: dict | None, name: str):
    """Optional timing hook (tools/scale_test.py). Adds seconds to timings[name]; no effect on outputs."""
    t = time.perf_counter()
    try:
        yield
    finally:
        if timings is not None:
            timings[name] = timings.get(name, 0.0) + time.perf_counter() - t


def _settings(path="config/settings.yaml") -> dict:
    try:
        with open(path) as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _vfinding(app, v):
    lane = {"mismatch_detected": "human_review", "expired": "return_for_rectification", "manual_review_required": "human_review"}.get(v.status)
    if lane is None or v.method == "digital_signature":
        return None
    sev = "medium" if v.status != "manual_review_required" else "low"
    return Finding(finding_id=f"{app.app_id}-V-{v.method}-{v.doc_id}", app_id=app.app_id, doc_id=v.doc_id, source="verification",
                   rule_id=f"V-{v.method}", title=f"Verification: {v.status.replace('_', ' ')} ({v.source})",
                   reason=(v.note or "; ".join(f"{c.field}: submitted '{c.submitted}' vs source '{c.returned}'" for c in v.compared if not c.match))[:400],
                   severity=sev, confidence=0.8, lane=lane, evidence=[Evidence(doc_id=v.doc_id, page=1, text=(v.reference or "")[:200])])


def run_application(manifest_path: str, out_dir: str = "output", today: date | None = None, audit_db: str = "output/audit.db",
                    records_path: str = "data/aicte_records.json", specs_dir: str = "config/doc_specs",
                    rulepack: str = "config/rulepack_eoa_existing.yaml", weights: str = "data/models/tamper_unet.pt",
                    reuse_db: str | None = None, trust_dir: str = "config/trust", timings: dict | None = None) -> ApplicationResult:
    t0, today = time.time(), today or date.today()
    st = _settings()
    with open(manifest_path) as f:
        app = Application(**json.load(f))
    log, notes = AuditLog(audit_db), []
    log.append(*SYSTEM, "application received", app.app_id, {"manifest": manifest_path, "documents": len(app.documents)})
    specs = {s["doc_type"]: s for s in load_specs(specs_dir)}
    records = load_records(records_path)
    record = records.get(app.permanent_id)
    log.append(*SYSTEM, "record checked", app.app_id, {"source": "MOCK AICTE records", "found": record is not None})
    if record is None:
        notes.append("No AICTE record found for this Permanent Id in the mock records; record-based checks skipped.")
    trust = sorted(glob.glob(os.path.join(trust_dir, "*.pem")))
    docs, findings, vers = [], [], []
    for slot in app.documents:
        with _step(timings, "ingest"):
            d = ingest(slot.path, f"{app.app_id}-{slot.slot}", slot.slot)
        with _step(timings, "classify_extract"):
            d = classify_and_extract(d, specs_dir)
        docs.append(d)
        log.append(*SYSTEM, "document read", app.app_id, {"doc_id": d.doc_id, "sha256": d.sha256, "type": d.doc_type,
                                                         "confidence": d.doc_type_confidence, "fields": sorted(d.fields)})
        if d.doc_type == "unclassified":
            findings.append(Finding(finding_id=f"{app.app_id}-R-UNCLASSIFIED-{d.doc_id}", app_id=app.app_id, doc_id=d.doc_id, source="rule",
                                    rule_id="R-UNCLASSIFIED", title="Document type not recognised",
                                    reason=f"{d.filename} could not be matched to any known document type.{' ' + d.metadata['error'] if 'error' in d.metadata else ''}",
                                    severity="low", lane="human_review", evidence=[Evidence(doc_id=d.doc_id, page=1, text=d.filename)]))
        elif slot.slot in DOC_TYPES and d.doc_type != slot.slot and d.doc_type_confidence >= 0.5:
            findings.append(Finding(finding_id=f"{app.app_id}-X-SLOT-{d.doc_id}", app_id=app.app_id, doc_id=d.doc_id, source="crosscheck",
                                    rule_id="X-SLOT", title="Document uploaded under the wrong checklist item",
                                    reason=f"Uploaded as '{slot.slot}' but it reads like '{d.doc_type}'.", severity="medium", lane="human_review",
                                    evidence=[Evidence(doc_id=d.doc_id, page=1, text=d.filename)]))
        with _step(timings, "forensics"):
            findings += pdf_structure_checks(app.app_id, d, specs.get(d.doc_type, {}))
            if d.doc_type == "affidavit_2" or d.metadata.get("has_signature_field"):
                vers.append(signature_check(d, trust))
            findings += tamper_check(app.app_id, d, weights, float(st.get("tamper_threshold", 0.5)))
        with _step(timings, "verification"):
            vers += verify_document(d, app, records)
    if not available(weights):
        notes.append("Tamper model not run (weights or torch missing on this machine).")
    for v in vers:
        log.append(*SYSTEM, "source response", app.app_id, {"doc_id": v.doc_id, "method": v.method, "source": v.source,
                                                           "mock": v.mock, "status": v.status, "payload_hash": v.payload_hash})
        if (f := _vfinding(app, v)):
            findings.append(f)
    with _step(timings, "rules"):
        findings += run_rules(app, docs, vers, record, rulepack, today)
    log.append(*SYSTEM, "rules applied", app.app_id, {"rulepack": rulepack, "sha256": sha256_file(rulepack), "today": today.isoformat()})
    with _step(timings, "crosscheck"):
        findings += run_crosscheck(app, docs, record, today)
    reuse_db = reuse_db or os.path.join(os.path.dirname(audit_db) or ".", "reuse.db")
    with _step(timings, "reuse"):
        findings += check_reuse(app, docs, reuse_db)
    log.append(*SYSTEM, "record checked", app.app_id, {"source": "reuse index", "db": reuse_db})
    if app.photos:
        with _step(timings, "photos"):
            findings += check_photos(app, today, float(st.get("photo_max_km", 1.0)), float(st.get("blur_threshold", 60.0)))
    seen: dict = {}
    for i, f in enumerate(findings):                       # make finding ids unique
        n = seen.get(f.finding_id, 0); seen[f.finding_id] = n + 1
        if n:
            findings[i] = f.model_copy(update={"finding_id": f"{f.finding_id}-{n + 1}"})
    lane = assign_lane(findings)
    alerts = make_alerts(app, findings, vers, today)
    for a in alerts:
        log.append(*SYSTEM, "alert", app.app_id, {"alert_id": a.alert_id, "kind": a.kind, "due_by": a.due_by})
    res = ApplicationResult(app_id=app.app_id, category=app.category, academic_year=app.academic_year, run_at=now_iso(), lane=lane,
                            documents=docs, findings=findings, verifications=vers, alerts=alerts, audit_head_hash="",
                            seconds_taken=round(time.time() - t0, 2), notes=notes)
    pr, why = priority_score(res, record, st, today)
    head = log.append(*SYSTEM, "observation", app.app_id, {"lane": lane, "findings": len(findings), "advisory": True,
                                                          "priority": pr, "priority_weights": "designed, assumption"})
    res = res.model_copy(update={"priority": pr, "priority_reasons": why, "audit_head_hash": head})
    with _step(timings, "report"):
        build_report(res, out_dir)
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("manifests", nargs="+"); ap.add_argument("--out", default="output"); ap.add_argument("--today", default=None)
    a = ap.parse_args()
    td = date.fromisoformat(a.today) if a.today else None
    for m in a.manifests:
        r = run_application(m, a.out, td)
        print(f"{r.app_id}: {r.lane}  priority={r.priority:.2f}  findings={len(r.findings)} alerts={len(r.alerts)}  {r.seconds_taken}s  -> {a.out}/{r.app_id}.report.html")
