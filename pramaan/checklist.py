"""WK23-3 Checklist auto-tick. tick(result) -> one row per requirement in config/checklists/<category>.yaml with status
green / amber / red / grey and the evidence (document, page, box) behind it; counts(rows) -> "9 green, 1 amber, 1 red, 3 grey".
Red = a return_for_rectification finding hits the row; amber = a human_review finding; green = its documents are present
(or the rules did not require them) and nothing hits it; grey = not automated (the officer checks by hand). OWNER: Aryan."""
from __future__ import annotations

import yaml

from .i18n import t
from .schemas import ApplicationResult

ORDER = ("green", "amber", "red", "grey")


def load(path: str = "config/checklists/eoa_existing.yaml") -> list[dict]:
    with open(path) as f:
        return (yaml.safe_load(f) or {}).get("rows", [])


def tick(result: ApplicationResult, path: str = "config/checklists/eoa_existing.yaml", lang: str = "en") -> list[dict]:
    docs = {d.doc_id: d.doc_type for d in result.documents}
    out = []
    for row in load(path):
        base = {"id": row["id"], "ref": row.get("ref"), "item": t(row["item"], lang)}
        if row.get("automated") is False:
            out.append({**base, "status": "grey", "why": t("Not automated yet: the officer checks this by hand.", lang), "evidence": []})
            continue
        types, rules = set(row.get("doc_types") or []), tuple(row.get("rules") or [])
        hits = [f for f in result.findings if f.lane != "info" and (f.rule_id.startswith(rules) or docs.get(f.doc_id) in types)]
        status = "red" if any(f.lane == "return_for_rectification" for f in hits) else "amber" if hits else "green"
        present = [i for i, dt in docs.items() if dt in types]
        why = "; ".join(t(f.title, lang) for f in hits) if hits else (
            t("Present and the checks pass.", lang) if present or not types else t("Not submitted; not required by the rules for this application.", lang))
        ev = [e.model_dump() for f in hits for e in f.evidence] or [{"doc_id": i, "page": 1, "bbox": None, "text": ""} for i in present]
        out.append({**base, "status": status, "why": why, "evidence": ev, "finding_ids": [f.finding_id for f in hits]})
    return out


def counts(rows: list[dict], lang: str = "en") -> str:
    return ", ".join(f"{sum(r['status'] == s for r in rows)} {t(s, lang)}" for s in ORDER)
