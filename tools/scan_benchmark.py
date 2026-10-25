"""Extraction on SCANNED synthetic documents: render -> 150 dpi raster -> scan_effect (light 0.6 / medium 1.0 / heavy 1.4)
-> JPEG q85 -> EasyOCR sidecar (CPU) -> ingest -> classify_extract -> compare with generator truth (normalised like run_eval).
  python -m tools.scan_benchmark [--k 4] [--types eoa_letter,...] [--no-csv]
Work files in output/scan_benchmark/ (sidecars are cached: a re-run resumes). Per-field detail -> output/scan_benchmark/detail.csv.
Appends extract_scan.* rows to eval/results.csv (label measured, set synthetic_scans). Specs are NOT tuned here. OWNER: Aryan."""
from __future__ import annotations

import argparse
import csv
import os
import random
import sys
import time
from collections import defaultdict

STRENGTHS = {"light": 0.6, "medium": 1.0, "heavy": 1.4}
TYPES = ("eoa_letter", "affidavit_2", "noc_format2", "fire_cert", "structural_cert")
WORK = os.path.join("output", "scan_benchmark")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--k", type=int, default=4); ap.add_argument("--seed", type=int, default=301)
    ap.add_argument("--types", default=",".join(TYPES)); ap.add_argument("--dpi", type=int, default=150)
    ap.add_argument("--no-csv", action="store_true")
    a = ap.parse_args()
    try:
        import easyocr
    except ImportError:
        print("EasyOCR is not installed. Run:\n    pip install easyocr\nthen run this command again."); return 2
    from pramaan.classify_extract import classify_and_extract
    from pramaan.ingest import ingest
    from pramaan.synth import content as C, docs as D
    from pramaan.synth.raster import jpeg_roundtrip, render_page, scan_effect
    from pramaan.util import norm_name
    from tools.ocr_sidecar import ocr_file
    types = a.types.split(",")
    os.makedirs(WORK, exist_ok=True)
    reader, detail, ocr_secs = None, [], []
    total, done = a.k * len(types) * len(D.LAYOUTS) * len(STRENGTHS), 0
    for k in range(a.k):
        rng = random.Random(a.seed + k); inst = C.make_institute(rng); det = D.default_details(rng, inst)
        for dt in types:
            for lay in D.LAYOUTS:
                stem = os.path.join(WORK, f"{k}_{dt}_{lay}")
                r = D.render_pdf(dt, lay, inst, det, stem + ".pdf")
                page = render_page(r["path"], dpi=a.dpi)
                for sname, s in STRENGTHS.items():
                    jp = f"{stem}_{sname}.jpg"
                    if not os.path.exists(jp + ".ocr.json"):
                        jpeg_roundtrip(scan_effect(page, random.Random(f"{k}{dt}{lay}{sname}"), s), 85).save(jp, quality=95)
                        if reader is None:
                            reader = easyocr.Reader(["en"], gpu=False, verbose=False)
                        t = time.perf_counter(); items = ocr_file(jp, a.dpi, reader); ocr_secs.append(time.perf_counter() - t)
                        import json
                        with open(jp + ".ocr.json", "w") as f:
                            json.dump(items, f)
                    d = classify_and_extract(ingest(jp, f"S{k}-{dt}-{lay}-{sname}"))
                    for fld, truth in r["truth"].items():
                        got = d.fields[fld].value if fld in d.fields else None
                        detail.append({"strength": sname, "doc_type": dt, "layout": lay, "k": k, "got_type": d.doc_type, "field": fld,
                                       "truth": truth, "got": got, "ok": int(norm_name(str(got)) == norm_name(str(truth))), "image": jp})
                    done += 1
                    print(f"[{done}/{total}] {dt} {lay} k{k} {sname}: type {d.doc_type}", flush=True)
    with open(os.path.join(WORK, "detail.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(detail[0])); w.writeheader(); w.writerows(detail)
    rows = summarise(detail, types, ocr_secs)
    if not a.no_csv:
        from pramaan.model.eval_common import RESULT_COLS
        with open("eval/results.csv", "a", newline="") as f:
            csv.DictWriter(f, fieldnames=RESULT_COLS).writerows(rows)
    for r in rows:
        print(f'{r["metric_id"]:48s} {r["value"]}  (n={r["n"]})')
    return 0


def summarise(detail: list[dict], types, ocr_secs) -> list[dict]:
    note = (f"EasyOCR CPU, 150 dpi, scan_effect + JPEG q85, Python {sys.version.split()[0]}, Aryan's M1 MacBook Air; "
            "synthetic docs; specs untuned for OCR")
    def row(mid, metric, num, den, unit="fraction"):
        return dict(metric_id=f"extract_scan.{mid}", metric=metric, value=round(num / den, 4) if den else 0.0, unit=unit, n=den,
                    set="synthetic_scans", label="measured", source_file="tools/scan_benchmark.py", notes=note)
    docs = {(d["strength"], d["doc_type"], d["layout"], d["k"]): d["got_type"] == d["doc_type"] for d in detail}
    out = []
    for s in STRENGTHS:
        dd = [v for key, v in docs.items() if key[0] == s]; ff = [d for d in detail if d["strength"] == s]
        out.append(row(f"type_acc.{s}", f"Document type accuracy, {s} scans", sum(dd), len(dd)))
        out.append(row(f"field_acc.{s}", f"Field accuracy, {s} scans", sum(d["ok"] for d in ff), len(ff)))
        for dt in types:
            fd = [d for d in ff if d["doc_type"] == dt]
            out.append(row(f"field_acc.{dt}.{s}", f"Field accuracy {dt}, {s} scans", sum(d["ok"] for d in fd), len(fd)))
    per = defaultdict(list)
    for d in detail:
        per[(d["doc_type"], d["field"])].append(d["ok"])
    for (dt, fld), v in sorted(per.items()):
        out.append(row(f"field_acc.{dt}.{fld}.all", f"Field accuracy {dt}.{fld}, all strengths", sum(v), len(v)))
    if ocr_secs:
        out.append(dict(row("ocr_seconds_per_page", "EasyOCR seconds per page (CPU)", 0, 0, "seconds"),
                        value=round(sum(ocr_secs) / len(ocr_secs), 2), n=len(ocr_secs)))
    return out


if __name__ == "__main__":
    sys.exit(main())
