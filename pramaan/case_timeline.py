"""WK25-21 Case timeline and case summary for one application (back-end for the case page; no UI here).
build_timeline(app_id) -> ordered events: submitted -> auto-checked -> assigned -> letter issued -> resubmitted -> EVC pack issued
-> decision -> appeal window -> closed. Each event: ts, actor, type, short audit hash (or "-" for events derived from the case
state), refs (finding / document ids). Only events that happened are listed; nothing is invented.
case_summary(app_id) -> header data: institute, Permanent Id, category, year, lane, trust score + top 3 reasons, assigned officer,
due date, appeal countdown, checklist counts, open deficiencies.
  python -m pramaan.case_timeline APP-02 [--out output] [--today 2026-10-26]        OWNER: Aryan."""
from __future__ import annotations

import argparse
import glob
import json
import os
from datetime import date

import yaml

from .appeal import status as appeal_status
from .assign import due_date
from .audit import AuditLog
from .checklist import counts, tick
from .i18n import t
from .schemas import ApplicationResult
from .trust import app_score

ORDER = ["submitted", "auto-checked", "assigned", "letter issued", "resubmitted", "EVC pack issued", "decision", "appeal window", "closed"]


def _load(app_id, out_dir, manifests_dir):
    res = ApplicationResult.model_validate_json(open(os.path.join(out_dir, f"{app_id}.result.json")).read())
    mp = os.path.join(manifests_dir, f"{app_id}.json")
    return res, (json.load(open(mp)) if os.path.exists(mp) else {})


def _ev(ts, actor, typ, h="-", refs=None, note=""):
    return {"ts": ts, "actor": actor, "type": typ, "hash": h[:12] if h and h != "-" else "-", "refs": refs or [], "note": note}


def build_timeline(app_id: str, out_dir: str = "output", audit_db: str | None = None, manifests_dir: str = "data/demo/apps",
                   today: date | None = None) -> list[dict]:
    audit_db = audit_db or os.path.join(out_dir, "audit.db")
    today = today or date.today()
    res, man = _load(app_id, out_dir, manifests_dir)
    with AuditLog(audit_db) as log:
        rows = log.rows(app_id)
        allrows = log.rows()
    ev = []
    if man.get("submitted_on"):
        ev.append(_ev(f"{man['submitted_on']}T00:00:00", "institute", "submitted", refs=[d["slot"] for d in man.get("documents", [])]))
    obs = [r for r in rows if r["action"] == "observation"]
    if obs:
        ev.append(_ev(obs[-1]["ts"], obs[-1]["actor"], "auto-checked", obs[-1]["hash"], [f.finding_id for f in res.findings],
                      f"lane {res.lane}"))
    asg = [r for r in rows if r["action"] == "case assigned"]
    if asg:
        ev.append(_ev(asg[-1]["ts"], asg[-1]["actor"], "assigned", asg[-1]["hash"], [json.loads(asg[-1]["detail"]).get("officer")]))
    elif man.get("declared", {}).get("assigned_officer") and obs:
        ev.append(_ev(obs[-1]["ts"], "system", "assigned", "-", [man["declared"]["assigned_officer"]], "derived from the manifest"))
    lods = [r for r in rows if r["action"] == "letter of deficiency finalised"]
    for r in lods:
        ev.append(_ev(r["ts"], r["actor"], "letter issued", r["hash"],
                      [f.finding_id for f in res.findings if f.lane == "return_for_rectification"]))
    pid = man.get("permanent_id")
    if pid:                                                    # a later application of the same institute = resubmission
        for p in sorted(glob.glob(os.path.join(manifests_dir, "*.json"))):
            m2 = json.load(open(p))
            if m2.get("permanent_id") == pid and m2["app_id"] > app_id:
                got = [r for r in allrows if r["app_id"] == m2["app_id"] and r["action"] == "application received"]
                if got:
                    ev.append(_ev(got[0]["ts"], "institute", "resubmitted", got[0]["hash"], [m2["app_id"]], f"as {m2['app_id']}"))
    for r in rows:
        if r["action"] == "EVC pack sealed":
            ev.append(_ev(r["ts"], r["actor"], "EVC pack issued", r["hash"]))
        elif r["action"].startswith("decision"):
            ev.append(_ev(r["ts"], r["actor"], "decision", r["hash"], note=r["action"].split(": ", 1)[-1]))
    ap = appeal_status(rows, app_id, today)
    if ap:
        ev.append(_ev(f"{ap['deadline']}T23:59:59", "system", "appeal window", "-", note=f"{ap['state']}; {ap['clause']}"))
        if ap["state"] == "closed (read-only)":
            last = max(r["ts"] for r in rows if r["action"].startswith("decision"))
            ev.append(_ev(max(last, f"{ap['deadline']}T23:59:59"), "system", "closed", "-", note="read-only"))
    return sorted(ev, key=lambda e: (e["ts"], ORDER.index(e["type"])))


def case_summary(app_id: str, out_dir: str = "output", audit_db: str | None = None, manifests_dir: str = "data/demo/apps",
                 today: date | None = None, settings_path: str = "config/settings.yaml", lang: str = "en") -> dict:
    audit_db = audit_db or os.path.join(out_dir, "audit.db")
    today = today or date.today()
    res, man = _load(app_id, out_dir, manifests_dir)
    with AuditLog(audit_db) as log:
        rows = log.rows(app_id)
    asg = [json.loads(r["detail"]).get("officer") for r in rows if r["action"] == "case assigned"]
    sc = app_score(res, lang)
    settings = yaml.safe_load(open(settings_path)) or {}
    obs = [r for r in rows if r["action"] == "observation"]
    since = date.fromisoformat(obs[-1]["ts"][:10]) if obs else today
    return {"app_id": app_id, "institute": man.get("declared", {}).get("institute_name"), "permanent_id": man.get("permanent_id"),
            "category": res.category, "academic_year": res.academic_year, "lane": res.lane, "trust_score": sc["score"],
            "trust_reasons": sc["reasons"][:3], "trust_label": sc["label"],
            "assigned_officer": asg[-1] if asg else man.get("declared", {}).get("assigned_officer"),
            "due_by": due_date(res, since, settings).isoformat(), "appeal": appeal_status(rows, app_id, today),
            "checklist": counts(tick(res, lang=lang), lang),
            "open_deficiencies": [t(f.title, lang) for f in res.findings if f.lane == "return_for_rectification"]}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("app_id"); ap.add_argument("--out", default="output"); ap.add_argument("--today", default=None)
    ap.add_argument("--lang", default="en")
    a = ap.parse_args()
    td = date.fromisoformat(a.today) if a.today else None
    s = case_summary(a.app_id, a.out, today=td, lang=a.lang)
    print(f"{s['app_id']}  {s['institute']}  ({s['permanent_id']}, {s['academic_year']})  {t('lane', a.lang)}: {t(s['lane'].replace('_', ' '), a.lang)}")
    print(f"  {t('Trust score', a.lang)} {s['trust_score']}/100 ({s['trust_label']}); {t('Checklist', a.lang)}: {s['checklist']}; "
          f"{t('Assigned officer', a.lang)}: {s['assigned_officer']}; {t('Due by', a.lang)} {s['due_by']}")
    for e in build_timeline(a.app_id, a.out, today=td):
        print(f"  {e['ts'][:19].replace('T', ' ')}  {t(e['type'], a.lang):16s} {e['actor']:16s} #{e['hash']}  {e['note']}")
