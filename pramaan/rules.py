"""run_rules(...) -> list[Finding]. Evaluates a YAML rule pack. Never raises. OWNER: Geetansh (reference version)."""
from __future__ import annotations

import re
from datetime import date

import yaml

from .schemas import Application, DocumentRecord, Evidence, Finding, VerificationResult
from .util import add_years, parse_date

NEEDS_DOC = {"field_present", "not_expired", "age_validity", "value_equals", "signature_required", "year_match"}


def _doc(docs, dt):
    return next((d for d in docs if d.doc_type == dt), None)


def _val(doc, field):
    f = doc.fields.get(field) if doc else None
    return (f.value or "").strip() if f and f.value else ""


def _ev(doc, field=None):
    if doc is None:
        return []
    f = doc.fields.get(field) if field else None
    if f and f.evidence:
        return [f.evidence]
    return [Evidence(doc_id=doc.doc_id, page=1, text=doc.filename[:200])]


def _check(rule, app, docs, ver, record, today):
    """Returns None (pass) or (doc, field, extra_reason, override dict)."""
    t, p = rule["type"], rule.get("params", {}) or {}
    doc = _doc(docs, p.get("doc_type")) if p.get("doc_type") else None
    if t in NEEDS_DOC and doc is None:
        return None                                   # missing document is reported by required_doc
    if t == "required_doc":
        return None if doc else (None, None, "", {})
    if t == "conditional_required":
        if doc is not None or record is None:
            return None
        if "when_record_older_than" in p:
            c = p["when_record_older_than"]
            d0 = parse_date(str(record.get(c["key"], "")))
            if d0 and add_years(d0, c["years"]) <= today:
                return (None, None, f" ({c['key']} = {d0.isoformat()})", {})
            return None
        c = p["when_record_equals"]
        return (None, None, "", {}) if record.get(c["key"]) == c["value"] else None
    f = p.get("field")
    if t == "field_present":
        return None if _val(doc, f) else (doc, f, "", {})
    if t == "not_expired":
        d = parse_date(_val(doc, f))
        if d is None:
            return (doc, f, " The date could not be read.", {"severity": "low", "lane": "human_review"}) if _val(doc, f) else None
        return (doc, f, f" Valid until {d.isoformat()}; checked on {today.isoformat()}.", {}) if d < today else None
    if t == "age_validity":
        d = parse_date(_val(doc, p["issue_field"]))
        if d is None:
            return None
        yrs = float(p["max_years"])
        m = re.search(r"\d+", _val(doc, p.get("validity_field", ""))) if p.get("validity_field") else None
        if m:
            yrs = min(yrs, float(m.group(0)))
        exp = add_years(d, yrs)
        return (doc, p["issue_field"], f" Issued {d.isoformat()}, allowed {yrs:g} years, so valid until {exp.isoformat()}.", {}) if exp < today else None
    if t == "value_equals":
        v = _val(doc, f)
        return None if not v or v == str(p["expected"]).strip() else (doc, f, f" Read: '{v}'.", {})
    if t == "signature_required":
        sig = [v for v in ver if v.doc_id == doc.doc_id and v.method == "digital_signature"]
        if any(v.status == "verified" for v in sig):
            return None
        why = f" Signature check said: {sig[0].status} ({sig[0].note[:80]})." if sig else " No signature check result."
        return (doc, None, why, {})
    if t == "year_match":
        v = _val(doc, f)
        m = re.search(r"(\d{4})", v)
        return None if not m or m.group(1) == app.academic_year[:4] else (doc, f, f" Read: '{v}', applied for {app.academic_year}.", {})
    if t == "record_flag":
        if record is None:
            return None
        return None if record.get(p["key"]) == p["expected"] else (None, None, "", {})
    raise ValueError(f"unknown rule type {t}")


def run_rules(app: Application, docs: list[DocumentRecord], verifications: list[VerificationResult],
              record: dict | None, rulepack_path: str, today: date) -> list[Finding]:
    out: list[Finding] = []
    try:
        with open(rulepack_path) as fh:
            rules = (yaml.safe_load(fh) or {}).get("rules", [])
    except Exception as e:
        return [Finding(finding_id=f"{app.app_id}-R-CONFIG-ERROR-APP", app_id=app.app_id, source="rule", rule_id="R-CONFIG-ERROR",
                        title="Rule pack could not be read", reason=str(e)[:200], severity="low", lane="info")]
    for r in rules:
        try:
            if app.category not in r.get("applies_to", []):
                continue
            res = _check(r, app, docs, verifications, record, today)
            if res is None:
                continue
            doc, field, extra, ov = res
            out.append(Finding(
                finding_id=f"{app.app_id}-{r['id']}-{doc.doc_id if doc else 'APP'}", app_id=app.app_id,
                doc_id=doc.doc_id if doc else None, source="rule", rule_id=r["id"], aph_clause=r.get("aph_clause"),
                clause_verified=bool(r.get("clause_verified", False)), title=r["title"], reason=(r["message"] + extra)[:400],
                severity=ov.get("severity", r["severity"]), lane=ov.get("lane", r["lane"]), evidence=_ev(doc, field)))
        except Exception as e:
            out.append(Finding(finding_id=f"{app.app_id}-R-CONFIG-ERROR-{r.get('id', '?')}", app_id=app.app_id, source="rule",
                               rule_id="R-CONFIG-ERROR", title=f"Rule {r.get('id', '?')} could not run",
                               reason=f"{type(e).__name__}: {str(e)[:150]}", severity="low", lane="info"))
    return out
