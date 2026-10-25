"""Clean demo state for the demo laptop: delete output/*.db (audit log, reuse index, webhook deliveries), output/*.json,
output/*.html and output/heatmaps/, then rebuild the SYNTHETIC demo bundles.
  python -m tools.reset_demo            # list what would be deleted (nothing is touched)
  python -m tools.reset_demo --yes      # delete + rebuild bundles
This DOES delete the audit chain (unlike tools/retention.py, which never does): use it only to start a fresh demo.
OWNER: Aryan."""
from __future__ import annotations

import argparse
import glob
import os
import shutil
from datetime import date


def targets(out_dir: str) -> list[str]:
    pats = ["*.db", "*.db-journal", "*.json", "*.html"]
    files = sorted({p for pat in pats for p in glob.glob(os.path.join(out_dir, pat))})
    heat = os.path.join(out_dir, "heatmaps")
    return files + ([heat] if os.path.isdir(heat) else [])


def reset(out_dir: str = "output", today: date = date(2026, 10, 26), apply: bool = False, rebuild: bool = True) -> list[str]:
    found = targets(out_dir)
    if apply:
        for p in found:
            shutil.rmtree(p) if os.path.isdir(p) else os.remove(p)
        if rebuild:
            from pramaan.synth import bundles
            bundles.build("data/demo", today)
    return found


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="output"); ap.add_argument("--today", default="2026-10-26")
    ap.add_argument("--yes", action="store_true", help="really delete (default: list only)")
    a = ap.parse_args()
    found = reset(a.out, date.fromisoformat(a.today), a.yes)
    for p in found:
        print(("deleted  " if a.yes else "would delete  ") + p)
    print(f"{len(found)} items {'deleted; demo bundles rebuilt in data/demo' if a.yes else 'listed; nothing deleted (add --yes)'}.")
    if a.yes:
        print("Next: python -m pramaan.demo   (or the pipeline + streamlit run dashboard/app.py)")
