"""Pre-translate the static UI strings once (WK23-17), so switching language is instant:
  python -m tools.build_translations                      (hi, bn, ta, mr; or --langs all / --langs hi,ta)   -> config/i18n/<lang>.json (committed)
Strings = every t("literal") in dashboard/ and pramaan/ (not f-strings: those are dynamic and cached on first view) + lane,
status and checklist words. Uses pramaan.i18n (IndicTrans2 offline, placeholders protected). OWNER: Aryan."""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import time

import yaml

EXTRA = ["Send to human review", "Return for rectification", "No issues found", "Approve for next step", "Send to expert review",
         "human review", "return for rectification", "clear", "info", "verified", "pending", "mismatch", "unavailable",
         "consent not given", "resolved", "still open", "new", "unchanged", "replaced", "added", "removed", "green", "amber", "red",
         "grey", "Correct", "False alarm", "open", "window closed", "closed (read-only)", "verification pending", "mismatch detected",
         "source unavailable", "manual review required", "expired"]


def strings() -> list[str]:
    found = set(EXTRA)
    for p in glob.glob("dashboard/*.py") + glob.glob("dashboard/pages/*.py") + glob.glob("pramaan/*.py"):
        src = open(p, encoding="utf-8").read()
        found |= set(re.findall(r'(?<![fA-Za-z_])t\("((?:[^"\\\n]|\\.)+)"', src))
        found |= set(re.findall(r"(?<![fA-Za-z_])t\('((?:[^'\\\n]|\\.)+)'", src))
    for row in (yaml.safe_load(open("config/checklists/eoa_existing.yaml")) or {}).get("rows", []):
        found.add(row["item"])
    from pramaan.i18n import BANNER
    found.add(BANNER)
    return sorted(s for s in found if re.search(r"[A-Za-z]", s) and "{" not in s)


if __name__ == "__main__":
    from pramaan.i18n import CODES, STATIC_LANGS, available, translate_many
    ap = argparse.ArgumentParser(); ap.add_argument("--langs", default="static", help="static (= hi,bn,ta,mr), all, or a list like hi,ta")
    a = ap.parse_args()
    langs = list(CODES) if a.langs == "all" else list(STATIC_LANGS) if a.langs == "static" else a.langs.split(",")
    if not available():
        raise SystemExit("IndicTrans2 is not available here (gated model: huggingface-cli login + accept the licence, then retry).")
    src = strings()
    os.makedirs("config/i18n", exist_ok=True)
    for lang in langs:
        t0 = time.time()
        table = translate_many(src, lang)
        json.dump(dict(sorted(table.items())), open(f"config/i18n/{lang}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        kept = sum(table[s] == s for s in src)
        print(f"{lang}: {len(src)} strings in {time.time() - t0:.0f} s ({kept} kept in English: placeholders lost or nothing to translate)",
              flush=True)
