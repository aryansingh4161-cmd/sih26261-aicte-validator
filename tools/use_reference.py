"""Copy reference versions into pramaan/ (the safety net).  python -m tools.use_reference rules crosscheck [--force]
Your own file, if any, is kept as pramaan/<name>.mine.py. Then run:  python -m tests.test_contracts <name>   OWNER: Aryan."""
import os
import shutil
import sys

MODS = ["ingest", "classify_extract", "rules", "crosscheck", "forensics", "issuer", "audit", "triage", "report", "pipeline", "photo_check"]

if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    if not args:
        print("modules:", " ".join(MODS + ["dashboard", "all-missing"])); sys.exit(0)
    if args == ["all-missing"]:
        args = [m for m in MODS if not os.path.exists(f"pramaan/{m}.py")]
    for m in args:
        src, dst = (("reference/dashboard/app.py", "dashboard/app.py") if m == "dashboard" else (f"reference/pramaan/{m}.py", f"pramaan/{m}.py"))
        if not os.path.exists(src):
            print("no reference for", m); continue
        if os.path.exists(dst) and not force:
            print(f"{dst} exists: kept. Use --force to replace it (yours is saved as .mine.py)"); continue
        if os.path.exists(dst):
            shutil.copy(dst, dst.replace(".py", ".mine.py"))
        os.makedirs(os.path.dirname(dst), exist_ok=True); shutil.copy(src, dst); print("copied", src, "->", dst)
