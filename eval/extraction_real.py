"""Field accuracy on REAL EoA letters against Saanvi's human answer key (the number that matters most on the deck).
Inputs (never committed: real_samples/ is in .gitignore):
  real_samples/codes.csv        letter_code,file           e.g. EOA1,real_samples/letter_a.pdf
  real_samples/eoa_truth.csv    letter_code,field,value_as_printed,page   (Drive sheet eoa_real_truth -> File > Download > CSV)
Run:  python -m eval.extraction_real      -> prints a table, appends to eval/results.csv, writes eval/extraction_real_detail.csv
WK22: python -m eval.extraction_real --set real_eoa_dev --codes 1-6     (DEV: the 6 letters the extraction was developed on)
      python -m eval.extraction_real --set real_eoa_test --codes 7-99   (held-out TEST: run ONCE, frozen spec, no changes after)
Comparison: dates are compared after normalising to ISO; text after upper-casing, removing extra spaces and
reading "&" as "AND" (WK22, applied to truth and extraction alike). OWNER: Jasraj."""
from __future__ import annotations

import csv
import os
import re
import sys

from pramaan.classify_extract import classify_and_extract
from pramaan.ingest import ingest
from pramaan.model.eval_common import RESULT_COLS
from pramaan.util import iso, parse_date

SKIP = {"NOT PRESENT", "UNREADABLE", ""}


def norm(field: str, v: str | None) -> str:
    v = re.sub(r"\s+", " ", v or "").strip()          # WK25: both sides - strip, every run of spaces / line breaks -> one space
    if field in ("approval_date", "printed_on"):
        v = re.sub(r"\s*([-/.])\s*", r"\1", v)                # a date broken over a line: "25-04- 2025" -> "25-04-2025"
        d = parse_date(v)
        return iso(d) if d else v.upper()
    return re.sub(r"\s+", " ", re.sub(r"\s*&\s*", " AND ", v)).strip().upper()     # WK22: "&" == "AND", both sides


def _code_no(code: str) -> int:
    m = re.search(r"\d+", code)
    return int(m.group(0)) if m else -1


def main(codes="real_samples/codes.csv", truth="real_samples/eoa_truth.csv", out="eval/results.csv", set_name="real_eoa_letters",
         code_range=(0, 10**6)):
    files = {r["letter_code"].strip(): r["file"].strip() for r in csv.DictReader(open(codes))
             if code_range[0] <= _code_no(r["letter_code"].strip()) <= code_range[1]}
    rows = [r for r in csv.DictReader(open(truth)) if r["field"].strip() != "program_row"]
    got_cache, detail, ok, n = {}, [], 0, 0
    for r in rows:
        code, field, want = r["letter_code"].strip(), r["field"].strip(), r["value_as_printed"].strip()
        if want.upper() in SKIP or code not in files:
            continue
        if code not in got_cache:
            got_cache[code] = classify_and_extract(ingest(files[code], code))
        d = got_cache[code]
        got = d.fields[field].value if field in d.fields else None
        hit = norm(field, got) == norm(field, want)
        ok += hit; n += 1
        detail.append({"letter_code": code, "field": field, "truth": want, "extracted": got or "", "match": int(hit), "doc_type": d.doc_type})
    os.makedirs("eval", exist_ok=True)
    with open(f"eval/extraction_real_detail_{set_name}.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["letter_code", "field", "truth", "extracted", "match", "doc_type"]); w.writeheader(); w.writerows(detail)
    acc = ok / n if n else float("nan")
    new = not os.path.exists(out)
    with open(out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_COLS)
        if new:
            w.writeheader()
        w.writerow(dict(metric_id="extract.field_acc.real_eoa", metric="Field extraction accuracy on REAL EoA letters (human answer key)",
                        value=round(acc, 4), unit="fraction", n=n, set=set_name, label="measured",
                        source_file=f"eval/extraction_real_detail_{set_name}.csv", notes=f"{len(got_cache)} letters ({','.join(sorted(got_cache, key=_code_no))}); fields: file_no, approval_date, permanent_id, "
                              "application_id, academic_year, printed_on, institute_name; "
                              + ("DEV set: extraction developed on these letters (optimistic)" if set_name.endswith("dev") else
                                 "held-out TEST set: not tuned on, run once with the frozen spec" if set_name.endswith("test") else "")))
    for x in detail:
        if not x["match"]:
            print(f"MISS {x['letter_code']} {x['field']}: truth '{x['truth']}' got '{x['extracted']}'")
    print(f"REAL EoA field accuracy: {ok}/{n} = {acc:.3f} over {len(got_cache)} letters")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes_csv", default="real_samples/codes.csv"); ap.add_argument("--truth", default="real_samples/eoa_truth.csv")
    ap.add_argument("--set", default="real_eoa_letters"); ap.add_argument("--codes", default="0-1000000", help="e.g. 1-6 or 7-99")
    a = ap.parse_args()
    lo, hi = (int(x) for x in a.codes.split("-"))
    main(a.codes_csv, a.truth, "eval/results.csv", a.set, (lo, hi))
