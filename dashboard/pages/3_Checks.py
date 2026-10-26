"""WK23 Checks: findings with officer feedback, year-over-year changes, serial reuse across institutes, verification board."""
import os
import sys

import streamlit as st

sys.path.insert(0, os.getcwd())
from dashboard.ui import DB, manifests, results, rtl, sidebar, t  # noqa: E402
from pramaan.audit import AuditLog  # noqa: E402
from pramaan.feedback import false_alarm_rate, record  # noqa: E402
from pramaan.schemas import Application  # noqa: E402
from pramaan.verify_board import board  # noqa: E402

st.set_page_config(page_title="Pramaan - Checks", layout="wide")
user = sidebar("Checks")
res, mans = results(), manifests()
if not res:
    st.warning(t("No results yet. Run the pipeline first (python -m pramaan.demo --no-dashboard).")); st.stop()
by_id = {r.app_id: r for r in res}
st.title(t("Checks"))

st.subheader(t("Year-over-year changes (vs last year's MOCK record)"))
yoy = [{t("Application"): f.app_id, t("Check"): f.rule_id, t("Finding"): t(f.title), t("Reason"): t(f.reason)}
       for r in res for f in r.findings if f.rule_id.startswith("X-YOY")]
if yoy:
    st.dataframe(yoy, hide_index=True, width="stretch")
else:
    st.write(t("No unexplained changes."))

st.subheader(t("Serial reuse across institutes"))
ser = [{t("Application"): f.app_id, t("Finding"): t(f.title), t("Reason"): t(f.reason), t("Similarity"): f.confidence}
       for r in res for f in r.findings if f.rule_id == "X-SERIAL"]
if ser:
    st.dataframe(ser, hide_index=True, width="stretch")
else:
    st.write(t("No serial reuse found."))

app_id = st.selectbox(t("Open application"), sorted(by_id), key="checks-app")
r = by_id[app_id]
st.subheader(t("Verification board") + f" — {app_id}")
st.caption(t("MOCK rows come from simulated sources (docs/ADAPTERS.md)."))
if app_id in mans:
    st.dataframe([{t("Document"): x["document"], t("Source"): x["source"], t("Status"): x["status"], t("Checked at"): x["checked_at"],
                   t("Compared"): x["compared"]} for x in board(r, Application(**mans[app_id]), st.session_state.get("lang", "en"))],
                 hide_index=True, width="stretch")

st.subheader(t("Findings — was the tool right?"))
can = user["role"] == "scrutiny_officer"
for f in r.findings:
    with st.expander(f"[{f.severity.upper()}] {t(f.title)} ({f.rule_id})"):
        rtl(t(f.reason))
        note = st.text_input(t("Note (optional)"), key=f"note-{f.finding_id}")
        c1, c2 = st.columns(2)
        for col, verdict in ((c1, "correct"), (c2, "false alarm")):
            if col.button(t(verdict.capitalize()), key=f"{verdict}-{f.finding_id}", disabled=not can):
                with AuditLog(DB) as log:
                    record(DB, f, verdict, user, note, log)
                st.success(t("Thank you. Stored with your id and the time."))
rate = false_alarm_rate(DB)
if rate:
    st.caption(t("False-alarm rate per rule so far") + ": " + ", ".join(f"{k} {v['false_alarms']}/{v['n']}" for k, v in sorted(rate.items())))
