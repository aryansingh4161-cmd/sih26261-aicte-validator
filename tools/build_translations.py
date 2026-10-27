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
    for p in (glob.glob("dashboard/*.py") + glob.glob("dashboard/pages/*.py") + glob.glob("pramaan/*.py") + glob.glob("api/*.py")
              + glob.glob("web/src/**/*.tsx", recursive=True) + glob.glob("web/src/**/*.ts", recursive=True)):    # WK26: web UI strings too
        src = open(p, encoding="utf-8").read()
        found |= set(re.findall(r'(?<![fA-Za-z_])t\("((?:[^"\\\n]|\\.)+)"', src))
        found |= set(re.findall(r"(?<![fA-Za-z_])t\('((?:[^'\\\n]|\\.)+)'", src))
        if p.endswith((".tsx", ".ts")):                      # WK27 A6: labels kept in arrays / maps and passed to t(label) later
            found |= set(re.findall(r'\b(?:label|short|name):\s*"([A-Z][^"\n]*)"', src))
            found |= set(re.findall(r'\[\s*"[^"\n]*",\s*"([A-Z][^"\n]*)"\s*\]', src))
            found |= set(re.findall(r'"[^"\n]+":\s*"([A-Z][^"\n]*)"', src))
            found |= set(re.findall(r'[{,]\s*[a-z_]+:\s*"([A-Z][a-z][^"\n]*)"', src))
            for m in re.findall(r'\bt\(([^()\n]*\?[^()\n]*)\)', src):  # t(x ? "a" : "b")
                found |= set(re.findall(r'"([^"\n]+)"', m))
            for arr in re.findall(r'const (?:steps|STEPS)\s*=\s*\[([^\]]+)\]', src):
                found |= set(re.findall(r'"([^"\n]+)"', arr))
    for row in (yaml.safe_load(open("config/checklists/eoa_existing.yaml")) or {}).get("rows", []):
        found.add(row["item"])
    from pramaan.i18n import BANNER
    found.add(BANNER)
    found |= {"confirm {n} findings"}
    found = {x.replace('\\"', '"') for x in found}                 # t("a \"b\"") in source = 'a "b"' at run time
    return sorted(s for s in found if re.search(r"[A-Za-z]", s) and ("{" not in s or s in ("confirm {n} findings",)) and not s.startswith(("var(", "#")))


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
        reviewed = f"config/i18n/{lang}_reviewed.json"           # WK27 A6: hand-checked words win over the machine translation
        if os.path.exists(reviewed):
            table.update({k: v for k, v in json.load(open(reviewed, encoding="utf-8")).items() if not k.startswith("_")})
        json.dump(dict(sorted(table.items())), open(f"config/i18n/{lang}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        kept = sum(table[s] == s for s in src)
        print(f"{lang}: {len(src)} strings in {time.time() - t0:.0f} s ({kept} kept in English: placeholders lost or nothing to translate)",
              flush=True)
