"""WK23-9 Verification status board: one row per document and source, status in plain words, when checked, what was compared.
Rows = the verifications the pipeline already made + three display-only MOCK adapters (they do not change findings or lanes):
  MOCK municipal occupancy register (occupancy_cert number), MOCK NBA (accredited courses for the Permanent Id), MOCK DigiLocker
  (issued fire / occupancy certificates; needs the institute's consent flag `declared.consent_digilocker`).
Status words: verified / pending / mismatch / unavailable / consent not given. Every MOCK row says MOCK (docs/ADAPTERS.md).
OWNER: Aryan."""
from __future__ import annotations

import json
import os

from .i18n import t
from .schemas import Application, ApplicationResult
from .util import now_iso, similarity

WORD = {"verified": "verified", "verification_pending": "pending", "manual_review_required": "pending", "mismatch_detected": "mismatch",
        "expired": "mismatch", "source_unavailable": "unavailable"}


def _mock(name: str, data_dir: str = "data/mock_issuers") -> dict | None:
    p = os.path.join(data_dir, f"{name}.json")
    return json.load(open(p)) if os.path.exists(p) else None


def _field(doc, f):
    x = doc.fields.get(f)
    return (x.value or "") if x else ""


class Adapter:
    """Interface: name, mock (bool), check(app, result) -> list of rows. A real API replaces one class (docs/ADAPTERS.md)."""
    name, mock = "adapter", True

    def check(self, app: Application, result: ApplicationResult) -> list[dict]:
        raise NotImplementedError


def row(doc_id, source, status, compared="", mock=True, when=None):
    return {"document": doc_id, "source": ("MOCK " if mock and not source.startswith("MOCK") else "") + source,
            "status": status, "checked_at": when or now_iso(), "compared": compared, "mock": mock}


class MunicipalRegister(Adapter):
    name = "municipal occupancy register"

    def check(self, app, result):
        db = _mock("occupancy")
        out = []
        for d in (d for d in result.documents if d.doc_type == "occupancy_cert"):
            no = _field(d, "certificate_no")
            if db is None:
                out.append(row(d.doc_id, self.name, "unavailable"))
            elif no not in db:
                out.append(row(d.doc_id, self.name, "pending", f"certificate {no}: not in the register yet"))
            else:
                ok = similarity(db[no]["institute_name"], _field(d, "institute_name")) >= 0.85 and db[no]["issue_date"] == _field(d, "issue_date")
                out.append(row(d.doc_id, self.name, "verified" if ok else "mismatch", f"certificate {no}: institute name, issue date"))
        return out


class NBA(Adapter):
    name = "NBA accreditation"

    def check(self, app, result):
        db = _mock("nba")
        if db is None:
            return [row(app.app_id, self.name, "unavailable")]
        rec = db.get(app.permanent_id)
        if rec is None:
            return [row(app.app_id, self.name, "pending", "no NBA record for this Permanent Id")]
        n = len(rec.get("accredited_courses", []))
        return [row(app.app_id, self.name, "verified", f"{n} accredited course(s) on record (information only)")]


class DigiLocker(Adapter):
    name = "DigiLocker issued documents"

    def check(self, app, result):
        docs = [d for d in result.documents if d.doc_type in ("fire_cert", "occupancy_cert")]
        if not app.declared.get("consent_digilocker"):
            return [row(d.doc_id, self.name, "consent not given", "the institute has not given consent") for d in docs]
        db = _mock("digilocker")
        if db is None:
            return [row(d.doc_id, self.name, "unavailable") for d in docs]
        issued = db.get(app.permanent_id, [])
        return [row(d.doc_id, self.name, "verified" if d.doc_type in issued else "pending", f"{d.doc_type} issued to this Permanent Id")
                for d in docs]


ADAPTERS = [MunicipalRegister(), NBA(), DigiLocker()]


def board(result: ApplicationResult, app: Application, lang: str = "en") -> list[dict]:
    rows = [row(v.doc_id, v.source, WORD.get(v.status, v.status), ", ".join(c.field for c in v.compared) or v.note, v.mock, v.timestamp)
            for v in result.verifications]
    for a in ADAPTERS:
        rows += a.check(app, result)
    for r in rows:
        r["status"] = t(r["status"], lang)
    return rows
