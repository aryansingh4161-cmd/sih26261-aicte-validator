"""MOCK asynchronous issuer flow (designed for integration; no real authority is contacted).
A source that answers LATER (e.g. a fire department) POSTs a signed JSON reply to /webhook/issuer:
  {"doc_id", "method", "reference", "status", "returned": {field: value}, "timestamp", "signature"}
signature = hex HMAC-SHA256 over the canonical JSON of the body WITHOUT "signature" (sort_keys, separators=(",", ":")),
key = issuer_webhook_secret in config/settings.yaml (a DEMO secret). Bad signature -> 401. Same reference+timestamp again -> 409.
A valid reply replaces that document's verification, writes "source response" to the audit log and recomputes the
application's findings, lane, alerts and priority from output/<app_id>.result.json (result + report rewritten).
  python -m pramaan.issuer_async --port 8601 --today 2026-10-26        OWNER: Nishchal / Aryan."""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sqlite3
from contextlib import closing
from datetime import date

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.routing import Route

from .audit import AuditLog
from .issuer import load_records
from .pipeline import _settings, _vfinding
from .priority import score as priority_score
from .report import build_report
from .schemas import VERIFICATION_METHODS, VERIFICATION_STATUSES, Application, ApplicationResult, CompareItem, VerificationResult
from .triage import assign_lane, make_alerts
from .util import now_iso, similarity

ACTOR = ("mock-fire-dept-webhook", "external_source")
SOURCE = "MOCK fire department webhook"
FIELDS = ("doc_id", "method", "reference", "status", "returned", "timestamp")


def canonical(body: dict) -> bytes:
    return json.dumps({k: v for k, v in body.items() if k != "signature"}, sort_keys=True, separators=(",", ":")).encode()


def sign(body: dict, secret: str) -> str:
    return hmac.new(secret.encode(), canonical(body), hashlib.sha256).hexdigest()


def _compare(doc, returned: dict) -> list[CompareItem]:
    out = []
    for f, ret in sorted(returned.items()):
        sub = doc.fields[f].value if doc and f in doc.fields else None
        ok = similarity(sub, ret) >= 0.85 if f.endswith("name") else (sub or "").strip() == str(ret).strip()
        out.append(CompareItem(field=f, submitted=sub, returned=str(ret), match=ok))
    return out


def apply_reply(body: dict, out_dir: str, audit_db: str, manifests_dir: str, records_path: str, today: date) -> ApplicationResult:
    """Fold one verified webhook reply into the stored result. Raises FileNotFoundError / KeyError if the doc is unknown."""
    app_id = body["doc_id"].rsplit("-", 1)[0]
    path = os.path.join(out_dir, f"{app_id}.result.json")
    with open(path) as f:
        res = ApplicationResult.model_validate_json(f.read())
    doc = next((d for d in res.documents if d.doc_id == body["doc_id"]), None)
    if doc is None:
        raise KeyError(body["doc_id"])
    cmp = _compare(doc, body.get("returned") or {})
    status, note = body["status"], "asynchronous reply (MOCK, simulated issuer)"
    if status == "verified" and not all(c.match for c in cmp):
        status, note = "mismatch_detected", note + "; issuer said verified but returned values differ from the document"
    v = VerificationResult(doc_id=doc.doc_id, method=body["method"], source=SOURCE, mock=True, timestamp=body["timestamp"],
                           status=status, reference=body.get("reference"), compared=cmp, note=note,
                           payload_hash=hashlib.sha256(canonical(body)).hexdigest())
    vers = [x for x in res.verifications if not (x.doc_id == v.doc_id and x.method == v.method)] + [v]
    findings = [f for f in res.findings if not (f.doc_id == v.doc_id and f.rule_id == f"V-{v.method}")]
    try:
        with open(os.path.join(manifests_dir, f"{app_id}.json")) as f:
            app = Application(**json.load(f))
    except Exception:
        app = Application(app_id=app_id, category=res.category, academic_year=res.academic_year, permanent_id="", submitted_on="")
    if (vf := _vfinding(app, v)):
        findings.append(vf)
    with AuditLog(audit_db) as log:
        return _fold(log, res, app, app_id, v, vers, findings, records_path, out_dir, today)


def _fold(log, res, app, app_id, v, vers, findings, records_path, out_dir, today) -> ApplicationResult:
    log.append(*ACTOR, "source response", app_id, {"doc_id": v.doc_id, "method": v.method, "source": v.source, "mock": True,
                                                   "status": v.status, "payload_hash": v.payload_hash, "async": True})
    lane, alerts = assign_lane(findings), make_alerts(app, findings, vers, today)
    res = res.model_copy(update={"verifications": vers, "findings": findings, "lane": lane, "alerts": alerts, "run_at": now_iso()})
    pr, why = priority_score(res, load_records(records_path).get(app.permanent_id), _settings(), today)
    head = log.append(*ACTOR, "observation", app_id, {"lane": lane, "findings": len(findings), "advisory": True, "priority": pr,
                                                      "recomputed_after": "asynchronous issuer reply"})
    res = res.model_copy(update={"priority": pr, "priority_reasons": why, "audit_head_hash": head})
    build_report(res, out_dir)
    return res


def create_app(out_dir: str = "output", audit_db: str = "output/audit.db", manifests_dir: str = "data/demo/apps",
               records_path: str = "data/aicte_records.json", today: date | None = None, secret: str | None = None) -> Starlette:
    secret = secret or str(_settings().get("issuer_webhook_secret", ""))
    os.makedirs(out_dir, exist_ok=True)
    seen_db = os.path.join(out_dir, "issuer_webhook.db")

    def deliveries(sql: str, args: tuple = ()) -> None:      # one short connection per call, always closed
        with closing(sqlite3.connect(seen_db)) as c:
            c.execute("CREATE TABLE IF NOT EXISTS deliveries (reference TEXT, timestamp TEXT, received_at TEXT, "
                      "PRIMARY KEY (reference, timestamp))")
            c.execute(sql, args); c.commit()

    deliveries("SELECT 1")

    async def webhook(request: Request):
        try:
            body = json.loads(await request.body())
        except Exception:
            return JSONResponse({"error": "body is not JSON"}, 400)
        if not isinstance(body, dict) or not secret or not hmac.compare_digest(str(body.get("signature", "")), sign(body, secret)):
            return JSONResponse({"error": "bad signature"}, 401)
        if any(k not in body for k in FIELDS) or body["method"] not in VERIFICATION_METHODS or body["status"] not in VERIFICATION_STATUSES:
            return JSONResponse({"error": f"need {FIELDS} with a known method and status"}, 422)
        try:
            deliveries("INSERT INTO deliveries VALUES (?,?,?)", (str(body["reference"]), body["timestamp"], now_iso()))
        except sqlite3.IntegrityError:
            return JSONResponse({"result": "duplicate delivery ignored"}, 409)
        try:
            res = apply_reply(body, out_dir, audit_db, manifests_dir, records_path, today or date.today())
        except Exception as e:                     # not applied -> forget the delivery so the sender can retry
            deliveries("DELETE FROM deliveries WHERE reference=? AND timestamp=?", (str(body["reference"]), body["timestamp"]))
            known = isinstance(e, (FileNotFoundError, KeyError))
            return JSONResponse({"error": f"{'unknown document or no stored result' if known else 'could not apply'}: {e}"[:200]},
                                404 if known else 500)
        v = next(x for x in res.verifications if x.doc_id == body["doc_id"] and x.method == body["method"])
        return JSONResponse({"result": "stored", "app_id": res.app_id, "status": v.status, "lane": res.lane, "mock": True})

    return Starlette(routes=[Route("/webhook/issuer", webhook, methods=["POST"])])


if __name__ == "__main__":
    import uvicorn
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8601); ap.add_argument("--out", default="output"); ap.add_argument("--today", default=None)
    a = ap.parse_args()
    td = date.fromisoformat(a.today) if a.today else None
    print("MOCK issuer webhook (designed for integration; DEMO secret) on http://127.0.0.1:%d/webhook/issuer" % a.port)
    uvicorn.run(create_app(a.out, os.path.join(a.out, "audit.db"), today=td), host="127.0.0.1", port=a.port, log_level="info")
