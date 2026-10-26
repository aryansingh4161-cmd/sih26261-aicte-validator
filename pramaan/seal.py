"""WK23-6 Report seal. seal_html(html, app_id, log, kind) appends a visible seal (QR code + text) and a machine-readable
comment holding {sha256 of the unsealed HTML, app id, the hash of the audit-log row that recorded the seal, timestamp}.
verify_sealed(text, audit_db) -> "VALID: matches audit entry #n" or "ALTERED: <why>". Any changed byte before the seal
changes the SHA-256. The QR is a PNG data URI (qrcode package; text-only seal if it is missing). OWNER: Aryan."""
from __future__ import annotations

import base64
import hashlib
import html as H
import io
import json

from .util import now_iso

MARK = "<!--PRAMAAN-SEAL-START-->"


def _qr_png(payload: str) -> str | None:
    try:
        import qrcode
    except ImportError:
        return None
    buf = io.BytesIO()
    qrcode.make(payload).save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def seal_html(html: str, app_id: str, log, kind: str = "report") -> str:
    sha = hashlib.sha256(html.encode("utf-8")).hexdigest()
    row = log.append("pramaan", "system", f"{kind} sealed", app_id, {"sha256": sha, "kind": kind})
    payload = json.dumps({"sha256": sha, "app_id": app_id, "audit_entry_hash": row, "ts": now_iso(), "kind": kind}, sort_keys=True)
    qr = _qr_png(payload)
    img = f"<img alt='seal QR code' src='{qr}' style='width:130px;height:130px;float:left;margin-right:12px'>" if qr else ""
    return (html + MARK + f"<div style='border-top:1px solid #999;margin:24px auto;max-width:46em;padding-top:8px;font:12px sans-serif'>"
            f"{img}<b>Sealed by Pramaan</b><br>SHA-256 {sha}<br>Audit entry {row[:16]}...<br>Check: python -m tools.verify_report "
            f"&lt;file&gt;<div style='clear:both'></div></div><!--PRAMAAN-SEAL {H.escape(payload, quote=False)} -->\n")


def seal_file(path: str, app_id: str, log, kind: str = "report") -> str:
    with open(path, encoding="utf-8") as f:
        text = f.read()
    if MARK in text:
        text = text.split(MARK, 1)[0]                     # re-sealing after a rebuild: seal the new content only
    with open(path, "w", encoding="utf-8") as f:
        f.write(seal_html(text, app_id, log, kind))
    return path


def verify_sealed(text: str, audit_db: str) -> str:
    from .audit import AuditLog
    if MARK not in text:
        return "ALTERED: no seal found"
    body, tail = text.split(MARK, 1)
    try:
        payload = json.loads(H.unescape(tail.split("<!--PRAMAAN-SEAL ", 1)[1].rsplit(" -->", 1)[0]))
    except Exception:
        return "ALTERED: the seal cannot be read"
    sha = hashlib.sha256(body.encode("utf-8")).hexdigest()
    if sha != payload.get("sha256"):
        return "ALTERED: content does not match its seal"
    with AuditLog(audit_db) as log:
        ok, bad = log.verify_chain()
        row = next((r for r in log.rows(payload.get("app_id")) if r["hash"] == payload.get("audit_entry_hash")), None)
    if row is None or json.loads(row["detail"]).get("sha256") != sha:
        return "ALTERED: no matching audit entry"
    if not ok:
        return f"ALTERED: audit chain broken at entry #{bad}"
    return f"VALID: matches audit entry #{row['id']}"
