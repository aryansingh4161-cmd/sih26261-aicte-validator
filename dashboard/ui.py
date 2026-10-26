"""Shared helpers for the WK23 dashboard pages: sign-in, language, results + manifests, audit. Every visible string -> t()."""
import glob
import json
import os
import sys

import streamlit as st
import yaml

sys.path.insert(0, os.getcwd())
from pramaan.audit import AuditLog  # noqa: E402
from pramaan.i18n import LANGUAGES, banner, t as _t  # noqa: E402
from pramaan.schemas import ApplicationResult  # noqa: E402

OUT = os.environ.get("PRAMAAN_OUT", "output")                  # tests point the pages at their own folder
DB, APPS = os.path.join(OUT, "audit.db"), os.environ.get("PRAMAAN_APPS", "data/demo/apps")


def lang() -> str:
    return st.session_state.get("lang", "en")


def t(text: str) -> str:
    return _t(text, lang())


def sidebar(page: str, roles: tuple = ("scrutiny_officer", "admin", "viewer")) -> dict:
    """Language selector + sign-in (demo users, no passwords). Returns the signed-in user; logs one page view per change."""
    names = list(LANGUAGES)
    st.session_state["lang"] = st.sidebar.selectbox("Language / भाषा", names, index=names.index(lang()),
                                                    format_func=lambda k: LANGUAGES[k])
    if lang() != "en":
        st.sidebar.info(banner(lang()))
    with open("config/users.yaml") as f:
        users = [u for u in (yaml.safe_load(f) or {}).get("users", []) if u["role"] in roles]
    user = st.sidebar.selectbox(t("Sign in as"), users, format_func=lambda u: f"{u['name']} ({u['role']})")
    st.sidebar.caption(t("AI advisory only. The officer decides."))
    key = (user["id"], page)
    if st.session_state.get(f"view-{page}") != key:
        with AuditLog(DB) as log:
            log.append(user["id"], user["role"], f"page view: {page}", None, {"ui": "dashboard"})
        st.session_state[f"view-{page}"] = key
    return user


def rtl(markdown: str) -> None:
    """Urdu is written right to left."""
    st.markdown(f"<div dir='rtl'>{markdown}</div>" if lang() == "ur" else markdown, unsafe_allow_html=True)


@st.cache_data(ttl=5)
def _load_results(mtimes: tuple) -> list[dict]:
    return [json.load(open(p)) for p, _ in mtimes]


def results() -> list[ApplicationResult]:
    paths = sorted(glob.glob(f"{OUT}/*.result.json"))
    return [ApplicationResult.model_validate(r) for r in _load_results(tuple((p, os.path.getmtime(p)) for p in paths))]


def manifests() -> dict:
    out = {}
    for p in sorted(glob.glob(f"{APPS}/*.json")):
        m = json.load(open(p))
        out[m["app_id"]] = m
    return out
