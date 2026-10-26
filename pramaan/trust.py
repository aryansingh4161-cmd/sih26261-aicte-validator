"""WK23-5 Trust score per document and per application, 0-100. DESIGNED score, not a probability: 100 minus deductions
with the weights in config/settings.yaml (trust_weights, ASSUMPTION). A finding deducts severity weight x confidence; a
verification result deducts by its status. Application score = the minimum over its documents and its application-level
findings (missing documents, cross-document checks); both are shown. Top 3 reasons in plain words. OWNER: Aryan."""
from __future__ import annotations

import yaml

from .i18n import t
from .schemas import ApplicationResult

LABEL = "designed score, not a probability"


def _weights(path: str = "config/settings.yaml") -> dict:
    with open(path) as f:
        return (yaml.safe_load(f) or {}).get("trust_weights", {})


def _score(items: list[tuple[float, str]], lang: str) -> tuple[int, list[str]]:
    items = sorted(items, reverse=True)
    reasons = [f"{t(why, lang)} (-{round(d)})" for d, why in items[:3] if d > 0]
    return max(0, round(100 - sum(d for d, _ in items))), reasons or [t("No findings and no failed checks.", lang)]


def doc_score(result: ApplicationResult, doc_id: str | None, w: dict | None = None, lang: str = "en") -> tuple[int, list[str]]:
    """doc_id=None scores the application-level findings (no document attached)."""
    w = w or _weights()
    items = [(w.get(f.severity, 0) * f.confidence, f.title) for f in result.findings if f.doc_id == doc_id]
    covered = {f.rule_id for f in result.findings if f.doc_id == doc_id}          # a V-<method> finding already deducted it
    items += [(w.get(v.status, 0), f"{v.source}: {v.status.replace('_', ' ')}") for v in result.verifications
              if doc_id is not None and v.doc_id == doc_id and f"V-{v.method}" not in covered]
    return _score(items, lang)


def app_score(result: ApplicationResult, lang: str = "en") -> dict:
    w = _weights()
    docs = {d.doc_id: doc_score(result, d.doc_id, w, lang) for d in result.documents}
    docs["application-level"] = doc_score(result, None, w, lang)
    worst = min(docs, key=lambda k: docs[k][0])
    return {"score": docs[worst][0], "reasons": docs[worst][1], "weakest": worst, "documents": docs, "label": t(LABEL, lang)}
