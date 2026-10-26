"""Case views, part 2 (WK26): verification sources + preview payload, changes since last year, resubmission, letter draft."""
from __future__ import annotations

import hashlib
import json

import yaml

from pramaan.geo import geocode
from pramaan.letters import build_lod
from pramaan.photo_check import km
from pramaan.resubmit import compare
from pramaan.rule_admin import check_clause
from pramaan.schemas import Application
from pramaan.util import norm_name
from pramaan.verify_board import board

from .ctx import DOC_LABEL, LANE_LABEL, Ctx

RESULT = {"verified": ("Matches", "clear"), "mismatch": ("Does not match", "return_for_rectification"),
          "expired": ("Expired", "return_for_rectification"), "pending": ("Pending", "human_review"),
          "unavailable": ("Source not answering", "not_automated"), "consent not given": ("Consent not given", "not_automated")}
_CLAUSE_CACHE: dict = {}


def _hash(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:6]


def sources(ctx: Ctx, app_id: str) -> dict:
    r, m = ctx.result(app_id), ctx.manifest(app_id)
    docs = {d.doc_id: d for d in r.documents}
    rows = []
    def answer(b, d) -> str:
        """A plain sentence from the source's compared fields (which matched, which did not)."""
        v = next((v for v in r.verifications if v.doc_id == b["document"] and v.source == b["source"]), None)
        if not v or not v.compared:
            return (v.note if v and v.note else b["compared"]) or ""
        nice = lambda f: f.replace("_", " ")
        bad = [c for c in v.compared if not c.match]
        if not bad:
            names = [nice(c.field) for c in v.compared]
            return "Found. " + (" and ".join(names) if len(names) < 3 else ", ".join(names[:-1]) + " and " + names[-1]).capitalize() + (" matches" if len(names) == 1 else " match")
        c = bad[0]
        return f"Found. {nice(c.field).capitalize()} differs: the file says '{c.submitted}', the source says '{c.returned}'"
    for b in board(r, Application(**m), "en"):
        d = docs.get(b["document"])
        ref = (d.fields["certificate_no"].value if d and "certificate_no" in d.fields else None) if d else None
        word, lane = RESULT.get(b["status"], (b["status"], "human_review"))
        src = b["source"].replace("MOCK ", "")
        rows.append({"source": src[:1].upper() + src[1:], "demo": b["mock"],
                     "asked": ctx.tr(f"{DOC_LABEL.get(d.doc_type, d.doc_type)} for {app_id}" if d else f"Records for {app_id}") + (f" ({ref})" if ref else ""),
                     "answer": ctx.tr(answer(b, d)[:1].upper() + answer(b, d)[1:]), "when": b["checked_at"], "result": ctx.tr(word), "lane": lane,
                     "doc_id": b["document"] if d else None, "preview": b["status"] not in ("unavailable", "consent not given")})
    reuse = [f for f in r.findings if f.rule_id in ("X-SERIAL", "X-REUSE-CERT", "X-REUSE-PHOTO")]
    rows.append({"source": "Serial register", "demo": False, "asked": ctx.tr("Certificate numbers, text and photos of this file"),
                 "answer": ctx.tr(reuse[0].reason) if reuse else ctx.tr("Not used in any other file"), "when": r.run_at,
                 "result": ctx.tr("Also used elsewhere" if reuse else "Unique"), "lane": "human_review" if reuse else "clear",
                 "doc_id": reuse[0].doc_id if reuse else None, "preview": True})
    dec, hit = m.get("declared", {}), geocode(m.get("declared", {}).get("address"))
    if hit and dec.get("latitude") is not None:
        dist = km((float(dec["latitude"]), float(dec["longitude"])), (hit["latitude"], hit["longitude"]))
        far = dist > float(ctx.settings().get("geo_max_km", 2.0))
        rows.append({"source": "Map check", "demo": True, "asked": ctx.tr("Declared campus location against the address"),
                     "answer": ctx.tr(f"Declared location is {dist:.1f} km from the address" if far else f"Within {dist * 1000:.0f} m of the address"),
                     "when": r.run_at, "result": ctx.tr("Differs" if far else "Matches"), "lane": "human_review" if far else "clear",
                     "doc_id": None, "preview": True})
    rows.append({"source": "Registrar of Societies", "demo": False, "asked": ctx.tr("Society registration"),
                 "answer": ctx.tr("No connection to this source yet"), "when": None, "result": ctx.tr("Check by hand"),
                 "lane": "not_automated", "doc_id": None, "preview": False})
    for i, x in enumerate(rows):
        x["id"] = i
    return {"count": sum(1 for x in rows if x["when"]), "rows": rows}


def preview(ctx: Ctx, app_id: str, row_id: int) -> dict:
    """What the source sent back, unchanged, plus where Pramaan looked (the evidence box)."""
    r, rows = ctx.result(app_id), sources(ctx, app_id)["rows"]
    x = rows[row_id]
    d = next((d for d in r.documents if d.doc_id == x["doc_id"]), None)
    f = next((f for f in r.findings if f.doc_id == x["doc_id"] and f.evidence and f.evidence[0].bbox), None) if d else None
    v = next((v for v in r.verifications if v.doc_id == x["doc_id"]), None) if d else None
    kv = [("Document id", v.reference if v and v.reference else (d.doc_id if d else app_id))]
    if v:
        kv += [(c.field.replace("_", " ").capitalize(), f"{c.returned} ({'matches' if c.match else 'the file says ' + str(c.submitted)})") for c in v.compared]
    kv += [("Issued by", x["source"] + (" (as sent by the source)" if x["demo"] else "")), ("Received", x["when"] or "-"),
           ("Answer hash", "#" + (v.payload_hash[:6] if v and v.payload_hash else _hash(x)))]
    return {**x, "kv": [{"k": ctx.tr(k), "v": str(val)} for k, val in kv],
            "image": f"/api/documents/{app_id}/{d.doc_id}/page/1.png" if d else None,
            "box": f.evidence[0].bbox.model_dump() if f else None,
            "note": ctx.tr("This is the raw answer, unchanged. Pramaan only draws the red box to show where it looked.")}


def changes(ctx: Ctx, app_id: str) -> dict:
    r, m = ctx.result(app_id), ctx.manifest(app_id)
    rec = ctx.records().get(m.get("permanent_id"), {})
    by = {d.doc_type: d for d in r.documents}
    noc = {norm_name(x.get("course")): x.get("intake_curr") for x in (by["noc_format2"].tables.get("programs", []) if "noc_format2" in by else [])}
    area = by.get("area_statement")
    rows = [(f"Approved intake: {p['course']}", p.get("intake_prev"), noc.get(norm_name(p["course"]), "-")) for p in rec.get("approved_programs", [])]
    rows += [("Built-up area (sq m)", rec.get("last_built_up_area_sqm"),
              area.fields["total_built_up_area_sqm"].value if area and "total_built_up_area_sqm" in area.fields else "-"),
             ("Institute name", rec.get("institute_name"), m.get("declared", {}).get("institute_name")),
             ("Address", rec.get("address"), m.get("declared", {}).get("address"))]
    yoy = {f.rule_id: f for f in r.findings if f.rule_id.startswith("X-YOY")}
    out = []
    for name, a, b in rows:
        same = str(a).strip().lower() == str(b).strip().lower()
        try:
            change = "Same" if same else f"Higher by {float(b) - float(a):g}" if float(b) > float(a) else f"Lower by {float(a) - float(b):g}"
        except (TypeError, ValueError):
            change = "Same" if same else "Changed"
        out.append({"field": ctx.tr(name), "before": a if a is not None else "-", "after": b if b is not None else "-",
                    "change": ctx.tr(change), "flag": not same})
    return {"changed": sum(x["flag"] for x in out), "total": len(out), "rows": out,
            "findings": [{"rule_id": k, "title": ctx.tr(f.title), "reason": ctx.tr(f.reason)} for k, f in yoy.items()],
            "note": ctx.tr("A change alone never moves the file to another lane. It is shown so the officer can ask why."),
            "source": ctx.tr("Last year's AICTE record (demo adapter)")}


def resubmission(ctx: Ctx, app_id: str) -> dict:
    m = ctx.manifest(app_id)
    prev = sorted(a for a, mm in ctx.manifests().items() if mm.get("permanent_id") == m.get("permanent_id") and a < app_id)
    if not prev:
        return {"available": False, "note": ctx.tr("This is the first submission of this file.")}
    p, n = ctx.result(prev[-1]), ctx.result(app_id)
    d = compare(p, n, ctx.lang)
    pf, nf = {f.rule_id: f for f in p.findings}, {f.rule_id: f for f in n.findings}
    rows = [{"issue": ctx.tr(x["title"]), "before": ctx.tr(pf[x["rule_id"]].reason) if x["rule_id"] in pf else "-",
             "after": ctx.tr(nf[x["rule_id"]].reason) if x["rule_id"] in nf else ctx.tr("No longer found in the new file"),
             "result": ctx.tr({"resolved": "Fixed", "still open": "Still open", "new": "New"}[x["status"]]), "status": x["status"]}
            for x in d["deficiencies"]]
    fixed = sum(x["status"] == "resolved" for x in rows)
    slots = {c["slot"] for c in d["changed_documents"]}
    tied = [sl for x in d["deficiencies"] for sl in slots if x["rule_id"].endswith(sl) or f"-{sl}-" in x["rule_id"]]
    slot = (tied or [c["slot"] for c in d["changed_documents"]] or [None])[0]     # the document behind the first deficiency
    img = lambda res: next((f"/api/documents/{res.app_id}/{doc.doc_id}/page/1.png" for doc in res.documents if (doc.slot or "") == slot), None)
    return {"available": True, "previous": prev[-1], "headline": ctx.tr(f"{fixed} of {sum(x['status'] != 'new' for x in rows)} issues fixed."),
            "summary": d["summary"], "rows": rows, "documents": d["documents"], "slot": ctx.tr(DOC_LABEL.get(slot, slot)) if slot else None,
            "before_image": img(p), "after_image": img(n)}


def letter_draft(ctx: Ctx, app_id: str, include: list[str] | None = None) -> dict:
    r, m = ctx.result(app_id), ctx.manifest(app_id)
    items = [{"finding_id": f.finding_id, "rule_id": f.rule_id, "title": ctx.tr(f.title), "lane": f.lane,
              "include": (f.finding_id in include) if include is not None else f.lane == "return_for_rectification",
              "clause": f.aph_clause, "clause_check": _clause(f.aph_clause)} for f in r.findings if f.lane in ("return_for_rectification", "human_review")]
    keep = {i["finding_id"] for i in items if i["include"]}
    # the officer decides: a Human review item the officer includes goes into the letter as a deficiency
    sub = r.model_copy(update={"findings": [f.model_copy(update={"lane": "return_for_rectification"}) if f.lane == "human_review" else f
                                            for f in r.findings if f.finding_id in keep]})
    reg = (m.get("declared", {}).get("region") or "XX").replace("-", "")[:2].upper()
    lod = build_lod(sub, institute=m.get("declared", {}).get("institute_name", ""), permanent_id=m.get("permanent_id", ""),
                    file_no=f"AICTE/RB/{reg}/{r.academic_year}/{app_id}", today=ctx.today, lang=ctx.lang)
    pack = yaml.safe_load(open("config/rulepack_eoa_existing.yaml")).get("rules", [])
    quotes = sorted({x["aph_clause"] for x in pack if x.get("aph_clause")})
    found = sum(1 for q in quotes if _clause(q)["found"])
    dec = m.get("declared", {})
    header = {"file_no": f"AICTE/RB/{reg}/{r.academic_year}/{app_id}", "date": ctx.today.strftime("%d %b %Y"), "institute": dec.get("institute_name"),
              "address": dec.get("address"), "permanent_id": m.get("permanent_id"), "academic_year": r.academic_year,
              "region": dec.get("region"), "subject": ctx.tr(f"Letter of Deficiency for Extension of Approval {r.academic_year}")}
    defs = [{**x, "clause_check": _clause(x["clause"])} for x in lod["deficiencies"]]
    return {"app_id": app_id, "items": items, "text": lod["text"], "header": header, "deficiencies": defs,
            "closing": ctx.tr("You are requested to upload the rectified documents on the AICTE portal within the time given on the portal. "
                              "You may appeal within 7 days of this letter being uploaded."),
            "signature": [ctx.tr("Regulation Bureau"), ctx.tr(f"{dec.get('region', '')} Regional Office, AICTE").strip()],
            "quotes": {"found": found, "total": len(quotes), "label": "measured"}}


def _clause(text: str | None) -> dict:
    if not text:
        return {"found": False, "page": None}
    if text not in _CLAUSE_CACHE:
        c = check_clause(text)
        _CLAUSE_CACHE[text] = {"found": c["found"], "page": c["page"]}
    return _CLAUSE_CACHE[text]
