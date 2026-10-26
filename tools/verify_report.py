"""Check a sealed Pramaan report or letter against the audit chain (WK23-6).
  python -m tools.verify_report output/APP-02.report.html [--audit output/audit.db]
Prints "VALID: matches audit entry #n" or "ALTERED: <why>"; exit code 0 / 1. OWNER: Aryan."""
from __future__ import annotations

import argparse
import sys

from pramaan.seal import verify_sealed

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("report"); ap.add_argument("--audit", default="output/audit.db")
    a = ap.parse_args()
    with open(a.report, encoding="utf-8", errors="replace") as f:
        msg = verify_sealed(f.read(), a.audit)
    print(msg)
    sys.exit(0 if msg.startswith("VALID") else 1)
