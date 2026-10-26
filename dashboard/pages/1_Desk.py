"""WK23 Desk: the officer's daily page. Applications by priority with trust score and checklist; per application the
checklist (with evidence), trust reasons, the Letter of Deficiency editor + sealed export, the resubmission diff; and the
one-click clear queue with its mandatory spot check. Advisory only: the officer decides; decisions go to the audit log."""
import json
import os
import sys
from datetime import date

import streamlit as st

sys.path.insert(0, os.getcwd())
from dashboard.ui import DB, OUT, manifests, results, rtl, sidebar, t  # noqa: E402
from pramaan.audit import AuditLog  # noqa: E402
from pramaan.checklist import counts, tick  # noqa: E402
from pramaan.evc_pack import evc_pack  # noqa: E402
from pramaan.letters import build_lod, export_docx, save_final, to_html  # noqa: E402
from pramaan.queue import SpotCheckIncomplete, approve_batch, batch_seed, clear_queue, spot_sample  # noqa: E402
from pramaan.resubmit import compare  # noqa: E402
from pramaan.seal import seal_html  # noqa: E402
from pramaan.trust import app_score  # noqa: E402

st.set_page_config(page_title="Pramaan - Desk", layout="wide")
user = sidebar("Desk")
res, mans = results(), manifests()
if not res:
    st.warning(t("No results yet. Run the pipeline first (python -m pramaan.demo --no-dashboard)."))
    st.stop()
by_id = {r.app_id: r for r in res}
COLOUR = {"green": "🟢", "amber": "🟠", "red": "🔴", "grey": "⚪"}

st.title(t("Desk"))
rows = []
for r in sorted(res, key=lambda r: -r.priority):
    m = mans.get(r.app_id, {}).get("declared", {})
    rows.append({t("Application"): r.app_id, t("Lane"): t(r.lane.replace("_", " ")), t("Priority"): round(r.priority, 2),
                 t("Trust score"): app_score(r, st.session_state.get("lang", "en"))["score"], t("Checklist"): counts(tick(r)),
                 t("Region"): m.get("region", ""), t("Assigned officer"): m.get("assigned_officer", "")})
st.dataframe(rows, hide_index=True, width="stretch")
st.caption(t("Trust score: designed score, not a probability (weights in config/settings.yaml)."))

tab_app, tab_queue = st.tabs([t("Application"), t("Clear queue")])
with tab_app:
    app_id = st.selectbox(t("Open application"), [r[t("Application")] for r in rows])
    r, m = by_id[app_id], mans.get(app_id, {})
    c1, c2 = st.columns([3, 2])
    with c1:
        st.subheader(t("Checklist") + f" — {counts(tick(r))}")
        for row in tick(r):
            with st.expander(f"{COLOUR[row['status']]} {row['id']} {row['item']}" + (f"  ({row['ref']})" if row["ref"] else "")):
                rtl(row["why"])
                for e in row["evidence"][:3]:
                    st.caption(f"{t('Evidence')}: {e['doc_id']} p.{e['page']}" + (f" — {e['text']}" if e.get("text") else ""))
    with c2:
        sc = app_score(r)
        st.subheader(t("Trust score") + f": {sc['score']}/100")
        st.caption(sc["label"])
        for why in sc["reasons"]:
            st.write("- " + why)
        prev = [a for a, mm in mans.items() if mm.get("permanent_id") == m.get("permanent_id") and a < app_id and a in by_id]
        if prev:
            d = compare(by_id[prev[-1]], r)
            st.subheader(t("Resubmission of") + f" {prev[-1]}")
            st.info(d["summary"])
            st.dataframe([{t("Deficiency"): x["title"], t("Status"): t(x["status"])} for x in d["deficiencies"]], hide_index=True)
            st.dataframe([{t("Document"): x["slot"], t("Status"): t(x["status"])} for x in d["changed_documents"]], hide_index=True)

    st.subheader(t("Letter of Deficiency (draft)"))
    lod = build_lod(r, institute=m.get("declared", {}).get("institute_name", "[Institute name]"),
                    permanent_id=m.get("permanent_id", "[Permanent Id]"), lang=st.session_state.get("lang", "en"))
    text = st.text_area(t("Edit the letter before export"), lod["text"], height=320, key=f"lod-{app_id}")
    if lod["notes"]:
        st.caption(t("Internal notes (not sent to the institute)") + ": " + "; ".join(n["what"] for n in lod["notes"]))
    b1, b2, b3, b4 = st.columns(4)
    if b1.button(t("Finalise letter (audit log)"), disabled=user["role"] != "scrutiny_officer"):
        with AuditLog(DB) as log:
            st.success(t("Stored in the audit log") + f": {save_final(log, user, app_id, text)[:16]}...")
    with AuditLog(DB) as log:
        sealed = seal_html(to_html(text, lod["notes"]), app_id, log, kind="letter of deficiency") if b2.button(t("Seal for export")) else None
    if sealed:
        st.session_state[f"sealed-{app_id}"] = sealed
    if st.session_state.get(f"sealed-{app_id}"):
        b3.download_button(t("Download sealed HTML"), st.session_state[f"sealed-{app_id}"], f"{app_id}_LoD.html", "text/html")
    path = os.path.join(OUT, f"{app_id}_LoD.docx")
    if export_docx(text, path):
        b4.download_button(t("Download .docx"), open(path, "rb").read(), os.path.basename(path))

    st.subheader(t("Expert Visit Committee pack"))
    if st.button(t("Build EVC visit pack (sealed)")):
        recs = json.load(open("data/aicte_records.json")) if os.path.exists("data/aicte_records.json") else {}
        with AuditLog(DB) as log:
            st.session_state[f"evc-{app_id}"] = evc_pack(r, recs.get(m.get("permanent_id")), log, lang=st.session_state.get("lang", "en"))
    if st.session_state.get(f"evc-{app_id}"):
        st.download_button(t("Download EVC pack"), st.session_state[f"evc-{app_id}"], f"{app_id}_EVC_pack.html", "text/html")
        st.html(st.session_state[f"evc-{app_id}"])

with tab_queue:
    q = clear_queue(res)
    ids = [r.app_id for r in q]
    st.subheader(t("Clear queue") + f": {len(ids)}")
    st.write(", ".join(ids) or t("Nothing to clear."))
    if ids:
        seed = batch_seed(ids, date.today().isoformat())
        sample = spot_sample(ids, seed)
        opened = st.session_state.setdefault("opened", set())
        st.write(t("Spot check: open these first") + f" ({len(sample)} of {len(ids)})")
        for a in sample:
            if st.button(f"{t('Open')} {a}", key=f"open-{a}"):
                opened.add(a)
            st.caption(f"{a}: {t('opened') if a in opened else t('not opened yet')}")
        ready = all(a in opened for a in sample)
        if st.button(t("Approve batch"), disabled=not ready or user["role"] != "scrutiny_officer"):
            try:
                with AuditLog(DB) as log:
                    hs = approve_batch(log, user, q, opened, seed)
                st.success(t("Approved") + f": {len(hs)} — " + t("auto-cleared, spot-checked") + f" {len(sample)} / {len(ids)}")
            except SpotCheckIncomplete as e:
                st.error(str(e))
