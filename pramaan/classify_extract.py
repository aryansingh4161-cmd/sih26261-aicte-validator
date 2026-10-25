"""classify_and_extract(doc, specs_dir) -> DocumentRecord with doc_type, fields, tables. Spec-driven (YAML), no AI at
runtime. OWNER: Jasraj (reference version)."""
from __future__ import annotations

import glob
import os
import re
from functools import lru_cache

import yaml

from .schemas import DocumentRecord, Evidence, ExtractedField
from .util import iso, parse_date


@lru_cache(maxsize=8)
def load_specs(specs_dir: str) -> tuple:
    specs = []
    for p in sorted(glob.glob(os.path.join(specs_dir, "*.yaml"))):
        with open(p) as f:
            specs.append(yaml.safe_load(f))
    return tuple(specs)


def _norm_value(v: str, typ: str):
    v = v.strip().strip(",;:")
    if typ == "date":
        d = parse_date(v)
        return (iso(d), 0.95) if d else (v, 0.4)
    if typ == "int":
        m = re.search(r"\d+", v)
        return (m.group(0), 0.95) if m else (v, 0.4)
    return (v, 0.9)


def _field(doc: DocumentRecord, name: str, fs: dict):
    lines = doc.blocks
    method = "ocr" if lines and lines[0].source == "ocr" else "regex"
    if fs.get("first_line") and lines:
        return ExtractedField(name=name, value=lines[0].text, confidence=0.7, method=method,
                              evidence=Evidence(doc_id=doc.doc_id, page=lines[0].page, bbox=lines[0].bbox, text=lines[0].text[:200]))
    labels = [l.lower() for l in fs.get("labels", [])]
    for i, b in enumerate(lines):
        if labels and b.text.strip().rstrip(":").lower() in labels and i + 1 < len(lines):
            val, conf = _norm_value(lines[i + 1].text, fs.get("type", "text"))
            nb = lines[i + 1]
            return ExtractedField(name=name, value=val, confidence=conf * nb.conf, method=method,
                                  evidence=Evidence(doc_id=doc.doc_id, page=nb.page, bbox=nb.bbox, text=nb.text[:200]))
        for pat in ([] if fs.get("join") else fs.get("patterns", [])):
            m = re.search(pat, b.text, flags=re.IGNORECASE)
            if m:
                val, conf = _norm_value(m.group(1), fs.get("type", "text"))
                return ExtractedField(name=name, value=val, confidence=conf * b.conf, method=method,
                                      evidence=Evidence(doc_id=doc.doc_id, page=b.page, bbox=b.bbox, text=b.text[:200]))
    if fs.get("join"):                      # value may wrap onto the next line: search the joined text
        joined, starts, pos = "", [], 0
        for b in lines:
            starts.append(len(joined)); joined += b.text + " "
        for pat in fs.get("patterns", []):
            m = re.search(pat, joined, flags=re.IGNORECASE)
            if m:
                k = max(i for i, st in enumerate(starts) if st <= m.start(1))
                val, conf = _norm_value(m.group(1), fs.get("type", "text"))
                return ExtractedField(name=name, value=val, confidence=0.8 * conf, method=method,
                                      evidence=Evidence(doc_id=doc.doc_id, page=lines[k].page, bbox=lines[k].bbox, text=lines[k].text[:200]))
    return None


def _rows_from_lines(doc: DocumentRecord, ts: dict) -> list:
    """Fallback for borderless tables: lines ending in one or two numbers after the header line."""
    two = "intake_prev" in ts["columns"]
    pat = re.compile(r"^(.*?)\s+(\d{1,4})\s+(\d{1,4})$" if two else r"^(.*?)\s+(\d{1,4})$")
    rows = []
    for b in doc.blocks:
        m = pat.match(b.text.strip())
        if m and not re.search(r"\d{4}-\d{2}", b.text):
            r = {"course": m.group(1).strip()}
            if two:
                r.update(intake_prev=m.group(2), intake_curr=m.group(3))
            else:
                r["intake_curr"] = m.group(2)
            rows.append(r)
    return rows


def _tables(doc: DocumentRecord, spec: dict) -> dict:
    out = {}
    tspec = spec.get("tables") or {}
    if not tspec or doc.is_scanned or not doc.path.lower().endswith(".pdf"):
        return out
    try:
        import pdfplumber
        with pdfplumber.open(doc.path) as pdf:
            raw = [t for p in pdf.pages for t in p.extract_tables()]
    except Exception:
        return out
    for tname, ts in tspec.items():
        for t in raw:
            if not t or len(t) < 2:
                continue
            hdr = [(c or "").replace("\n", " ").lower() for c in t[0]]
            idx = {}
            for col, cs in ts["columns"].items():
                hits = [j for j, h in enumerate(hdr) if any(k in h for k in cs["match"])]
                if hits:
                    idx[col] = hits[0] if cs.get("pick", "first") == "first" else hits[-1]
            if len(idx) == len(ts["columns"]):
                out[tname] = [{c: re.sub(r"\s+", " ", (r[j] or "")).strip() for c, j in idx.items()} for r in t[1:]]
                break
        if tname not in out:
            rows = _rows_from_lines(doc, ts)
            if rows:
                out[tname] = rows
    return out


def classify_and_extract(doc: DocumentRecord, specs_dir: str = "config/doc_specs") -> DocumentRecord:
    try:
        specs = load_specs(specs_dir)
        text = "\n".join(b.text for b in doc.blocks).lower()
        best, best_score, best_fields = None, 0.0, {}
        for sp in specs:
            if not any(k.lower() in text for k in sp.get("match_any", [])):
                continue
            fields = {n: f for n, fs in (sp.get("fields") or {}).items() if (f := _field(doc, n, fs))}
            score = 0.6 + 0.4 * len(fields) / max(1, len(sp.get("fields") or {}))
            if score > best_score:
                best, best_score, best_fields = sp, score, fields
        if best is None:
            slot_spec = next((s for s in specs if s["doc_type"] == doc.slot), None)
            if slot_spec is not None:      # no readable text: trust the upload slot, with low confidence
                return doc.model_copy(update={"doc_type": doc.slot, "doc_type_confidence": 0.3})
            return doc.model_copy(update={"doc_type": "unclassified", "doc_type_confidence": 0.0})
        return doc.model_copy(update={"doc_type": best["doc_type"], "doc_type_confidence": round(best_score, 3),
                                      "fields": best_fields, "tables": _tables(doc, best)})
    except Exception as e:
        md = dict(doc.metadata); md["extract_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return doc.model_copy(update={"metadata": md})
