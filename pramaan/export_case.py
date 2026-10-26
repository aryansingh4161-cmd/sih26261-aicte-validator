"""WK23-13 RTI / appeal case export: one ZIP per application with
  manifest.json, hashes.json (SHA-256 of every document), documents/ (ONLY synthetic demo files under data/demo/),
  result.json (findings, verifications, lane), evidence/*.png (crops around each finding's box), letter_of_deficiency.txt
  (the officer's finalised text from the audit log, else the draft), decisions.json (officer rows + feedback), audit_slice.json
  (this application's audit rows, with prev/hash) + VERIFY.txt, report.html (sealed).
export_case(app_id, out_dir, audit_db, manifests_dir, zip_path) -> zip_path. OWNER: Aryan."""
from __future__ import annotations

import hashlib
import io
import json
import os
import zipfile

from .audit import AuditLog
from .letters import build_lod
from .schemas import ApplicationResult

SYNTHETIC_ROOT = os.path.abspath(os.path.join("data", "demo"))
VERIFY = """How to check this case file
1. Every document's SHA-256 is in hashes.json; recompute it (sha256sum <file>) and compare.
2. audit_slice.json lists this application's audit-log rows in order. Each row's hash = SHA-256 of the UTF-8 JSON array
   [prev_hash, ts, actor, role, action, app_id, detail] (json.dumps, ensure_ascii=False; pramaan/audit.py). The full chain
   (all applications) can be checked with AuditLog(<audit.db>).verify_chain().
3. report.html carries a seal: python -m tools.verify_report report.html --audit <audit.db> prints VALID or ALTERED.
This export is advisory decision support; decisions in it were taken by the named officers.
"""


def _sha(path: str) -> str:
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _crop(doc, ev) -> bytes | None:
    try:
        from PIL import Image
        if doc.path.lower().endswith((".jpg", ".jpeg", ".png")):
            img = Image.open(doc.path).convert("RGB")
        else:
            from .synth.raster import render_page
            img = render_page(doc.path, dpi=110, page=ev.page - 1)
        W, H = img.size
        b = ev.bbox
        box = (0, 0, W, min(H, 400)) if b is None else (max(0, int(b.x0 * W) - 40), max(0, int(b.y0 * H) - 40),
                                                         min(W, int(b.x1 * W) + 40), min(H, int(b.y1 * H) + 40))
        buf = io.BytesIO(); img.crop(box).save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return None


def export_case(app_id: str, out_dir: str = "output", audit_db: str = "output/audit.db", manifests_dir: str = "data/demo/apps",
                zip_path: str | None = None, institute_copy: bool = False) -> str:
    """institute_copy=True (WK25): for the institute; internal notes, their audit rows and officer feedback are left out.
    The officer copy (default) also carries notes.json."""
    res = ApplicationResult.model_validate_json(open(os.path.join(out_dir, f"{app_id}.result.json")).read())
    man_p = os.path.join(manifests_dir, f"{app_id}.json")
    man = json.load(open(man_p)) if os.path.exists(man_p) else {}
    zip_path = zip_path or os.path.join(out_dir, f"{app_id}_case.zip")
    with AuditLog(audit_db) as log:
        rows = log.rows(app_id)
    final = [r for r in rows if r["action"] == "letter of deficiency finalised"]
    lod = json.loads(final[-1]["detail"]).get("text") if final else build_lod(res)["text"] + "\n(draft: no finalised letter in the audit log)"
    if institute_copy:                                          # internal notes stay inside the office
        rows = [r for r in rows if r["action"] != "internal note" and not r["action"].startswith("feedback")]
    decisions = [r for r in rows if r["role"] not in ("system", "external_source")]
    try:
        from .feedback import rows as fb_rows
        feedback = [] if institute_copy else [r for r in fb_rows(audit_db) if r["app_id"] == app_id]
    except Exception:
        feedback = []
    docs = {d.doc_id: d for d in res.documents}
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(man, indent=2))
        z.writestr("hashes.json", json.dumps({d.doc_id: {"file": os.path.basename(d.path), "sha256": d.sha256} for d in res.documents}, indent=2))
        for d in res.documents:
            if os.path.abspath(d.path).startswith(SYNTHETIC_ROOT) and os.path.exists(d.path):
                z.write(d.path, f"documents/{os.path.basename(d.path)}")
        z.writestr("result.json", res.model_dump_json(indent=2))
        for i, f in enumerate(res.findings):
            for j, ev in enumerate(f.evidence[:2]):
                png = _crop(docs[ev.doc_id], ev) if ev.doc_id in docs else None
                if png:
                    z.writestr(f"evidence/{i + 1:02d}_{f.rule_id}_{j + 1}.png", png)
        z.writestr("letter_of_deficiency.txt", lod)
        z.writestr("decisions.json", json.dumps({"officer_audit_rows": decisions, "feedback": feedback}, indent=2))
        z.writestr("audit_slice.json", json.dumps(rows, indent=2))
        z.writestr("VERIFY.txt", VERIFY)
        if not institute_copy:
            from .notes import list_notes
            z.writestr("notes.json", json.dumps(list_notes(audit_db, app_id), indent=2))
        rep = os.path.join(out_dir, f"{app_id}.report.html")
        if os.path.exists(rep):
            z.write(rep, "report.html")
    return zip_path
