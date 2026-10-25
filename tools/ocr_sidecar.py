"""Real OCR for scanned documents: writes <file>.ocr.json in the format pramaan/ingest.py reads
([{page, text, bbox: [x0, y0, x1, y1] as page fractions, conf}], one item per text LINE).
  python -m tools.ocr_sidecar data/demo/docs/APP-12/structural_cert_scan.jpg [--dpi 200] [--force]
Uses EasyOCR on CPU (local, no cloud). Overwrites an existing sidecar only with --force. OWNER: Jasraj / Aryan."""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

PIP = "pip install easyocr"


def _pages(path: str, dpi: int):
    if path.lower().endswith(".pdf"):
        import pypdfium2 as pdfium
        from pramaan.synth.raster import render_page
        return [render_page(path, dpi=dpi, page=i) for i in range(len(pdfium.PdfDocument(path)))]
    from PIL import Image
    return [Image.open(path).convert("RGB")]


def _lines(segs, W, H, page):
    """EasyOCR gives phrases; ingest matches patterns line by line, so merge phrases whose vertical centres overlap."""
    boxes = []
    for quad, text, conf in segs:
        xs, ys = [p[0] for p in quad], [p[1] for p in quad]
        boxes.append([min(xs), min(ys), max(xs), max(ys), text, float(conf)])
    boxes.sort(key=lambda b: (b[1] + b[3]) / 2)
    lines: list = []
    for b in boxes:
        cy = (b[1] + b[3]) / 2
        cur = lines[-1] if lines else None
        if cur and abs(cy - cur["cy"]) < 0.5 * min(b[3] - b[1], cur["h"]):
            cur["items"].append(b)
        else:
            lines.append({"cy": cy, "h": b[3] - b[1], "items": [b]})
    out = []
    for ln in lines:
        it = sorted(ln["items"], key=lambda b: b[0])
        out.append({"page": page, "text": " ".join(b[4] for b in it).strip(),
                    "bbox": [min(b[0] for b in it) / W, min(b[1] for b in it) / H, max(b[2] for b in it) / W, max(b[3] for b in it) / H],
                    "conf": round(float(np.mean([b[5] for b in it])), 3)})
    return [o for o in out if o["text"]]


def ocr_file(path: str, dpi: int = 200, reader=None) -> list:
    if reader is None:
        import easyocr
        reader = easyocr.Reader(["en"], gpu=False, verbose=False)
    items = []
    for i, img in enumerate(_pages(path, dpi)):
        W, H = img.size
        items += _lines(reader.readtext(np.asarray(img)), W, H, i + 1)
    return items


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+"); ap.add_argument("--dpi", type=int, default=200); ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    try:
        import easyocr
    except ImportError:
        print(f"EasyOCR is not installed. Run:\n    {PIP}\n(in the activated .venv), then run this command again.")
        sys.exit(2)
    rd = easyocr.Reader(["en"], gpu=False, verbose=False)
    for f in a.files:
        side = f + ".ocr.json"
        if os.path.exists(side) and not a.force:
            print(f"skip {f}: {side} exists (use --force)")
            continue
        items = ocr_file(f, a.dpi, rd)
        with open(side, "w") as fh:
            json.dump(items, fh, indent=1)
        print(f"wrote {len(items)} lines to {side} (EasyOCR, mean conf {np.mean([x['conf'] for x in items]) if items else 0:.2f})")
