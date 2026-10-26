"""WK22 synthetic SCAN set (50 pages: 10 each of fire, structural, occupancy, NOC, affidavit) and before/after OCR scoring.
Each page: random layout, rendered at 150-200 dpi, grey paper, rotated +/-2 deg, blurred, JPEG q60. Truth = generator truth.
  python -m tools.scan_set build                     -> data/scans_synth/img/*.jpg + truth.json (git-ignored)
  python -m tools.scan_set run --ocr base|clean      -> EasyOCR sidecars in data/scans_synth/<ocr>/ (cached; a re-run resumes)
  python -m tools.scan_set score --ocr base|clean --tag before|after   -> per-type field accuracy, detail CSV
base = the current OCR path (image as is); clean = tools/ocr_sidecar.py --clean (300 dpi, greyscale, auto-contrast, deskew,
denoise). Nothing here is tuned on this set: it is the measurement set. OWNER: Aryan."""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import sys
import tempfile
import time

from PIL import Image, ImageFilter

TYPES = ("fire_cert", "structural_cert", "occupancy_cert", "noc_format2", "affidavit_2")
ROOT = os.path.join("data", "scans_synth")


def degrade(page: Image.Image, rng: random.Random) -> Image.Image:
    import numpy as np
    grey = rng.randint(200, 222)                                # grey paper: white -> grey, ink stays dark
    a = np.asarray(page.convert("RGB"), np.float32) * (grey / 255.0)
    img = Image.fromarray(a.clip(0, 255).astype("uint8"))
    img = img.rotate(rng.uniform(-2.0, 2.0), resample=Image.BICUBIC, expand=True, fillcolor=(grey, grey, grey))
    return img.filter(ImageFilter.GaussianBlur(rng.uniform(0.5, 1.0)))


def build(n_per: int = 10, seed: int = 2201) -> dict:
    from pramaan.synth import content as C, docs as D
    from pramaan.synth.raster import render_page
    os.makedirs(os.path.join(ROOT, "img"), exist_ok=True)
    truth = {}
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for dt in TYPES:
            for i in range(n_per):
                rng = random.Random(f"{seed}-{dt}-{i}")
                inst = C.make_institute(rng); det = D.default_details(rng, inst); lay = rng.choice(D.LAYOUTS)
                r = D.render_pdf(dt, lay, inst, det, os.path.join(tmp, f"{dt}_{i}.pdf"))
                dpi = rng.randint(150, 200)
                stem = f"{dt}_{i:02d}"
                degrade(render_page(r["path"], dpi=dpi), rng).save(os.path.join(ROOT, "img", stem + ".jpg"), quality=60)
                truth[stem] = {"doc_type": dt, "layout": lay, "dpi": dpi, "truth": r["truth"]}
    json.dump(truth, open(os.path.join(ROOT, "truth.json"), "w"), indent=1)
    return truth


def _variant_path(stem: str, ocr: str) -> str:
    """ingest reads <image>.ocr.json, so each OCR variant gets its own folder with a link to the shared image."""
    d = os.path.join(ROOT, ocr); os.makedirs(d, exist_ok=True)
    p = os.path.join(d, stem + ".jpg")
    if not os.path.exists(p):
        os.symlink(os.path.abspath(os.path.join(ROOT, "img", stem + ".jpg")), p)
    return p


def run(ocr: str) -> None:
    import easyocr
    from tools.ocr_sidecar import ocr_file
    truth = json.load(open(os.path.join(ROOT, "truth.json")))
    reader, secs = easyocr.Reader(["en"], gpu=False, verbose=False), []
    for k, stem in enumerate(sorted(truth)):
        p = _variant_path(stem, ocr)
        if os.path.exists(p + ".ocr.json"):
            continue
        t = time.perf_counter()
        items = ocr_file(p, reader=reader, clean=(ocr == "clean"))
        secs.append(time.perf_counter() - t)
        json.dump(items, open(p + ".ocr.json", "w"))
        print(f"[{k + 1}/{len(truth)}] {ocr} {stem}: {len(items)} lines, {secs[-1]:.1f} s", flush=True)
    if secs:
        print(f"{ocr}: mean {sum(secs) / len(secs):.1f} s/page over {len(secs)} pages")


def score(ocr: str, tag: str) -> dict:
    from pramaan.classify_extract import classify_and_extract
    from pramaan.ingest import ingest
    from pramaan.util import norm_name
    truth = json.load(open(os.path.join(ROOT, "truth.json")))
    detail, per = [], {}
    for stem, t in sorted(truth.items()):
        d = classify_and_extract(ingest(_variant_path(stem, ocr), stem))
        for f, v in t["truth"].items():
            got = d.fields[f].value if f in d.fields else None
            ok = int(norm_name(str(got)) == norm_name(str(v)))
            detail.append({"stem": stem, "doc_type": t["doc_type"], "got_type": d.doc_type, "field": f, "truth": v, "got": got, "ok": ok})
            s = per.setdefault(t["doc_type"], [0, 0]); s[0] += ok; s[1] += 1
    with open(os.path.join(ROOT, f"detail_{tag}_{ocr}.csv"), "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(detail[0])); w.writeheader(); w.writerows(detail)
    per["all"] = [sum(v[0] for v in per.values()), sum(v[1] for v in per.values())]
    for k, (ok, n) in per.items():
        print(f"{tag:7s} ocr={ocr:5s} {k:16s} {ok}/{n} = {ok / n:.3f}")
    return per


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["build", "run", "score"]); ap.add_argument("--ocr", default="base", choices=["base", "clean"])
    ap.add_argument("--tag", default="before")
    a = ap.parse_args()
    if a.cmd == "build":
        print(f"wrote {len(build())} pages to {ROOT}/img")
    elif a.cmd == "run":
        run(a.ocr)
    else:
        score(a.ocr, a.tag)
    sys.exit(0)
