"""Officer dashboard (Streamlit). Run from the repo root:  streamlit run dashboard/app.py
Reads output/*.result.json written by the pipeline. The officer decides; every decision goes into the audit log.
UNTESTED by the author (Streamlit not installable in his sandbox). OWNER: Aryan (reference version)."""
import glob
import json
import os
import sys
from datetime import date

import streamlit as st
import yaml
from PIL import Image, ImageDraw

sys.path.insert(0, os.getcwd())
from pramaan.audit import AuditLog  # noqa: E402
from pramaan.pipeline import run_application  # noqa: E402

OUT, DB = "output", "output/audit.db"
LANE = {"human_review": ("Send to human review", "#c2410c"), "return_for_rectification": ("Return for rectification", "#b86e00"),
        "clear": ("No issues found", "#1f7a3a")}
st.set_page_config(page_title="Pramaan AI - officer view", layout="wide")


def load():
    res = []
    for p in sorted(glob.glob(f"{OUT}/*.result.json")):
        with open(p) as f:
            res.append(json.load(f))
    return res


def page_image(path, page, boxes):
    try:
        if path.lower().endswith((".jpg", ".jpeg", ".png")):
            img = Image.open(path).convert("RGB")
        else:
            from pramaan.synth.raster import render_page
            img = render_page(path, dpi=110, page=page - 1)
        d = ImageDraw.Draw(img); W, H = img.size
        for b in boxes:
            d.rectangle([b["x0"] * W - 3, b["y0"] * H - 3, b["x1"] * W + 3, b["y1"] * H + 3], outline=(220, 38, 38), width=3)
        return img
    except Exception as e:
        st.caption(f"preview not available: {e}")
        return None


def users(path="config/users.yaml"):
    with open(path) as f:
        cfg = yaml.safe_load(f) or {}
    return cfg.get("users", []), cfg.get("roles", {})


def view_once(log, user, app_id, what):
    """Audit every page view, once per (user, page) change, not on every Streamlit rerun."""
    key = (user["id"], app_id, what)
    if st.session_state.get("last_view") != key:
        log.append(user["id"], user["role"], f"page view: {what}", app_id, {"ui": "dashboard"})
        st.session_state["last_view"] = key


st.sidebar.title("Pramaan AI")
st.sidebar.caption("AI advisory only. The officer decides. The tool never rejects.")
USERS, ROLES = users()
user = st.sidebar.selectbox("Sign in as", USERS, format_func=lambda u: f"{u['name']} ({u['role']})")
PERMS = set(ROLES.get(user["role"], []))
st.sidebar.caption("demo users, no passwords (designed for SSO)")
os.makedirs(OUT, exist_ok=True)
log = AuditLog(DB)
if st.session_state.get("signed_in") != user["id"]:
    log.append(user["id"], user["role"], "sign in", None, {"permissions": sorted(PERMS), "auth": "demo, no password"})
    st.session_state["signed_in"] = user["id"]
if "run_pipeline" in PERMS:
    if st.sidebar.button("Run pipeline on demo applications"):
        with st.spinner("Processing..."):
            for m in sorted(glob.glob("data/demo/apps/*.json")):
                run_application(m, OUT, date(2026, 10, 26), DB)
        log.append(user["id"], user["role"], "run pipeline", None, {"apps": "data/demo/apps/*.json"})
        st.sidebar.success("Done")
else:
    st.sidebar.caption("Running the pipeline needs the admin role.")
if "read" not in PERMS:
    st.warning("This role cannot view applications.")
    st.stop()
results = load()
if not results:
    st.info("No results yet. Click 'Run pipeline on demo applications' in the sidebar.")
    st.stop()
lane_f = st.sidebar.multiselect("Lane", list(LANE), default=list(LANE))
rows = sorted((r for r in results if r["lane"] in lane_f), key=lambda r: -r.get("priority", 0.0))
st.subheader("Queue")
st.dataframe([{"application": r["app_id"], "priority": r.get("priority", 0.0), "lane": LANE[r["lane"]][0], "findings": len(r["findings"]),
               "high": sum(f["severity"] == "high" for f in r["findings"]),
               "earliest due": min((a["due_by"] for a in r["alerts"]), default="-"), "seconds": r["seconds_taken"]} for r in rows],
             width="stretch", hide_index=True)
if not rows:
    st.stop()
app = st.selectbox("Open application", [r["app_id"] for r in rows])
r = next(x for x in rows if x["app_id"] == app)
view_once(log, user, app, "application")
label, col = LANE[r["lane"]]
st.markdown(f"<div style='background:{col};color:white;padding:10px 16px;border-radius:6px;font-size:20px;display:inline-block'>"
            f"{label}</div> &nbsp; <span style='color:#555'>advisory, {len(r['findings'])} findings</span>", unsafe_allow_html=True)
left, right = st.columns([1, 1])
docs = {d["doc_id"]: d for d in r["documents"]}
with left:
    st.markdown("#### Findings")
    for i, f in enumerate(sorted(r["findings"], key=lambda f: ["human_review", "return_for_rectification", "info"].index(f["lane"]))):
        with st.expander(f"[{f['severity'].upper()}] {f['title']}", expanded=i < 2):
            st.write(f["reason"])
            st.caption(f"{f['source']} | {f['rule_id']} | confidence {f['confidence']:.0%} | lane: {f['lane']}")
            if f.get("aph_clause"):
                st.caption(f"Handbook: {f['aph_clause']}" + ("" if f["clause_verified"] else "  (clause UNVERIFIED)"))
            for e in f["evidence"]:
                if st.button(f"Show evidence: {e['doc_id']} p.{e['page']}", key=f"{f['finding_id']}-{e['doc_id']}-{e['page']}"):
                    st.session_state["ev"] = e
    st.markdown("#### Verification (MOCK = simulated source)")
    st.dataframe([{"document": v["doc_id"], "method": v["method"], "source": v["source"], "status": v["status"],
                   "mock": "MOCK" if v["mock"] else "real", "note": v["note"]} for v in r["verifications"]], hide_index=True)
    st.markdown("#### Verification timeline (from the audit log; MOCK sources, designed for integration)")
    tl: dict = {}
    for x in log.rows(app):
        if x["action"] == "source response":
            dd = json.loads(x["detail"] or "{}")
            steps = tl.setdefault((dd.get("doc_id"), dd.get("method")), [])
            if not steps or (steps[-1]["status"], steps[-1]["source"]) != (dd.get("status"), dd.get("source")):
                steps.append({"ts": x["ts"], "status": dd.get("status"), "source": dd.get("source"), "hash": dd.get("payload_hash") or ""})
    for (doc_id, method), steps in sorted(tl.items(), key=lambda kv: (-len(kv[1]), str(kv[0]))):
        st.markdown(f"**{doc_id}** ({method}): " + " &rarr; ".join(
            f"`{e['status']}` at {str(e['ts'])[:19].replace('T', ' ')} <span style='color:#777'>({e['source']}, "
            f"payload {e['hash'][:12]})</span>" for e in steps), unsafe_allow_html=True)
with right:
    st.markdown("#### Document")
    ev = st.session_state.get("ev")
    if ev and ev["doc_id"] in docs:
        d = docs[ev["doc_id"]]
        img = page_image(d["path"], ev["page"], [ev["bbox"]] if ev.get("bbox") else [])
        if img is not None:
            st.image(img, caption=f"{d['filename']} ({d['doc_type']}) - red box = evidence", width="stretch")
    else:
        st.caption("Click 'Show evidence' on a finding to see the highlighted region.")
st.markdown("#### Officer decision")
c1, c2 = st.columns([2, 1])
comment = c1.text_input("Reason (required)", key=f"c-{app}")
decision = c2.selectbox("Decision", ["Approve for next step", "Return for rectification", "Send to expert review"], key=f"d-{app}")
if "decide" not in PERMS:
    st.info(f"Signed in as {user['role']}: read only. Only a scrutiny officer can record a decision.")
elif st.button("Record decision"):
    if not comment.strip():
        st.error("Write a reason first. Every decision needs one.")
    else:
        log.append(user["id"], user["role"], f"decision: {decision}", app, {"comment": comment, "ai_lane": r["lane"]})
        st.success("Decision recorded in the audit log.")
ok, bad = log.verify_chain()
st.caption(f"Audit chain: {'intact' if ok else f'BROKEN at row {bad}'} | head {log.head()[:16]}...")
with st.expander("Audit log for this application"):
    st.dataframe([{k: x.get(k) for k in ("id", "ts", "actor", "role", "action", "hash")} for x in log.rows(app)], hide_index=True)
