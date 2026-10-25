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
from pramaan.audit import GENESIS, AuditLog  # noqa: E402

OUT, DB = "output", "output/audit.db"
LANES = ("clear", "return_for_rectification", "human_review")
SOURCES = ("rule", "crosscheck", "pdf_forensics", "tamper_model", "photo", "verification")
DECISION_LANE = {"Approve for next step": "clear", "Return for rectification": "return_for_rectification",
                 "Send to expert review": "human_review"}
st.set_page_config(page_title="Pramaan AI - analytics", layout="wide")


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


st.title("Analytics")
st.caption("Read only. AI output is advisory; officers decide. MOCK verification sources are simulated (designed for integration).")
res = results()
rows, chain_ok, bad_id = audit_rows()
if not res:
    st.info("No results yet: run the pipeline (officer view, admin role) to fill output/.")
today = st.sidebar.date_input("Check SLA due dates against", value=date.today())

c = st.columns(4)
c[0].metric("Applications", len(res))
c[1].metric("Findings", sum(len(r["findings"]) for r in res))
c[2].metric("Mean processing seconds", f"{sum(r['seconds_taken'] for r in res) / len(res):.2f}" if res else "-")
c[3].metric("Audit chain", {True: "intact", False: f"BROKEN at row {bad_id}", None: "no audit log"}[chain_ok])

left, right = st.columns(2)
with left:
    st.markdown("#### Applications per lane")
    lanes = Counter(r["lane"] for r in res)
    st.dataframe([{"lane": k, "applications": lanes.get(k, 0)} for k in LANES], hide_index=True, width="stretch")
    st.markdown("#### Findings per source")
    src = Counter(f["source"] for r in res for f in r["findings"])
    st.dataframe([{"source": k, "findings": src.get(k, 0)} for k in SOURCES], hide_index=True, width="stretch")
with right:
    st.markdown("#### Alerts by kind")
    st.caption(f"Overdue = due date before {today.isoformat()}. SLA days are configurable ASSUMPTIONS (config/settings.yaml), not AICTE rules.")
    kinds: dict = {}
    for r in res:
        for a in r["alerts"]:
            k = kinds.setdefault(a["kind"], [0, 0]); k[0] += 1; k[1] += int(a["due_by"] < today.isoformat())
    st.dataframe([{"kind": k, "alerts": v[0], "overdue": v[1], "within SLA": v[0] - v[1]} for k, v in sorted(kinds.items())]
                 or [{"kind": "-", "alerts": 0, "overdue": 0, "within SLA": 0}], hide_index=True, width="stretch")
    st.markdown("#### Pending verifications")
    pend = [{"application": r["app_id"], "document": v["doc_id"], "method": v["method"], "source": v["source"], "since": v["timestamp"][:19]}
            for r in res for v in r["verifications"] if v["status"] == "verification_pending"]
    if pend:
        st.dataframe(pend, hide_index=True, width="stretch")
    else:
        st.caption("None pending.")

st.markdown("#### Officer decisions vs AI lane")
dec = []
for x in rows:
    if x["action"].startswith("decision: "):
        d = json.loads(x["detail"] or "{}"); choice = x["action"][len("decision: "):]
        dec.append({"ts": x["ts"], "application": x["app_id"], "officer": x["actor"], "role": x["role"], "decision": choice,
                    "AI lane": d.get("ai_lane"), "agrees": DECISION_LANE.get(choice) == d.get("ai_lane")})
if not dec:
    st.info("no decisions yet")
else:
    agree = sum(d["agrees"] for d in dec)
    st.metric("Agreement (officer decision maps to the AI lane)", f"{agree / len(dec):.0%}", help=f"{agree} of {len(dec)} decisions")
    st.caption("Mapping: Approve for next step = clear; Return for rectification = return_for_rectification; "
               "Send to expert review = human_review. Every decision counts (an application may have several).")
    st.dataframe(dec, hide_index=True, width="stretch")

st.markdown("#### Latest 50 audit rows")
st.caption({True: "Chain intact: every row's hash recomputes from the previous one.",
            False: f"Chain BROKEN at row {bad_id}: a row was changed or removed.", None: "No audit log yet."}[chain_ok])
st.dataframe([{k: x[k] for k in ("id", "ts", "actor", "role", "action", "app_id")} | {"hash": x["hash"][:16]} for x in rows[-50:][::-1]],
             hide_index=True, width="stretch")
