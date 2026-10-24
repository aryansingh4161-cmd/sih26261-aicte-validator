#!/usr/bin/env python3
"""Probe PDF metadata and structure; append one result row per PDF to probe_results.csv."""

import csv
import sys
from pathlib import Path

import fitz  # PyMuPDF
import pdfplumber

COLUMNS = [
    "file", "pages", "text_chars_page1", "images_page1", "producer",
    "creator", "creation_date", "mod_date", "eof_markers",
    "has_signature_field", "fonts_page1",
]
OUTPUT_CSV = Path("probe_results.csv")


def probe_pdf(path: Path) -> dict:
    raw = path.read_bytes()
    eof_markers = raw.count(b"%%EOF")
    has_signature = b"/ByteRange" in raw or b"/Type /Sig" in raw

    with fitz.open(path) as doc:
        pages = len(doc)
        if pages == 0:
            raise ValueError("PDF has no pages")
        page = doc[0]
        text_chars = len(page.get_text().strip())
        images = len(page.get_images(full=True))
        metadata = doc.metadata or {}

    fonts = set()
    with pdfplumber.open(path) as pdf:
        if pdf.pages:
            for char in (pdf.pages[0].chars or []):
                font = char.get("fontname")
                if font:
                    fonts.add(font)

    return {
        "file": str(path),
        "pages": pages,
        "text_chars_page1": text_chars,
        "images_page1": images,
        "producer": metadata.get("producer") or "",
        "creator": metadata.get("creator") or "",
        "creation_date": metadata.get("creationDate") or "",
        "mod_date": metadata.get("modDate") or "",
        "eof_markers": eof_markers,
        "has_signature_field": has_signature,
        "fonts_page1": "; ".join(sorted(fonts)),
    }


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python pdf_probe.py file1.pdf file2.pdf ...")
        return 2

    rows = []
    for name in sys.argv[1:]:
        path = Path(name)
        try:
            row = probe_pdf(path)
            rows.append(row)
            print(",".join(str(row[col]).replace(",", " ") for col in COLUMNS))
        except Exception as exc:
            print(f"{name}: ERROR: {exc}", file=sys.stderr)

    if rows:
        needs_header = not OUTPUT_CSV.exists() or OUTPUT_CSV.stat().st_size == 0
        with OUTPUT_CSV.open("a", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=COLUMNS)
            if needs_header:
                writer.writeheader()
            writer.writerows(rows)
        print(f"\nAppended {len(rows)} row(s) to {OUTPUT_CSV}")

    return 0 if rows else 1


if __name__ == "__main__":
    raise SystemExit(main())
