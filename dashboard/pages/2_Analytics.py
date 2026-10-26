"""Analytics page (Streamlit multipage: appears next to the officer view when you run  streamlit run dashboard/app.py).
READ ONLY: reads output/*.result.json and output/audit.db (opened read-only); writes nothing, not even page views.
OWNER: Aryan."""
import glob
import json
import os
import sqlite3
import sys
from collections import Counter
from datetime import date

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, os.getcwd())
from pramaan.audit import GENESIS, AuditLog  # noqa: E402

OUT = os.environ.get("PRAMAAN_OUT", "output")
DB = os.path.join(OUT, "audit.db")
LANES = ("clear", "return_for_rectification", "human_review")
SOURCES = ("rule", "crosscheck", "pdf_forensics", "tamper_model", "photo", "verification")
DECISION_LANE = {"Approve for next step": "clear", "Return for rectification": "return_for_rectification",
                 "Send to expert review": "human_review"}
st.set_page_config(page_title="Pramaan AI - analytics", layout="wide")
from dashboard.ui import language, show_table, t  # noqa: E402  (WK23-17)
language()


def results() -> list[dict]:
    out = []
    for p in sorted(glob.glob(f"{OUT}/*.result.json")):
        try:
            with open(p) as f:
                out.append(json.load(f))
        except Exception:
            continue
    return out


def audit_rows() -> tuple[list[dict], bool | None, int | None]:
    """All rows + chain status, from a read-only connection (same hash as pramaan.audit.AuditLog.verify_chain)."""
    if not os.path.exists(DB):
        return [], None, None
    con = sqlite3.connect(f"file:{os.path.abspath(DB)}?mode=ro", uri=True)
    try:
        cols = ["id", "ts", "actor", "role", "action", "app_id", "detail", "prev_hash", "hash"]
        rows = [dict(zip(cols, r)) for r in con.execute(f"SELECT {', '.join(cols)} FROM audit ORDER BY id")]
    except sqlite3.Error:
        return [], None, None
    finally:
        con.close()
    prev = GENESIS
    for r in rows:
        if r["prev_hash"] != prev or AuditLog._h(prev, r["ts"], r["actor"], r["role"], r["action"], r["app_id"], r["detail"]) != r["hash"]:
            return rows, False, r["id"]
        prev = r["hash"]
    return rows, True, None


st.title(t("Analytics"))
st.caption(t("Read only. AI output is advisory; officers decide. MOCK verification sources are simulated (designed for integration)."))
res = results()
rows, chain_ok, bad_id = audit_rows()
if not res:
    st.info(t("No results yet: run the pipeline (officer view, admin role) to fill output/."))
today = st.sidebar.date_input("Check SLA due dates against", value=date.today())

c = st.columns(4)
c[0].metric(t("Applications"), len(res))
c[1].metric(t("Findings"), sum(len(r["findings"]) for r in res))
c[2].metric(t("Mean processing seconds"), f"{sum(r['seconds_taken'] for r in res) / len(res):.2f}" if res else "-")
c[3].metric(t("Audit chain"), t({True: "intact", False: f"BROKEN at row {bad_id}", None: "no audit log"}[chain_ok]))

left, right = st.columns(2)
with left:
    st.markdown("#### " + t("Applications per lane"))
    lanes = Counter(r["lane"] for r in res)
    show_table([{"lane": k, "applications": lanes.get(k, 0)} for k in LANES], hide_index=True, width="stretch")
    st.markdown("#### " + t("Findings per source"))
    src = Counter(f["source"] for r in res for f in r["findings"])
    show_table([{"source": k, "findings": src.get(k, 0)} for k in SOURCES], hide_index=True, width="stretch")
with right:
    st.markdown("#### " + t("Alerts by kind"))
    st.caption(t(f"Overdue = due date before {today.isoformat()}. SLA days are configurable ASSUMPTIONS (config/settings.yaml), not AICTE rules."))
    kinds: dict = {}
    for r in res:
        for a in r["alerts"]:
            k = kinds.setdefault(a["kind"], [0, 0]); k[0] += 1; k[1] += int(a["due_by"] < today.isoformat())
    show_table([{"kind": k, "alerts": v[0], "overdue": v[1], "within SLA": v[0] - v[1]} for k, v in sorted(kinds.items())]
                 or [{"kind": "-", "alerts": 0, "overdue": 0, "within SLA": 0}], hide_index=True, width="stretch")
    st.markdown("#### " + t("Pending verifications"))
    pend = [{"application": r["app_id"], "document": v["doc_id"], "method": v["method"], "source": v["source"], "since": v["timestamp"][:19]}
            for r in res for v in r["verifications"] if v["status"] == "verification_pending"]
    if pend:
        show_table(pend, hide_index=True, width="stretch")
    else:
        st.caption(t("None pending."))

st.markdown("#### " + t("Officer decisions vs AI lane"))
dec = []
for x in rows:
    if x["action"].startswith("decision: "):
        d = json.loads(x["detail"] or "{}"); choice = x["action"][len("decision: "):]
        dec.append({"ts": x["ts"], "application": x["app_id"], "officer": x["actor"], "role": x["role"], "decision": choice,
                    "AI lane": d.get("ai_lane"), "agrees": DECISION_LANE.get(choice) == d.get("ai_lane")})
if not dec:
    st.info(t("no decisions yet"))
else:
    agree = sum(d["agrees"] for d in dec)
    st.metric(t("Agreement (officer decision maps to the AI lane)"), f"{agree / len(dec):.0%}", help=f"{agree} of {len(dec)} decisions")
    st.caption(t("Mapping: Approve for next step = clear; Return for rectification = return_for_rectification; "
               "Send to expert review = human_review. Every decision counts (an application may have several)."))
    show_table(dec, hide_index=True, width="stretch")

st.markdown("#### " + t("Latest 50 audit rows"))
st.caption(t({True: "Chain intact: every row's hash recomputes from the previous one.",
            False: f"Chain BROKEN at row {bad_id}: a row was changed or removed.", None: "No audit log yet."}[chain_ok]))
show_table([{k: x[k] for k in ("id", "ts", "actor", "role", "action", "app_id")} | {"hash": x["hash"][:16]} for x in rows[-50:][::-1]],
             hide_index=True, width="stretch")

# ---------------- WK23-16 leadership view (read only) ----------------
from pramaan import analytics as A  # noqa: E402
from pramaan.schemas import ApplicationResult  # noqa: E402

st.markdown("## " + t("Leadership view"))
RES = [ApplicationResult.model_validate(x) for x in results()]
MANS = {}
for p in sorted(glob.glob(os.path.join(os.environ.get("PRAMAAN_APPS", "data/demo/apps"), "*.json"))):
    m = json.load(open(p)); MANS[m["app_id"]] = m
c1, c2, c3 = st.columns(3)
k, n = A.auto_cleared_share(RES, rows)
c1.metric(t("Share auto-cleared (clear-queue batches)"), f"{k} of {n}")
med = A.median_processing_days(RES, MANS)
c2.metric(t("Median processing time (days, synthetic)"), "-" if med is None else f"{med:g}",
          help=t("Synthetic: demo submission dates vs the pipeline run time. Not a measured office figure."))
br = A.sla_breaches(RES, rows, date.today())
c3.metric(t("SLA breaches (alerts past due, no decision)"), len(br))
st.markdown("#### " + t("Top 10 deficiencies"))
show_table([{"deficiency": title, "count": c} for title, c in A.top_deficiencies(RES)], hide_index=True, width="stretch")
st.markdown("#### " + t("Deficiencies by region"))
show_table([{"region": k2, **v} for k2, v in A.by_region(RES, MANS).items()], hide_index=True, width="stretch")
st.markdown("#### " + t("Lane split"))
st.bar_chart({t(k.replace("_", " ")): v for k, v in A.lane_split(RES).items()})
st.markdown("#### " + t("False-alarm rate per rule (officer feedback)"))
fa = A.false_alarms_readonly(DB)
if fa:
    show_table([{"rule": r2, **v} for r2, v in sorted(fa.items())], hide_index=True, width="stretch")
else:
    st.caption(t("No officer feedback yet."))
if br:
    st.markdown("#### " + t("SLA breaches"))
    show_table(br, hide_index=True, width="stretch")
