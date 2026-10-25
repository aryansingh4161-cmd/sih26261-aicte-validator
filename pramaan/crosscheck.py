"""run_crosscheck(app, docs, record, today) -> list[Finding]. Contradictions BETWEEN documents and against the (mock)
AICTE record. Every finding goes to human review: a contradiction is a question for a person, not a verdict.
OWNER: Geetansh (reference version)."""
from __future__ import annotations

import re
from datetime import date

from .schemas import Application, DocumentRecord, Evidence, Finding
from .util import parse_date, similarity

NAME_THR = 0.85
DATE_FIELDS = ("issue_date", "sworn_date", "approval_date", "printed_on")


def _ev(doc, field, extra=""):
    f = doc.fields.get(field)
    if f and f.evidence:
        return f.evidence
    return Evidence(doc_id=doc.doc_id, page=1, text=(extra or doc.filename)[:200])


def _f(app, rid, title, reason, sev, evs, doc_id=None, conf=0.9):
    return Finding(finding_id=f"{app.app_id}-{rid}-{doc_id or 'APP'}", app_id=app.app_id, doc_id=doc_id, source="crosscheck",
                   rule_id=rid, title=title, reason=reason[:400], severity=sev, confidence=conf, lane="human_review",
                   evidence=evs)


def _tok(s):
    return set(re.findall(r"[A-Z]{3,}", (s or "").upper())) - {"AND", "THE", "FOR", "UNDER", "POST", "GRADUATE", "DEMO", "EXAMPLE", "STATE", "TECHNICAL", "UNIVERSITY"}


def _match_course(c, rows, intake=None, used=None):
    """Best unused EoA row for this course; among equally good rows prefer the one with the same intake
    (the same course can appear at two levels, e.g. UG and PG)."""
    t, used = _tok(c), used if used is not None else set()
    cands = []
    for i, r in enumerate(rows):
        if i in used:
            continue
        u = _tok(r.get("course"))
        s = len(t & u) / max(1, len(t | u)) if t else 0.0
        if s >= 0.6:
            cands.append((s, str(r.get("intake_curr")) == str(intake), i))
    if not cands:
        return None
    s, _, i = max(cands, key=lambda x: (round(x[0], 2), x[1]))
    used.add(i)
    return rows[i]


def run_crosscheck(app: Application, docs: list[DocumentRecord], record: dict | None, today: date) -> list[Finding]:
    out: list[Finding] = []
    try:
        ref = (record or {}).get("institute_name") or app.declared.get("institute_name")
        for d in docs:
            nm = d.fields.get("institute_name")
            if ref and nm and nm.value and similarity(nm.value, ref) < NAME_THR:
                out.append(_f(app, "X-NAME", f"Institute name differs on {d.doc_type}",
                              f"'{nm.value}' on this document vs '{ref}' in the application record (similarity {similarity(nm.value, ref):.2f}).",
                              "medium", [_ev(d, "institute_name")], d.doc_id))
            for fld in DATE_FIELDS:
                dt = parse_date(d.fields[fld].value) if fld in d.fields and d.fields[fld].value else None
                if dt and dt > today:
                    out.append(_f(app, "X-FUTURE-DATE", f"Date in the future on {d.doc_type}",
                                  f"{fld} is {dt.isoformat()}, after today ({today.isoformat()}).", "high", [_ev(d, fld)], d.doc_id))
        eoa = next((d for d in docs if d.doc_type == "eoa_letter"), None)
        if eoa:
            pid = eoa.fields.get("permanent_id")
            if pid and pid.value and pid.value != app.permanent_id:
                out.append(_f(app, "X-PERMID", "Previous EoA letter belongs to a different Permanent Id",
                              f"Letter shows {pid.value}; application is for {app.permanent_id}.", "high", [_ev(eoa, "permanent_id")], eoa.doc_id))
        fire = next((d for d in docs if d.doc_type == "fire_cert"), None)
        if fire and "issue_date" in fire.fields and "valid_until" in fire.fields:
            a, b = parse_date(fire.fields["issue_date"].value), parse_date(fire.fields["valid_until"].value)
            if a and b and b <= a:
                out.append(_f(app, "X-FIRE-DATES", "Fire certificate valid-until is before its issue date",
                              f"Issued {a.isoformat()}, valid until {b.isoformat()}.", "high", [_ev(fire, "issue_date"), _ev(fire, "valid_until")], fire.doc_id))
        aff = next((d for d in docs if d.doc_type == "affidavit_2"), None)
        sub = parse_date(app.submitted_on)
        if aff and sub and "sworn_date" in aff.fields:
            sw = parse_date(aff.fields["sworn_date"].value)
            if sw and sw > sub:
                out.append(_f(app, "X-SWORN-AFTER-SUBMIT", "Affidavit sworn after the application was submitted",
                              f"Sworn {sw.isoformat()}, submitted {sub.isoformat()}.", "medium", [_ev(aff, "sworn_date")], aff.doc_id))
        noc = next((d for d in docs if d.doc_type == "noc_format2"), None)
        if noc and eoa and noc.tables.get("programs") and eoa.tables.get("programs"):
            used: set = set()
            for r in noc.tables["programs"]:
                m = _match_course(r.get("course"), eoa.tables["programs"], r.get("intake_curr"), used)
                ev = [Evidence(doc_id=noc.doc_id, page=1, text=f"{r.get('course')} {r.get('intake_curr')}"[:200])]
                if m is None:
                    out.append(_f(app, "X-PROG-NOT-APPROVED", "NOC lists a programme not on the previous approval",
                                  f"'{r.get('course')}' is on the university NOC but not on last year's EoA letter.", "medium", ev, noc.doc_id, 0.7))
                    continue
                ev.append(Evidence(doc_id=eoa.doc_id, page=1, text=f"{m.get('course')} {m.get('intake_curr')}"[:200]))
                n_noc, n_eoa = int(r.get("intake_curr") or 0), int(m.get("intake_curr") or 0)
                bad = n_noc != n_eoa if app.category == "eoa_existing_regular" else n_noc < n_eoa
                if bad:
                    out.append(_f(app, "X-INTAKE", "Intake on university NOC disagrees with approved intake",
                                  f"{r.get('course')}: NOC says {n_noc}, previous EoA letter says {n_eoa}.", "medium", ev, noc.doc_id))
    except Exception as e:
        out.append(Finding(finding_id=f"{app.app_id}-X-ERROR-APP", app_id=app.app_id, source="crosscheck", rule_id="X-ERROR",
                           title="Cross-check could not finish", reason=f"{type(e).__name__}: {str(e)[:150]}", severity="low", lane="info"))
    return out
