"""The whole demo in one command (Mac, Linux, Windows):
  python -m pramaan.demo [--today 2026-10-26] [--no-dashboard] [--quick]
Checks the environment, builds the SYNTHETIC demo bundles, runs the pipeline on every demo application, runs the eval
harness (into output/demo_eval.csv, so eval/results.csv is not touched), prints lanes + key metrics, starts the dashboard.
Optional parts (pyHanko signing, tamper model, EasyOCR) are skipped with a clear message. OWNER: Aryan."""
from __future__ import annotations

import argparse
import glob
import importlib.util
import os
import subprocess
import sys
import time
from datetime import date

WEIGHTS = "data/models/tamper_unet.pt"
KEY_METRICS = ("extract.field_acc.all", "extract.type_acc.all", "demo.recall", "demo.unexpected_findings",
               "demo.lane_agreement", "demo.seconds_per_app")


def _has(*mods: str) -> bool:
    return all(importlib.util.find_spec(m) is not None for m in mods)


def environment() -> dict:
    env = {"pyhanko": _has("pyhanko"), "torch": _has("torch", "segmentation_models_pytorch"), "weights": os.path.exists(WEIGHTS),
           "easyocr": _has("easyocr"), "streamlit": _has("streamlit")}
    print(f"Pramaan AI demo - Python {sys.version.split()[0]} on {sys.platform} (all data SYNTHETIC; issuer checks MOCK)")
    if sys.version_info < (3, 11):
        print("  WARNING: Python 3.11 or newer expected.")
    lines = [("pyHanko (sign + validate affidavits)", env["pyhanko"], "pip install pyhanko  -> affidavits stay unsigned, R-SIG findings appear"),
             ("torch + segmentation-models-pytorch", env["torch"], "optional; tamper model skipped (Colab: see pramaan/model/)"),
             (f"tamper weights {WEIGHTS}", env["weights"], "copy from the team Drive; APP-12 F-TAMPER is then found"),
             ("EasyOCR (real OCR sidecars)", env["easyocr"], "optional; demo uses MOCKED OCR sidecars (pip install easyocr)"),
             ("Streamlit (dashboard)", env["streamlit"], "pip install streamlit")]
    for name, ok, why in lines:
        print(f"  [{'x' if ok else ' '}] {name}" + ("" if ok else f"  - skipped: {why}"))
    return env


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--today", default="2026-10-26"); ap.add_argument("--no-dashboard", action="store_true")
    ap.add_argument("--quick", action="store_true", help="smaller extraction eval (5 institutes instead of 20)")
    ap.add_argument("--port", type=int, default=8501)
    a = ap.parse_args()
    today = date.fromisoformat(a.today)
    env = environment()

    print("\n1/4 Building demo applications (synthetic) ...")
    from .synth import bundles
    t = time.time(); truth = bundles.build("data/demo", today)
    print(f"    {len(truth)} applications in data/demo/apps; signed affidavits: {env['pyhanko']} ({time.time() - t:.0f} s)")

    print("2/4 Running the pipeline on every application ...")
    from .pipeline import run_application
    res = [run_application(m, "output", today) for m in sorted(glob.glob(os.path.join("data", "demo", "apps", "*.json")))]
    print(f"    {'application':12s} {'lane':26s} {'priority':>8s}  findings")
    for r in res:
        rules = ", ".join(sorted({f.rule_id for f in r.findings}))[:60] or "-"
        print(f"    {r.app_id:12s} {r.lane:26s} {r.priority:8.2f}  {len(r.findings)}  {rules}")
    print("    reports: output/<app>.report.html")

    print("3/4 Eval harness (synthetic; label measured) ...")
    out = os.path.join("output", "demo_eval.csv")
    if os.path.exists(out):
        os.remove(out)
    cmd = [sys.executable, "-m", "eval.run_eval", "--today", a.today, "--out", out] + (["--n_inst", "5"] if a.quick else [])
    p = subprocess.run(cmd, capture_output=True, text=True)
    if p.returncode != 0:
        print("    eval failed:\n" + p.stderr[-1500:]); return 1
    for ln in p.stdout.splitlines():
        if ln.split(" ")[0] in KEY_METRICS:
            print("    " + ln)
    print(f"    all rows: {out}")
    if not env["weights"]:
        print("    note: APP-12 needs the tamper weights; without them its lane is 'clear' (the one lane miss).")

    print("4/4 Dashboard")
    if a.no_dashboard or not env["streamlit"]:
        print("    skipped." + ("" if env["streamlit"] else " (Streamlit missing)") + "  Start later: streamlit run dashboard/app.py")
        return 0
    print(f"    http://localhost:{a.port}  (sign in as a demo user; Ctrl+C to stop)")
    try:
        return subprocess.call([sys.executable, "-m", "streamlit", "run", os.path.join("dashboard", "app.py"),
                                "--server.port", str(a.port), "--server.headless", "true"])
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
