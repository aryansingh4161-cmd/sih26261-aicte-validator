"""MOCK verification adapters (designed for integration; NO real AICTE, DigiLocker, issuer or API connection).
verify_document(doc, app, records) -> list[VerificationResult]. Every result has mock=True and source "MOCK ...".
OWNER: Nishchal (reference version)."""
from __future__ import annotations

import json
import os

from .schemas import Application, CompareItem, DocumentRecord, VerificationResult
from .util import now_iso, sha256_text, similarity

MOCK_DIR = "data/mock_issuers"


def load_records(path: str = "data/aicte_records.json") -> dict:
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return {}


def _issuer_db(name: str) -> dict:
    try:
        with open(os.path.join(MOCK_DIR, f"{name}.json")) as f:
            return json.load(f)
    except Exception:
        return {}


def _res(doc, method, source, status, ref=None, compared=None, note=""):
    payload = json.dumps({"ref": ref, "status": status, "cmp": [c.model_dump() for c in compared or []]}, sort_keys=True)
    return VerificationResult(doc_id=doc.doc_id, method=method, source=f"MOCK {source}", mock=True, timestamp=now_iso(),
                              status=status, reference=ref, compared=compared or [], note=note, payload_hash=sha256_text(payload))


def _v(doc, f):
    x = doc.fields.get(f)
    return x.value if x else None


def verify_document(doc: DocumentRecord, app: Application, records: dict) -> list[VerificationResult]:
    rec = records.get(app.permanent_id)
    if doc.doc_type == "eoa_letter":
        if rec is None:
            return [_res(doc, "reference_number", "AICTE records", "source_unavailable", _v(doc, "file_no"), note="no record for this Permanent Id in the mock records")]
        cmp = [CompareItem(field="institute_name", submitted=_v(doc, "institute_name"), returned=rec.get("institute_name"),
                           match=similarity(_v(doc, "institute_name"), rec.get("institute_name")) >= 0.85),
               CompareItem(field="academic_year", submitted=_v(doc, "academic_year"), returned=rec.get("last_eoa_year"),
                           match=_v(doc, "academic_year") == rec.get("last_eoa_year"))]
        st = "verified" if all(c.match for c in cmp) else "mismatch_detected"
        return [_res(doc, "reference_number", "AICTE records", st, _v(doc, "file_no"), cmp)]
    if doc.doc_type == "fire_cert":
        db = _issuer_db("fire")
        no = _v(doc, "certificate_no")
        if db.get("_down"):
            return [_res(doc, "issuer_portal", "Fire department portal", "source_unavailable", no, note="mock portal is down (simulated)")]
        if not no:
            return [_res(doc, "issuer_portal", "Fire department portal", "manual_review_required", None, note="certificate number not read")]
        if no not in db:
            return [_res(doc, "issuer_portal", "Fire department portal", "verification_pending", no, note="no answer yet from issuer (simulated)")]
        r = db[no]
        cmp = [CompareItem(field="valid_until", submitted=_v(doc, "valid_until"), returned=r.get("valid_until"), match=_v(doc, "valid_until") == r.get("valid_until")),
               CompareItem(field="institute_name", submitted=_v(doc, "institute_name"), returned=r.get("institute_name"),
                           match=similarity(_v(doc, "institute_name"), r.get("institute_name")) >= 0.85)]
        st = "verified" if all(c.match for c in cmp) else "mismatch_detected"
        return [_res(doc, "issuer_portal", "Fire department portal", st, no, cmp)]
    if doc.doc_type == "noc_format2":
        db = _issuer_db("university")
        ref = _v(doc, "ref_no")
        if ref in db:
            ok = db[ref].get("institute_name") and similarity(db[ref]["institute_name"], _v(doc, "institute_name")) >= 0.85
            return [_res(doc, "digital_repository", "University repository", "verified" if ok else "mismatch_detected", ref,
                         [CompareItem(field="institute_name", submitted=_v(doc, "institute_name"), returned=db[ref].get("institute_name"), match=bool(ok))])]
        return [_res(doc, "digital_repository", "University repository", "verification_pending", ref, note="not found in mock repository yet")]
    return []
