"""build_report(result, out_dir) -> {"json": path, "html": path}. One self-contained HTML (inline CSS, no JS).
OWNER: Aryan (reference version)."""
from __future__ import annotations

import os
from html import escape as E

from .privacy import mask_text, personal_values
from .schemas import ApplicationResult

LANE = {"clear": ("#1f7a3a", "No issues found - ready for officer sign-off"),
        "return_for_rectification": ("#b86e00", "Return for rectification"),
        "human_review": ("#c2410c", "Send to human review")}
SEV = {"high": "#b91c1c", "medium": "#b45309", "low": "#2563eb", "info": "#6b7280"}
CSS = """body{font-family:Arial,Helvetica,sans-serif;margin:0;color:#1f2937;background:#f5f6f8}
.wrap{max-width:900px;margin:0 auto;padding:18px}.hdr{background:#1e3a5f;color:#fff;padding:14px 18px}
.hdr h1{font-size:18px;margin:0}.hdr p{margin:4px 0 0;font-size:12px;opacity:.85}
.badge{display:inline-block;color:#fff;font-weight:bold;padding:10px 18px;border-radius:6px;font-size:18px;margin-top:14px}
.note{font-size:12px;color:#4b5563;margin:6px 0 14px}h2{font-size:15px;border-bottom:2px solid #d1d5db;padding-bottom:4px;margin-top:22px}
.card{background:#fff;border-left:5px solid #999;padding:10px 12px;margin:8px 0;border-radius:4px}
.card b{font-size:14px}.pill{color:#fff;font-size:11px;padding:2px 7px;border-radius:9px;margin-left:6px}
.small{font-size:12px;color:#4b5563}.ev{font-family:monospace;font-size:12px;background:#f3f4f6;padding:2px 5px;margin:2px 0}
table{border-collapse:collapse;width:100%;background:#fff;font-size:12px}td,th{border:1px solid #e5e7eb;padding:5px;text-align:left}
th{background:#eef2f7}.mock{background:#7c3aed;color:#fff;font-size:10px;padding:1px 5px;border-radius:3px}
.none{color:#9ca3af;font-size:12px}.foot{font-size:11px;color:#6b7280;margin-top:24px;word-break:break-all}
@media print{body{background:#fff}}"""


def _table(headers, rows):
    if not rows:
        return '<p class="none">None</p>'
    h = "".join(f"<th>{E(x)}</th>" for x in headers)
    b = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in r) + "</tr>" for r in rows)
    return f"<table><tr>{h}</tr>{b}</table>"


def _finding(f):
    clause = ""
    if f.aph_clause:
        clause = f'<div class="small">Handbook clause: {E(f.aph_clause)}{"" if f.clause_verified else " - <b>UNVERIFIED</b>"}</div>'
    ev = "".join(f'<div class="ev">{E(e.doc_id)} p.{e.page}: {E(e.text)}</div>' for e in f.evidence)
    return (f'<div class="card" style="border-left-color:{SEV[f.severity]}"><b>{E(f.title)}</b>'
            f'<span class="pill" style="background:{SEV[f.severity]}">{E(f.severity)}</span>'
            f'<span class="small"> confidence {f.confidence:.0%} - {E(f.source)} - {E(f.rule_id)}</span>'
            f'<div>{E(f.reason)}</div>{clause}{ev}</div>')


def _masked(r: ApplicationResult) -> ApplicationResult:
    """The HTML report does not need personal values: mask them in findings and verifications (result JSON keeps them)."""
    pv = personal_values(r.documents)
    if not pv:
        return r
    m = lambda s: mask_text(s, pv) if s else s
    fs = [f.model_copy(update={"title": m(f.title), "reason": m(f.reason),
                               "evidence": [e.model_copy(update={"text": m(e.text)}) for e in f.evidence]}) for f in r.findings]
    vs = [v.model_copy(update={"reference": m(v.reference), "note": m(v.note)}) for v in r.verifications]
    return r.model_copy(update={"findings": fs, "verifications": vs})


def render_html(r: ApplicationResult) -> str:
    r = _masked(r)
    col, label = LANE[r.lane]
    parts = [f'<div class="hdr"><h1>Pramaan AI - Application advisory report</h1><p>{E(r.app_id)} | {E(r.category)} | '
             f'Academic year {E(r.academic_year)} | run {E(r.run_at)}</p></div><div class="wrap">',
             f'<div class="badge" style="background:{col}">{E(label)}</div>',
             f'<p><b>Inspection priority {r.priority:.2f}</b> <span class="small">(0..1, designed weights, an assumption; orders the queue only)</span></p>'
             + ''.join(f'<div class="small">- {E(x)}</div>' for x in r.priority_reasons),
             '<p class="note">AI advisory only. A human officer decides. This tool never rejects an application.</p>']
    for lane, title in (("human_review", "Needs human review"), ("return_for_rectification", "Return for rectification"), ("info", "For information")):
        fs = [f for f in r.findings if f.lane == lane]
        parts.append(f"<h2>{title} ({len(fs)})</h2>" + ("".join(_finding(f) for f in fs) or '<p class="none">None</p>'))
    parts.append("<h2>Documents</h2>" + _table(["Document", "Detected type", "Type confidence", "Pages", "Scanned"],
                 [[E(d.doc_id), E(d.doc_type), f"{d.doc_type_confidence:.0%}", str(d.pages), "yes" if d.is_scanned else "no"] for d in r.documents]))
    parts.append("<h2>Verification</h2>" + _table(["Document", "Method", "Source", "Status", "Reference", "Note"],
                 [[E(v.doc_id), E(v.method), E(v.source) + (' <span class="mock">MOCK</span>' if v.mock else ""), f"<b>{E(v.status)}</b>",
                   E(v.reference or ""), E(v.note)] for v in r.verifications]))
    parts.append("<h2>Alerts</h2>" + _table(["Kind", "Message", "Due by"], [[E(a.kind), E(a.message), E(a.due_by)] for a in r.alerts]))
    notes = "".join(f"<div>{E(n)}</div>" for n in r.notes)
    parts.append(f'<div class="foot">{notes}<div>Audit chain head: {E(r.audit_head_hash)}</div>'
                 f'<div>Processed in {r.seconds_taken:.1f} s. SLA days are configurable assumptions. Verification marked MOCK is simulated '
                 f'(designed for integration; no real authority was contacted).</div></div></div>')
    return f'<!doctype html><html><head><meta charset="utf-8"><title>{E(r.app_id)} report</title><style>{CSS}</style></head><body>{"".join(parts)}</body></html>'


def build_report(result: ApplicationResult, out_dir: str) -> dict:
    os.makedirs(out_dir, exist_ok=True)
    j = os.path.join(out_dir, f"{result.app_id}.result.json")
    h = os.path.join(out_dir, f"{result.app_id}.report.html")
    with open(j, "w") as f:
        f.write(result.model_dump_json(indent=2))
    with open(h, "w", encoding="utf-8") as f:
        f.write(render_html(result))
    return {"json": j, "html": h}
