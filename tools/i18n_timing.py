"""Measure (WK23-17): seconds to render a dashboard page in a language with a COLD translation cache (no static table, empty
SQLite cache: model load + every string translated) vs WARM (static table + cache filled by the cold run).
  python -m tools.i18n_timing --page dashboard/pages/1_Desk.py --lang hi
Runs the page headless (streamlit AppTest) on output/. Each run is a separate process, so the model load is included when cold."""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import tempfile
import time

ONE = """
import os, time, sys
from streamlit.testing.v1 import AppTest
at = AppTest.from_file(os.path.abspath(sys.argv[1]), default_timeout=1800)
at.session_state["lang"] = sys.argv[2]
t0 = time.time(); at.run(); dt = time.time() - t0
print("SECONDS", round(dt, 2), "EXCEPTIONS", len(at.exception))
"""


def run(page: str, lang: str, env: dict) -> str:
    out = subprocess.run([sys.executable, "-c", ONE, page, lang], capture_output=True, text=True, env={**os.environ, **env})
    return next((l for l in out.stdout.splitlines() if l.startswith("SECONDS")), out.stderr[-300:])


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--page", default="dashboard/pages/1_Desk.py"); ap.add_argument("--lang", default="hi")
    a = ap.parse_args()
    tmp = tempfile.mkdtemp()
    cold_env = {"PRAMAAN_I18N_CACHE": os.path.join(tmp, "cache.db"), "PRAMAAN_I18N_STATIC": os.path.join(tmp, "no_static")}
    print("cold:", run(a.page, a.lang, cold_env))
    print("warm (same cache, static tables on):", run(a.page, a.lang, {"PRAMAAN_I18N_CACHE": cold_env["PRAMAAN_I18N_CACHE"]}))
    print("english:", run(a.page, "en", {}))
