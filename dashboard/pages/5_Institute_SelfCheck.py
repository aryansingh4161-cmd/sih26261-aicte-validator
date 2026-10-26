"""WK23 Institute self-check (pre-submission). Role `institute`: sees only applications with its own Permanent Id, uploads its
files, runs the same engine in precheck mode and gets a plain-words to-do list. Marked SELF-CHECK; nothing goes into the
officer's audit log as a decision."""
import json
import os
import sys
from datetime import date

import streamlit as st

sys.path.insert(0, os.getcwd())
from dashboard.ui import OUT, lang, manifests, rtl, sidebar, t  # noqa: E402
from pramaan.schemas import DOC_TYPES  # noqa: E402
from pramaan.selfcheck import MARK, precheck, todo  # noqa: E402
from pramaan.i18n import t as tl  # noqa: E402

st.set_page_config(page_title="Pramaan - Institute self-check", layout="wide")
user = sidebar("Institute self-check", roles=("institute",))
mans = manifests()
pid = user.get("permanent_id", "")
if pid.startswith("from_app "):                                  # demo user: the Permanent Id of a demo application
    pid = mans.get(pid.split()[1], {}).get("permanent_id", "")
mine = {a: m for a, m in mans.items() if m.get("permanent_id") == pid}
st.title(t("Institute self-check"))
st.warning(t(MARK))
work = os.path.join(OUT, "selfcheck", user["id"])

mode = st.radio(t("What do you want to check?"), [t("One of my applications"), t("Files I upload now")])
manifest = None
if mode == t("One of my applications"):
    if not mine:
        st.write(t("No applications found for your Permanent Id.")); st.stop()
    app_id = st.selectbox(t("Application"), sorted(mine))
    manifest = f"data/demo/apps/{app_id}.json"
else:
    files = st.file_uploader(t("Upload your documents (PDF or scans)"), accept_multiple_files=True)
    slots = {}
    for f in files or []:
        slots[f.name] = st.selectbox(f"{t('Document type of')} {f.name}", [d for d in DOC_TYPES if d != "unclassified"], key=f.name)
    if files and mine:
        up = os.path.join(work, "upload"); os.makedirs(up, exist_ok=True)
        base = mans[sorted(mine)[-1]]
        docs = []
        for f in files:
            p = os.path.join(up, os.path.basename(f.name)); open(p, "wb").write(f.getbuffer()); docs.append({"slot": slots[f.name], "path": p})
        m = {**base, "app_id": f"SELF-{user['id']}", "documents": docs, "photos": []}
        manifest = os.path.join(up, "manifest.json"); json.dump(m, open(manifest, "w"), indent=1)

if manifest and st.button(t("Run self-check")):
    r = precheck(manifest, work, date.today())
    st.session_state["selfcheck"] = (r.model_dump_json(), r.lane)
if st.session_state.get("selfcheck"):
    from pramaan.schemas import ApplicationResult
    r = ApplicationResult.model_validate_json(st.session_state["selfcheck"][0])
    st.subheader(t("Your to-do list"))
    items = todo(r, date.today(), lang())
    for i in items:
        rtl("- " + i)
    if lang() != "en":                                            # English + chosen language side by side
        both = "\n".join(f"{tl(x, 'en')}\n    {x}" for x in todo(r, date.today(), "en"))
    else:
        both = "\n".join(items)
    st.download_button(t("Download to-do list"), "SELF-CHECK\n" + both, f"{r.app_id}_todo.txt")
