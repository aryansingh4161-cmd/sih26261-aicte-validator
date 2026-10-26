"""WK25-24 Rule administration without code (back-end + CLI; no UI here).
check_clause(text) -> {found, page, note}: word-for-word against the Approval Process Handbook PDF (settings `handbook_pdf`, a
local copy, not committed). Normalisation: curly quotes -> straight, every run of spaces / line breaks -> one space, lower case.
A leading reference ("ANNEXURE-2 2.1 iii. - ") is not part of the quote. No Handbook text on this machine -> found=False.
propose_edit(rule) -> {ok, errors, warnings, diff, text}: validates (supported type, severity, lane, categories, params, wording),
writes a TEMP copy of the rule pack, runs the rule engine on it (no R-CONFIG-ERROR) and the rule-pack contract test
(tests.test_contracts rules) against the copy. clause_verified is set here: true ONLY if check_clause found the quote.
apply_edit(rule, user) -> applies only an OK proposal: the rule's block is replaced in the YAML text (comments elsewhere kept),
`version` bumped, an audit row (who, rule id, version, diff). coverage() -> rows of the rules sheet covered by the rule pack.
  python -m pramaan.rule_admin check "<clause text>"
  python -m pramaan.rule_admin diff  rule.yaml          python -m pramaan.rule_admin apply rule.yaml --user officer.demo
OWNER: Aryan."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import date

import yaml

from .i18n import t

RULEPACK = "config/rulepack_eoa_existing.yaml"
TYPES = {"required_doc": {"doc_type"}, "conditional_required": {"doc_type"}, "field_present": {"doc_type", "field"},
         "not_expired": {"doc_type", "field"}, "age_validity": {"doc_type", "issue_field", "max_years"},
         "provisional_age": {"doc_type", "kind_field", "kinds", "issue_field", "max_academic_years"},
         "value_equals": {"doc_type", "field", "expected"}, "signature_required": {"doc_type"}, "year_match": {"doc_type", "field"},
         "record_flag": {"key", "expected"}, "area_min": {"doc_type", "norms_file"}}
REQUIRED = ("id", "type", "applies_to", "params", "severity", "lane", "title", "message")
SEVERITIES, LANES, CATEGORIES = ("info", "low", "medium", "high"), ("return_for_rectification", "human_review", "info"), \
    ("eoa_existing_regular", "intake_increase")
BANNED = re.compile(r"\b(reject\w*|forged|forgery|fraud\w*)\b", re.I)
_TEXT: dict = {}


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", s).strip().lower()


def _handbook(settings_path: str = "config/settings.yaml") -> list[tuple[int, str]] | None:
    pdf = (yaml.safe_load(open(settings_path)) or {}).get("handbook_pdf", "data/handbook/APH.pdf")
    if not os.path.exists(pdf):
        return None
    sha = hashlib.sha256(open(pdf, "rb").read()).hexdigest()
    if sha not in _TEXT:
        cache = os.path.join("output", f"handbook_{sha[:12]}.json")
        if os.path.exists(cache):
            _TEXT[sha] = [tuple(x) for x in json.load(open(cache))]
        else:
            import pdfplumber
            with pdfplumber.open(pdf) as doc:
                _TEXT[sha] = [(i + 1, _norm(p.extract_text() or "")) for i, p in enumerate(doc.pages)]
            os.makedirs("output", exist_ok=True)
            json.dump(_TEXT[sha], open(cache, "w"))
    return _TEXT[sha]


def quote_part(clause: str) -> str:
    """'ANNEXURE-2 2.1 iii. - As per ...' -> 'As per ...' (the reference before ' - ' is not Handbook wording)."""
    m = re.match(r"^\s*(?:ANNEXURE-\d+\s+[\d.]+\s*[a-z]+\.|[\d.]+\s*[a-z]?\.|APH\s+[\d.]+\s*[a-z]?\.)\s*-\s*(.+)$", clause.strip(), re.I | re.S)
    return (m.group(1) if m else clause).strip().strip('"')


def check_clause(text: str, settings_path: str = "config/settings.yaml") -> dict:
    pages = _handbook(settings_path)
    if pages is None:
        return {"found": False, "page": None, "note": t("Handbook text not available on this machine (settings handbook_pdf).")}
    q = _norm(quote_part(text))
    if len(q) < 20:
        return {"found": False, "page": None, "note": t("Quote too short to check word for word (at least 20 characters).")}
    joined = " ".join(p for _, p in pages)                          # a quote may run over a page break
    if q not in joined:
        return {"found": False, "page": None, "note": t("Not found word for word in the Handbook.")}
    page = next((n for n, p in pages if q in p), None)
    if page is None:
        pos, acc = joined.index(q), 0
        for n, p in pages:
            acc += len(p) + 1
            if acc > pos:
                page = n; break
    return {"found": True, "page": page, "note": t("Found word for word in the Handbook") + f" (p. {page})."}


def _validate(rule: dict) -> list[str]:
    e = [f"missing field '{k}'" for k in REQUIRED if k not in rule]
    if e:
        return e
    if rule["type"] not in TYPES:
        e.append(f"unsupported rule type '{rule['type']}' (supported: {', '.join(sorted(TYPES))})")
    else:
        miss = TYPES[rule["type"]] - set((rule.get("params") or {}))
        e += [f"params need '{k}' for type {rule['type']}" for k in sorted(miss)]
    if rule["severity"] not in SEVERITIES:
        e.append(f"severity must be one of {SEVERITIES}")
    if rule["lane"] not in LANES:
        e.append(f"lane must be one of {LANES}")
    if not rule["applies_to"] or set(rule["applies_to"]) - set(CATEGORIES):
        e.append(f"applies_to must be a non-empty subset of {CATEGORIES}")
    if not re.fullmatch(r"[A-Z]-[A-Za-z0-9_-]+", str(rule["id"])):
        e.append("id must look like R-MISS-fire_cert")
    for k in ("title", "message"):
        if BANNED.search(str(rule.get(k, ""))):
            e.append(f"{k} uses a word the system never says (reject / forged / fraud)")
    return e


def _block(rule: dict) -> str:
    body = yaml.safe_dump([rule], sort_keys=False, allow_unicode=True, width=200)
    return "".join("  " + ln if ln.strip() else ln for ln in body.splitlines(keepends=True))


def _new_text(src: str, rule: dict) -> str:
    lines = src.splitlines(keepends=True)
    start = next((i for i, ln in enumerate(lines) if re.match(rf"\s*- id:\s*{re.escape(rule['id'])}\s*$", ln)), None)
    if start is None:                                                # a new rule goes at the end
        return src.rstrip("\n") + "\n" + _block(rule)
    end = next((i for i in range(start + 1, len(lines)) if re.match(r"\s*- id:\s*\S", lines[i])), len(lines))
    return "".join(lines[:start]) + _block(rule) + "".join(lines[end:])


def _bump(text: str) -> str:
    m = re.search(r"^version:\s*(\d+)", text, re.M)
    return re.sub(r"^version:\s*\d+", f"version: {int(m.group(1)) + 1}", text, count=1, flags=re.M) if m else "version: 1\n" + text


def propose_edit(rule: dict, rulepack: str = RULEPACK, run_contract_test: bool = True) -> dict:
    rule = dict(rule)
    errors, warnings = _validate(rule), []
    if rule.get("aph_clause"):
        chk = check_clause(rule["aph_clause"])
        rule["clause_verified"] = chk["found"]                       # never taken from the input
        if not chk["found"]:
            warnings.append(t("Clause not verified: ") + chk["note"] + " " + t("clause_verified stays false."))
    else:
        rule["aph_clause"], rule["clause_verified"] = None, False
    src = open(rulepack).read()
    new = _new_text(src, rule) if not errors else src
    diff = "".join(difflib.unified_diff(src.splitlines(keepends=True), new.splitlines(keepends=True), rulepack, rulepack + " (proposed)"))
    if not errors:
        tmp = tempfile.mkdtemp()
        tp = os.path.join(tmp, "rulepack.yaml")
        open(tp, "w").write(new)
        try:
            ids = [r["id"] for r in (yaml.safe_load(new) or {}).get("rules", [])]
            if len(ids) != len(set(ids)):
                errors.append("duplicate rule id in the rule pack")
            from .rules import run_rules
            from .schemas import Application
            app = Application(app_id="RULE-ADMIN", category=rule["applies_to"][0], academic_year="2026-27", permanent_id="1-0",
                              submitted_on="2026-10-01")
            bad = [f for f in run_rules(app, [], [], {}, tp, date(2026, 10, 26)) if f.rule_id == "R-CONFIG-ERROR"]
            errors += [f"rule engine: {f.reason}" for f in bad]
        except Exception as ex:
            errors.append(f"rule pack does not load: {type(ex).__name__}: {str(ex)[:150]}")
        if not errors and run_contract_test:
            r = subprocess.run([sys.executable, "-m", "tests.test_contracts", "rules", "area"], capture_output=True, text=True,
                               env={**os.environ, "PRAMAAN_RULEPACK": tp})
            if "ALL TESTS PASSED" not in r.stdout:
                errors.append("rule-pack contract test failed on the proposed copy: " + (r.stdout + r.stderr)[-300:])
        shutil.rmtree(tmp, ignore_errors=True)
    return {"ok": not errors, "errors": errors, "warnings": warnings, "diff": diff, "rule": rule, "text": new if not errors else None}


def apply_edit(rule: dict, user: dict, rulepack: str = RULEPACK, audit_db: str = "output/audit.db", run_contract_test: bool = True) -> dict:
    p = propose_edit(rule, rulepack, run_contract_test)
    if not p["ok"]:
        return {**p, "applied": False}
    text = _bump(p["text"])
    ver = int(re.search(r"^version:\s*(\d+)", text, re.M).group(1))
    open(rulepack, "w").write(text)
    from .audit import AuditLog
    with AuditLog(audit_db) as log:
        h = log.append(user["id"], user["role"], "rule pack edited", None,
                       {"rule_id": p["rule"]["id"], "version": ver, "clause_verified": p["rule"]["clause_verified"], "diff": p["diff"]})
    return {**p, "applied": True, "version": ver, "audit_hash": h}


def coverage(path: str = "config/rule_coverage.yaml", rulepack: str = RULEPACK) -> dict:
    cov = yaml.safe_load(open(path)) or {}
    ids = {r["id"] for r in (yaml.safe_load(open(rulepack)) or {}).get("rules", [])} | set(cov.get("engine_checks", []))
    rows = [r for r in cov.get("rows", []) if set(r.get("rule_ids", [])) & ids]
    return {"covered": len(rows), "total": cov.get("total_rows"), "rows": [r["row"] for r in rows], "source": cov.get("source")}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "diff", "apply", "coverage"]); ap.add_argument("arg", nargs="?")
    ap.add_argument("--user", default="admin.demo"); ap.add_argument("--rulepack", default=RULEPACK)
    a = ap.parse_args()
    if a.cmd == "check":
        print(json.dumps(check_clause(a.arg or ""), ensure_ascii=False))
    elif a.cmd == "coverage":
        print(json.dumps(coverage(rulepack=a.rulepack)))
    else:
        rule = yaml.safe_load(open(a.arg))
        users = {u["id"]: u for u in (yaml.safe_load(open("config/users.yaml")) or {}).get("users", [])}
        out = propose_edit(rule, a.rulepack) if a.cmd == "diff" else apply_edit(rule, users[a.user], a.rulepack)
        print(out["diff"] or t("(no change)"))
        for w in out["warnings"]:
            print("WARNING:", w)
        for e in out["errors"]:
            print("ERROR:", e)
        print(("APPLIED, version " + str(out.get("version"))) if out.get("applied") else ("OK" if out["ok"] else "REFUSED"))
        sys.exit(0 if out["ok"] else 1)
