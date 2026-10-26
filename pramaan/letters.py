"""WK23-1 Letter of Deficiency (LoD), auto-drafted from the findings. Advisory draft: the officer edits and signs it.
build_lod(result) -> {"deficiencies": [...], "notes": [...], "text": str, "html": str}
  - every return_for_rectification finding -> one numbered deficiency: what is wrong, which document, the Handbook clause
    quoted verbatim (aph_clause, when the rule has one) and what to submit;
  - human_review findings are NOT in the letter: they go to the officer's internal-notes annex; info findings are left out.
export_docx(lod, path) writes a .docx (python-docx). save_final(log, user, app_id, text) stores the officer's edited text in
the audit log. Every user-visible string goes through i18n.t(). OWNER: Aryan."""
from __future__ import annotations

import hashlib
import html as H
from datetime import date

from .i18n import t
from .schemas import ApplicationResult

DOC_LABEL = {"eoa_letter": "previous Extension of Approval letter", "affidavit_2": "Affidavit 2", "noc_format2": "University NOC (Format 2)",
             "fire_cert": "Fire Safety Certificate", "structural_cert": "Structural Stability Certificate",
             "area_statement": "built-up area statement", "occupancy_cert": "Occupancy / Completion Certificate"}
FOOTER = "Draft prepared by Pramaan (advisory). To be reviewed and signed by the competent officer."


def _doc_type(rule_id: str, doc_id: str | None, result: ApplicationResult) -> str | None:
    d = next((d for d in result.documents if d.doc_id == doc_id), None)
    if d:
        return d.doc_type
    for dt in DOC_LABEL:                                      # missing documents have no doc_id: read it from the rule id
        if rule_id.endswith(dt) or f"-{dt}-" in rule_id:
            return dt
    return None


def _to_submit(rule_id: str, label: str, lang: str) -> str:
    if rule_id.startswith("R-MISS"):
        return t(f"Upload a valid {label}.", lang)
    if rule_id.startswith(("R-EXP", "R-PROV")):
        return t(f"Upload a {label} that is valid on the date of submission.", lang)
    if rule_id.startswith("R-FLD"):
        return t(f"Upload a corrected {label}.", lang)
    if rule_id.startswith("R-SIG"):
        return t(f"Upload the {label} with a valid digital signature.", lang)
    if rule_id.startswith("R-REC"):
        return t("Upload the proof of payment made on the AICTE portal for this academic year.", lang)
    if rule_id.startswith("R-AREA"):
        return t("Submit a revised built-up area statement showing the required area, or the building plan approved for it.", lang)
    return t("Submit documents that address this deficiency.", lang)


def build_lod(result: ApplicationResult, institute: str = "[Institute name]", permanent_id: str = "[Permanent Id]",
              file_no: str = "[File No.]", today: date | None = None, lang: str = "en") -> dict:
    defs, notes = [], []
    for f in result.findings:
        dt = _doc_type(f.rule_id, f.doc_id, result)
        label = DOC_LABEL.get(dt, "document") if dt else "application"
        if f.lane == "return_for_rectification":
            defs.append({"n": len(defs) + 1, "rule_id": f.rule_id, "what": t(f.title, lang), "reason": t(f.reason, lang),
                         "document": t(label, lang), "clause": f.aph_clause, "clause_verified": f.clause_verified,
                         "to_submit": _to_submit(f.rule_id, label, lang), "finding_id": f.finding_id})
        elif f.lane == "human_review":
            notes.append({"rule_id": f.rule_id, "what": t(f.title, lang), "reason": t(f.reason, lang), "finding_id": f.finding_id})
    head = [t("LETTER OF DEFICIENCY (DRAFT)", lang), f"{t('File No.', lang)}: {file_no}",
            f"{t('Date', lang)}: {(today or date.today()).isoformat()}", f"{t('Institute', lang)}: {institute}",
            f"{t('Permanent Id', lang)}: {permanent_id}", f"{t('Application', lang)}: {result.app_id} ({result.academic_year})", ""]
    body = [t("The following deficiencies were found in the application for Extension of Approval:", lang)] if defs else \
        [t("No deficiencies were found; no Letter of Deficiency is needed.", lang)]
    for d in defs:
        body += [f"{d['n']}. {d['what']} ({d['document']})", f"   {d['reason']}"]
        if d["clause"]:
            body.append(f"   {t('Handbook', lang)}: \"{d['clause']}\"")              # the official English clause, never translated
            if lang != "en":
                body.append(f"   ({t('gist, machine-translated', lang)}: {t(d['clause'].split(' - ', 1)[-1], lang)})")
        body.append(f"   {t('To submit', lang)}: {d['to_submit']}")
    text = "\n".join(head + body + ["", t(FOOTER, lang)])
    return {"app_id": result.app_id, "deficiencies": defs, "notes": notes, "text": text, "html": to_html(text, notes, lang)}


def to_html(text: str, notes: list, lang: str = "en") -> str:
    annex = "".join(f"<li><b>{H.escape(n['what'])}</b> ({H.escape(n['rule_id'])}): {H.escape(n['reason'])}</li>" for n in notes)
    return (f"<!doctype html><meta charset='utf-8'><title>{H.escape(t('Letter of Deficiency (draft)', lang))}</title>"
            f"<body style='font-family:serif;max-width:46em;margin:2em auto'><pre style='white-space:pre-wrap;font-family:serif'>"
            f"{H.escape(text)}</pre><hr><h3>{H.escape(t('Internal notes for the officer (not sent to the institute)', lang))}</h3>"
            f"<ul>{annex or '<li>' + H.escape(t('None', lang)) + '</li>'}</ul></body>")


def export_docx(text: str, path: str) -> str | None:
    try:
        from docx import Document
    except ImportError:
        return None
    doc = Document()
    for line in text.split("\n"):
        doc.add_paragraph(line)
    doc.save(path)
    return path


def save_final(log, user: dict, app_id: str, text: str, outbox: str | None = None) -> str:
    """The officer's final (possibly edited) text goes into the audit log (this issues the letter and starts the 7-day appeal
    window, appeal.py) and a MOCK notification goes to the outbox; returns the audit row hash."""
    from .outbox import send
    h = log.append(user["id"], user["role"], "letter of deficiency finalised", app_id,
                   {"sha256": hashlib.sha256(text.encode()).hexdigest(), "text": text})
    send("lod_issued", f"institute of {app_id}", {"app_id": app_id, "issued_on": date.today().isoformat()},
         key=f"lod-{app_id}-{h[:12]}", outbox=outbox)
    return h
