"""WK23-15 Expert Visit Committee (EVC) pack: one page per application listing what to inspect physically, each item with its
clause: rooms below the norm (with the norm), a building over 30 years old (structural certificate), a partial / provisional
occupancy certificate, photo findings, programmes added since last year, an affidavit sworn after submission, a far-off declared
location. Sealed (seal.py). Clauses come from the rule pack / norm rows; "(design check, no Handbook clause)" otherwise.
OWNER: Aryan."""
from __future__ import annotations

import html as H
from datetime import date

import yaml

from .i18n import t
from .schemas import ApplicationResult
from .seal import seal_html
from .util import parse_date

PHOTO = ("F-PHOTO", "F-META-EXIF", "F-META-JPEG", "X-REUSE-PHOTO")


def _clauses(rulepack: str) -> dict:
    with open(rulepack) as f:
        return {r["id"]: r.get("aph_clause") for r in (yaml.safe_load(f) or {}).get("rules", [])}


def items(result: ApplicationResult, record: dict | None, today: date, rulepack: str = "config/rulepack_eoa_existing.yaml",
          lang: str = "en") -> list[dict]:
    cl, out = _clauses(rulepack), []
    add = lambda what, why, clause: out.append({"what": t(what, lang), "why": t(why, lang), "clause": clause or t("(design check, no Handbook clause)", lang)})
    for f in result.findings:
        if f.rule_id.startswith("R-AREA"):
            add("Measure the rooms: " + f.title, f.reason, f.aph_clause)
        elif f.rule_id.startswith(PHOTO):
            add("Compare the campus with the photos: " + f.title, f.reason, None)
        elif f.rule_id in ("X-YOY-PROGRAMME", "X-YOY-INTAKE") or (f.rule_id == "X-INTAKE" and "not on last year" in f.reason):
            add("Check the facilities for the added intake / programmes", f.reason, None)
        elif f.rule_id == "X-SWORN-AFTER-SUBMIT":
            add("Ask for the original affidavit (sworn after submission)", f.reason, cl.get("R-MISS-affidavit_2"))
        elif f.rule_id == "X-GEO":
            add("Confirm the campus location on site", f.reason, None)
    built = parse_date((record or {}).get("building_completion_date"))
    if built and (today - built).days > 30 * 365:
        add(f"Building completed {built.year} (over 30 years): see the Structural Stability Certificate and the structure",
            "Building age from the AICTE record.", cl.get("R-MISS-structural_cert"))
    occ = next((d for d in result.documents if d.doc_type == "occupancy_cert"), None)
    kind = (occ.fields["certificate_kind"].value or "").lower() if occ and "certificate_kind" in occ.fields else ""
    if kind in ("partial", "provisional"):
        add(f"Occupancy certificate is {kind}: see which blocks are occupied", "Certificate kind printed on the document.",
            cl.get("R-PROV-occupancy_cert"))
    return out


def evc_pack(result: ApplicationResult, record: dict | None, log, today: date | None = None, lang: str = "en") -> str:
    today = today or date.today()
    rows = items(result, record, today, lang=lang)
    li = "".join(f"<li><b>{H.escape(i['what'])}</b><br>{H.escape(i['why'])}<br><i>{H.escape(i['clause'])}</i></li>" for i in rows)
    body = (f"<!doctype html><meta charset='utf-8'><title>EVC pack {result.app_id}</title><body style='font-family:sans-serif;"
            f"max-width:46em;margin:2em auto'><h2>{H.escape(t('Expert Visit Committee: what to inspect', lang))}</h2>"
            f"<p>{H.escape(t('Application', lang))} {result.app_id} ({result.academic_year}) - {today.isoformat()} - "
            f"{H.escape(t('advisory: prepared by Pramaan from the findings', lang))}</p>"
            f"<ol>{li or '<li>' + H.escape(t('Nothing specific beyond the standard inspection.', lang)) + '</li>'}</ol></body>")
    return seal_html(body, result.app_id, log, kind="EVC pack")
