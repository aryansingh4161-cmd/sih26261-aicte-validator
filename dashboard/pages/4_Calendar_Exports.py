"""WK23 Calendar & Exports: my queue (assignment + SLA), certificate expiries (month table, overdue, reminders, .ics),
RTI / appeal case export, MOCK notification outbox."""
import os
import sys
from datetime import date

import streamlit as st
import yaml

sys.path.insert(0, os.getcwd())
from dashboard.ui import DB, OUT, manifests, results, sidebar, t  # noqa: E402
from pramaan.assign import assign, due_date, my_queue  # noqa: E402
from pramaan.expiry import days_left, expiries, overdue, reminders, to_ics  # noqa: E402
from pramaan.export_case import export_case  # noqa: E402
from pramaan.outbox import log as outbox_log  # noqa: E402

st.set_page_config(page_title="Pramaan - Calendar & Exports", layout="wide")
user = sidebar("Calendar & Exports")
res, mans = results(), manifests()
if not res:
    st.warning(t("No results yet. Run the pipeline first (python -m pramaan.demo --no-dashboard).")); st.stop()
settings = yaml.safe_load(open("config/settings.yaml")) or {}
today = date.today()
st.title(t("Calendar & Exports"))

st.subheader(t("My queue"))
users = yaml.safe_load(open("config/users.yaml"))["users"]
a = assign(res, mans, users)
mine = my_queue(a, user["id"], res)
if mine:
    st.dataframe([{t("Application"): r.app_id, t("Lane"): t(r.lane.replace("_", " ")), t("Priority"): round(r.priority, 2),
                   t("Due by"): due_date(r, today, settings).isoformat()} for r in mine], hide_index=True, width="stretch")
else:
    st.write(t("Nothing assigned to you. Officers are assigned by region (config/users.yaml)."))
st.caption(t("Due dates: SLA days by lane in config/settings.yaml (assumption)."))

st.subheader(t("Certificate expiries"))
rows = expiries(res)
od = overdue(rows, today)
st.write(t("Overdue") + f": {len(od)}")
if od:
    st.dataframe([{t("Application"): x["app_id"], t("Document"): x["doc_type"], t("Expired on"): x["expires"]} for x in od], hide_index=True)
month = st.selectbox(t("Month"), sorted({x["expires"][:7] for x in rows}))
st.dataframe([{t("Date"): x["expires"], t("Application"): x["app_id"], t("Document"): x["doc_type"], t("Days left"): days_left(x, today),
               t("From"): x["how"]} for x in rows if x["expires"].startswith(month)], hide_index=True, width="stretch")
c1, c2 = st.columns(2)
c1.download_button(t("Download calendar (.ics)"), to_ics(rows), "pramaan_expiries.ics", "text/calendar")
if c2.button(t("Queue reminders (MOCK outbox)")):
    st.success(t("Reminders queued") + f": {len(reminders(rows, today, settings.get('reminder_days', (60, 30, 7))))}")

st.subheader(t("RTI / appeal case export"))
app_id = st.selectbox(t("Application"), sorted(r.app_id for r in res))
if st.button(t("Build case ZIP")):
    zp = export_case(app_id, OUT, DB)
    st.download_button(t("Download case ZIP"), open(zp, "rb").read(), os.path.basename(zp), "application/zip")

st.subheader(t("Notification outbox (MOCK: nothing is sent)"))
box = outbox_log()
if box:
    st.dataframe([{t("Created"): x["created_at"], t("Channel"): x["channel"], t("To"): x["to"], t("Subject"): x["subject"]}
                  for x in box[-50:]], hide_index=True, width="stretch")
else:
    st.write(t("Outbox is empty."))
