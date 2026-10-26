"""WK23-14 Institute self-check (pre-submission). precheck(manifest_path, work_dir) runs the SAME engine in "precheck" mode:
its own audit and reuse databases inside work_dir (nothing reaches the officer's audit log, no decision is recorded, and the
self-check never enters the reuse index), result notes start with "SELF-CHECK". todo(result) -> a plain-words to-do list.
OWNER: Aryan."""
from __future__ import annotations

import os
from datetime import date

from .i18n import t
from .letters import DOC_LABEL, _doc_type, _to_submit
from .pipeline import run_application
from .schemas import ApplicationResult
from .util import add_years, parse_date

MARK = "SELF-CHECK: run by the institute before submission; not a decision and not part of the officer's file."


def precheck(manifest_path: str, work_dir: str, today: date | None = None) -> ApplicationResult:
    os.makedirs(work_dir, exist_ok=True)
    r = run_application(manifest_path, work_dir, today, os.path.join(work_dir, "selfcheck_audit.db"),
                        reuse_db=os.path.join(work_dir, "selfcheck_reuse.db"))
    return r.model_copy(update={"notes": [MARK] + r.notes})


def _field(result, doc_type, f):
    d = next((d for d in result.documents if d.doc_type == doc_type), None)
    x = d.fields.get(f) if d else None
    return parse_date(x.value) if x and x.value else None


def todo(result: ApplicationResult, today: date | None = None, lang: str = "en") -> list[str]:
    today = today or date.today()
    out = []
    for f in result.findings:
        dt = _doc_type(f.rule_id, f.doc_id, result)
        label = DOC_LABEL.get(dt, "document") if dt else "application"
        if f.rule_id == "R-EXP-structural_cert" and _field(result, "structural_cert", "issue_date"):
            iss = _field(result, "structural_cert", "issue_date")
            d = next(d for d in result.documents if d.doc_type == "structural_cert")
            stated = "".join(ch for ch in (d.fields["validity_years"].value if "validity_years" in d.fields else "") if ch.isdigit())
            allowed = min(5, int(stated)) if stated else 5          # same as R-EXP-structural_cert: 5 years or less if stated
            out.append(t(f"Your Structural Stability Certificate is {(today - iss).days // 365} years old: upload one issued after "
                         f"{add_years(today, -allowed).isoformat()}.", lang))
        elif f.rule_id == "R-EXP-fire_cert" and _field(result, "fire_cert", "valid_until"):
            out.append(t(f"Your Fire Safety Certificate expired on {_field(result, 'fire_cert', 'valid_until').isoformat()}: "
                         "upload the renewed certificate.", lang))
        elif f.lane == "return_for_rectification":
            out.append(f"{t(f.title, lang)}: {_to_submit(f.rule_id, label, lang)}")
        elif f.lane == "human_review":
            out.append(t(f"Please check your {label}: {f.title.lower()}. An officer will look at this after submission.", lang))
    return out or [t("Nothing to fix was found. You can submit.", lang)]
