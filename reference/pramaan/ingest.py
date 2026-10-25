"""ingest(path, doc_id, slot) -> DocumentRecord. Reads the text layer (pdfplumber) or an OCR sidecar. Never raises.
OWNER: Jasraj (reference version)."""
from __future__ import annotations

import json
import os
import re

from .schemas import BBox, DocumentRecord, TextBlock
from .util import sha256_file

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".tif", ".tiff")


def _clip(v: float) -> float:
    return max(0.0, min(1.0, float(v)))


def _fonts(pdf) -> list:
    names = set()
    for page in pdf.pages:
        for ch in page.chars:
            n = ch.get("fontname") or ""
            names.add(re.sub(r"^[A-Z]{6}\+", "", n))
    return sorted(n for n in names if n)


def _sidecar(path: str) -> list:
    side = path + ".ocr.json"
    if not os.path.exists(side):
        return []
    with open(side) as f:
        items = json.load(f)
    out = []
    for it in items:
        b = it.get("bbox", [0, 0, 0, 0])
        out.append(TextBlock(page=int(it.get("page", 1)), text=str(it.get("text", "")), source="ocr",
                             conf=float(it.get("conf", 0.5)),
                             bbox=BBox(x0=_clip(b[0]), y0=_clip(b[1]), x1=_clip(b[2]), y1=_clip(b[3]))))
    return out


def ingest(path: str, doc_id: str, slot: str | None = None) -> DocumentRecord:
    base = dict(doc_id=doc_id, filename=os.path.basename(path), path=path, slot=slot)
    try:
        base["sha256"] = sha256_file(path)
    except Exception as e:
        return DocumentRecord(sha256="", metadata={"error": f"cannot read file: {e}"}, **base)
    try:
        if path.lower().endswith(IMAGE_EXT):
            return DocumentRecord(pages=1, is_scanned=True, blocks=_sidecar(path), **base)
        import pdfplumber
        with open(path, "rb") as f:
            raw = f.read()
        blocks, n_chars = [], 0
        with pdfplumber.open(path) as pdf:
            md = pdf.metadata or {}
            for i, page in enumerate(pdf.pages, start=1):
                W, H = float(page.width), float(page.height)
                for ln in page.extract_text_lines():
                    t = (ln.get("text") or "").strip()
                    if not t:
                        continue
                    n_chars += len(t)
                    blocks.append(TextBlock(page=i, text=t, source="text_layer",
                                            bbox=BBox(x0=_clip(ln["x0"] / W), y0=_clip(ln["top"] / H),
                                                      x1=_clip(ln["x1"] / W), y1=_clip(ln["bottom"] / H))))
            pages = len(pdf.pages)
            fonts = _fonts(pdf)
        meta = {"producer": md.get("Producer"), "creator": md.get("Creator"),
                "creation_date": md.get("CreationDate"), "mod_date": md.get("ModDate"),
                "eof_markers": raw.count(b"%%EOF"),
                "has_signature_field": any(k in raw for k in (b"/ByteRange", b"/Type /Sig", b"/Type/Sig")),
                "fonts": fonts}
        scanned = pages > 0 and n_chars / pages < 30
        if scanned:
            blocks += _sidecar(path)
        return DocumentRecord(pages=pages, is_scanned=scanned, metadata=meta, blocks=blocks, **base)
    except Exception as e:
        return DocumentRecord(pages=0, metadata={"error": f"{type(e).__name__}: {str(e)[:120]}"}, **base)
