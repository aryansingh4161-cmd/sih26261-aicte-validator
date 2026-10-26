"""WK25-22 Search across applications + saved filters per officer (back-end; no UI here).
search(query, filters) -> ranked rows {app_id, field, value, reason, score}. Every word of the query must match the application
(AND). Words match: app id, Permanent Id, institute name (fuzzy, a typo is fine), rule id, document type ("fire", "structural",
"occupancy", "noc", "affidavit", "area", "eoa"), region, lane, officer, and status words ("expired", "missing", "serial",
"review", "reuse", "mismatch", "clear"). Words that hit the SAME finding score highest. filters: region, lane, officer (exact).
Saved filters: table saved_filters in the audit DB file (save / list / run / delete).
  python -m pramaan.search "fire expired" --region North-West [--out output]        OWNER: Aryan."""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sqlite3
from contextlib import closing

from .i18n import t
from .schemas import ApplicationResult
from .util import now_iso

DOC_WORDS = {"fire": "fire_cert", "structural": "structural_cert", "structure": "structural_cert", "occupancy": "occupancy_cert",
             "completion": "occupancy_cert", "noc": "noc_format2", "affidavit": "affidavit_2", "area": "area_statement", "eoa": "eoa_letter"}
STATUS = {"expired": ("R-EXP", "R-PROV"), "missing": ("R-MISS",), "serial": ("X-SERIAL",), "reuse": ("X-REUSE",),
          "mismatch": ("X-", "V-"), "tamper": ("F-TAMPER",), "photo": ("F-PHOTO", "F-META-EXIF")}
LANE_WORDS = {"review": "human_review", "rectification": "return_for_rectification", "return": "return_for_rectification", "clear": "clear"}


def _ratio(a: str, b: str) -> float:
    try:
        from rapidfuzz import fuzz
        return fuzz.ratio(a, b) / 100
    except ImportError:
        import difflib
        return difflib.SequenceMatcher(None, a, b).ratio()


def _load(out_dir: str, manifests_dir: str):
    res = [ApplicationResult.model_validate_json(open(p).read()) for p in sorted(glob.glob(os.path.join(out_dir, "*.result.json")))]
    mans = {}
    for p in glob.glob(os.path.join(manifests_dir, "*.json")):
        m = json.load(open(p)); mans[m["app_id"]] = m
    return res, mans


def _word_hits(w: str, r: ApplicationResult, m: dict) -> list[tuple[float, str, str, str | None]]:
    """(score, field, value, finding_id) for one query word against one application."""
    d, hits = m.get("declared", {}), []
    if w in r.app_id.lower():
        hits.append((5, "app id", r.app_id, None))
    if m.get("permanent_id") and w in m["permanent_id"].lower():
        hits.append((5, "Permanent Id", m["permanent_id"], None))
    name = (d.get("institute_name") or "").lower()
    if len(w) >= 4 and any(_ratio(w, nw) >= 0.8 for nw in re.findall(r"[a-z]+", name)):
        hits.append((3, "institute name", d.get("institute_name"), None))
    for key, field in (("region", "region"), ("assigned_officer", "officer")):
        if d.get(key) and w == str(d[key]).lower():
            hits.append((2, field, d[key], None))
    if LANE_WORDS.get(w) == r.lane:
        hits.append((2, "lane", r.lane, None))
    dt = DOC_WORDS.get(w)
    for f in r.findings:
        rid = f.rule_id.lower()
        if len(w) >= 3 and (rid.startswith(w) or w == rid):
            hits.append((4, "rule id", f.rule_id, f.finding_id))
        if dt and (dt in rid or (f.doc_id or "").endswith(dt)):
            hits.append((3, "finding", f"{f.rule_id}: {f.title}", f.finding_id))
        if w in STATUS and f.rule_id.startswith(STATUS[w]):
            hits.append((3, "finding", f"{f.rule_id}: {f.title}", f.finding_id))
    if dt and any(doc.doc_type == dt for doc in r.documents):
        hits.append((1, "document", dt, None))
    return hits


def search(query: str, filters: dict | None = None, out_dir: str = "output", manifests_dir: str = "data/demo/apps",
           lang: str = "en") -> list[dict]:
    filters = {k: v for k, v in (filters or {}).items() if v}
    res, mans = _load(out_dir, manifests_dir)
    words = [w for w in re.findall(r"[\w-]+", query.lower()) if w]
    out = []
    for r in res:
        m = mans.get(r.app_id, {}); d = m.get("declared", {})
        if any(str({"region": d.get("region"), "lane": r.lane, "officer": d.get("assigned_officer")}.get(k)) != str(v) for k, v in filters.items()):
            continue
        per = [_word_hits(w, r, m) for w in words]
        if any(not h for h in per):                    # every word must match (an empty query lists the filtered apps)
            continue
        same = {}
        for h in per:
            for _, _, _, fid in h:
                if fid:
                    same[fid] = same.get(fid, 0) + 1
        best = [max(h) for h in per]
        score = sum(b[0] for b in best) + 5 * max([n - 1 for n in same.values()] or [0])     # words on the same finding
        top = max(best, default=(0, "filter", r.app_id, None))
        out.append({"app_id": r.app_id, "field": t(top[1], lang), "value": top[2], "score": score,
                    "reason": t("matched", lang) + ": " + "; ".join(f"'{w}' -> {b[1]} {b[2]}" for w, b in zip(words, best)) if words
                    else t("matches the filters", lang)})
    return sorted(out, key=lambda x: (-x["score"], x["app_id"]))


def _db(path: str):
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS saved_filters (officer TEXT, name TEXT, query TEXT, filters TEXT, created TEXT, "
              "PRIMARY KEY (officer, name))")
    return closing(c)


def save_filter(db: str, officer: str, name: str, query: str, filters: dict | None = None) -> None:
    with _db(db) as c:
        c.execute("INSERT OR REPLACE INTO saved_filters VALUES (?,?,?,?,?)", (officer, name, query, json.dumps(filters or {}), now_iso()))
        c.commit()


def list_filters(db: str, officer: str) -> list[dict]:
    with _db(db) as c:
        return [{"name": n, "query": q, "filters": json.loads(f), "created": ts}
                for n, q, f, ts in c.execute("SELECT name, query, filters, created FROM saved_filters WHERE officer=? ORDER BY name", (officer,))]


def run_filter(db: str, officer: str, name: str, **kw) -> list[dict]:
    f = next((x for x in list_filters(db, officer) if x["name"] == name), None)
    if f is None:
        raise KeyError(f"no saved filter '{name}' for {officer}")
    return search(f["query"], f["filters"], **kw)


def delete_filter(db: str, officer: str, name: str) -> bool:
    with _db(db) as c:
        n = c.execute("DELETE FROM saved_filters WHERE officer=? AND name=?", (officer, name)).rowcount
        c.commit()
    return n > 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?", default=""); ap.add_argument("--region"); ap.add_argument("--lane"); ap.add_argument("--officer")
    ap.add_argument("--out", default="output"); ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    rows = search(a.query, {"region": a.region, "lane": a.lane, "officer": a.officer}, a.out, lang=a.lang)
    for x in rows[:20]:
        print(f"{x['app_id']}  {x['score']:>3}  {x['reason']}")
    print(f"{len(rows)} {t('applications found', a.lang)}")
