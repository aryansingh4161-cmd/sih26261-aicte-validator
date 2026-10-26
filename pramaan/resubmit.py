"""WK23-2 Resubmission diff: what changed between an institute's earlier application and its resubmission.
compare(prev, new) -> {"deficiencies": [{rule_id, title, status}], "documents": [{slot, status}], "summary": str}
Deficiency = a return_for_rectification finding, matched by rule id: resolved (only before) / still open (both) / new (only now).
Document = matched by upload slot: unchanged (same SHA-256) / replaced / added / removed. prev=None (first submission):
everything is new. OWNER: Aryan."""
from __future__ import annotations

from .i18n import t
from .schemas import ApplicationResult


def _defs(r: ApplicationResult | None) -> dict:
    return {f.rule_id: f.title for f in (r.findings if r else []) if f.lane == "return_for_rectification"}


def _slots(r: ApplicationResult | None) -> dict:
    return {(d.slot or d.doc_id.split("-", 2)[-1]): d.sha256 for d in (r.documents if r else [])}


def compare(prev: ApplicationResult | None, new: ApplicationResult, lang: str = "en") -> dict:
    a, b = _defs(prev), _defs(new)
    defs = [{"rule_id": k, "title": a[k], "status": "still open" if k in b else "resolved"} for k in a]
    defs += [{"rule_id": k, "title": b[k], "status": "new"} for k in b if k not in a]
    sa, sb = _slots(prev), _slots(new)
    docs = [{"slot": s, "status": "removed" if s not in sb else "unchanged" if sa[s] == sb[s] else "replaced"} for s in sa]
    docs += [{"slot": s, "status": "added"} for s in sb if s not in sa]
    n = {k: sum(d["status"] == k for d in defs) for k in ("resolved", "still open", "new")}
    summary = t(f"{n['resolved']} of {len(a)} deficiencies resolved; {n['still open']} still open; {n['new']} new", lang)
    return {"prev_app": prev.app_id if prev else None, "app_id": new.app_id, "deficiencies": defs, "documents": docs,
            "summary": summary, "changed_documents": [d for d in docs if d["status"] != "unchanged"]}
