"""WK23-7 Year-over-year compare: this year's application vs last year's MOCK AICTE record (which mirrors last year's EoA
letter: approved intake per programme, built-up area, institute name and address). Unexplained changes -> human_review:
  X-YOY-INTAKE    (intake_increase applications) total intake up >= intake_up_pct while the built-up area rose < area_up_min_pct
  X-YOY-PROGRAMME (intake_increase applications) a course on this year's NOC that was not approved last year
  X-YOY-NAME / X-YOY-ADDRESS  declared name / address differs from last year's (Annexure-2 2.13 documents expected)
For regular EoA applications any intake or course change is already X-INTAKE (crosscheck.py), so it is not repeated here.
Thresholds: settings.yaml `yoy` (ASSUMPTION). OWNER: Aryan."""
from __future__ import annotations

import re

from .i18n import t
from .schemas import Application, DocumentRecord, Evidence, Finding
from .util import norm_name, similarity


def _num(v) -> float | None:
    m = re.search(r"\d+(?:\.\d+)?", str(v or "").replace(",", ""))
    return float(m.group(0)) if m else None


def _f(app, rid, title, reason, doc=None, text=""):
    ev = [Evidence(doc_id=doc.doc_id if doc else app.app_id, page=1, text=text[:200])]
    return Finding(finding_id=f"{app.app_id}-{rid}-{doc.doc_id if doc else 'APP'}", app_id=app.app_id, doc_id=doc.doc_id if doc else None,
                   source="crosscheck", rule_id=rid, title=t(title), reason=t(reason)[:400], severity="medium", confidence=0.8,
                   lane="human_review", evidence=ev)


def yoy_check(app: Application, docs: list[DocumentRecord], record: dict | None, settings: dict) -> list[Finding]:
    if not record:
        return []
    cfg = settings.get("yoy", {}) or {}
    out, by = [], {d.doc_type: d for d in docs}
    noc, area = by.get("noc_format2"), by.get("area_statement")
    last = {norm_name(p["course"]): _num(p.get("intake_prev")) or 0 for p in record.get("approved_programs", [])}
    if app.category == "intake_increase" and noc and noc.tables.get("programs"):
        now = {norm_name(r.get("course")): _num(r.get("intake_curr")) or 0 for r in noc.tables["programs"]}
        a0 = _num(record.get("last_built_up_area_sqm"))
        a1 = _num(area.fields["total_built_up_area_sqm"].value) if area and "total_built_up_area_sqm" in area.fields else None
        i0, i1 = sum(last.values()), sum(now.values())
        if i0 and a0 and a1 and i1 >= i0 * (1 + cfg.get("intake_up_pct", 25) / 100) and a1 < a0 * (1 + cfg.get("area_up_min_pct", 5) / 100):
            out.append(_f(app, "X-YOY-INTAKE", "Intake rises much faster than the built-up area",
                          f"Total intake {i0:g} last year -> {i1:g} now (+{100 * (i1 / i0 - 1):.0f}%), while the built-up area went "
                          f"{a0:g} -> {a1:g} sq m ({100 * (a1 / a0 - 1):+.0f}%). Thresholds: intake +{cfg.get('intake_up_pct', 25)}%, "
                          f"area below +{cfg.get('area_up_min_pct', 5)}% (assumption).", area or noc, f"intake {i0:g}->{i1:g}, area {a0:g}->{a1:g}"))
        new = [c for c in now if c not in last]
        if new:
            out.append(_f(app, "X-YOY-PROGRAMME", "Programme not approved last year",
                          f"Course(s) on this year's NOC that were not approved last year: {', '.join(new)}.", noc, ", ".join(new)))
    name, addr = app.declared.get("institute_name"), app.declared.get("address")
    if name and record.get("institute_name") and similarity(name, record["institute_name"]) < cfg.get("name_similarity", 0.85):
        out.append(_f(app, "X-YOY-NAME", "Institute name differs from last year",
                      f"Declared '{name}', last year '{record['institute_name']}'. A name change needs the Annexure-2 2.13 documents.",
                      text=f"{record['institute_name']} -> {name}"))
    if addr and record.get("address") and similarity(addr, record["address"]) < cfg.get("address_similarity", 0.7):
        out.append(_f(app, "X-YOY-ADDRESS", "Institute address differs from last year",
                      f"Declared '{addr}', last year '{record['address']}'.", text=f"{record['address']} -> {addr}"))
    return out
