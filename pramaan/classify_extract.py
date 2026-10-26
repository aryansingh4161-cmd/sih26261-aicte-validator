"""classify_and_extract(doc, specs_dir) -> DocumentRecord with doc_type, fields, tables. Spec-driven (YAML), no AI at
runtime. OWNER: Jasraj (reference version)."""
from __future__ import annotations

import glob
import os
import re
from functools import lru_cache

import yaml

from .fuzzy import fix_date_chars, label_matches, repair_line
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
        d = parse_date(v) or parse_date(fix_date_chars(v))          # WK22: OCR O/0, l/1 swaps inside a date
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
    ocr = method == "ocr"                   # WK22: OCR lines get fuzzy labels; text PDFs are matched exactly, as before
    if ocr:
        known = list(fs.get("labels", [])) + [m.group(1).strip() for p in fs.get("patterns", [])
                                              if (m := re.match(r"\^?([A-Za-z][A-Za-z ]{3,})", p))]
        lines = [b.model_copy(update={"text": repair_line(b.text, known)}) for b in lines]

    def is_label(t):
        return t.strip().rstrip(":").lower() in labels or (ocr and any(label_matches(t, l) for l in labels))
    for i, b in enumerate(lines):
        if labels and is_label(b.text) and i + 1 < len(lines):
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
    cols = list(ts["columns"])                      # first column = text, the rest = numbers, in spec order
    pat = re.compile(r"^(.*?)" + r"\s+(\d{1,4})" * (len(cols) - 1) + "$")
    rows = []
    for b in doc.blocks:
        m = pat.match(b.text.strip())
        if m and not re.search(r"\d{4}-\d{2}", b.text):
            rows.append({c: m.group(i + 1).strip() for i, c in enumerate(cols)})
    return rows


def _word_tables(page) -> list:
    """Borderless tables from word positions: header cells = runs of words split by gaps > 5 pt; every word below goes to
    the column whose header starts left of it; lines with a number in the last column start a row, lines without one
    continue the row above (wrapped cells). Lines before the first row extend the header. Cell text is left-aligned, so a
    line whose words do not start at their column's start (running text below the table) ends it."""
    lines: list = []
    for w in sorted(page.extract_words(), key=lambda w: (round(w["top"]), w["x0"])):
        if lines and abs(w["top"] - lines[-1][0]["top"]) < 2:
            lines[-1].append(w)
        else:
            lines.append([w])
    out = []
    for hi, hl in enumerate(lines):
        starts = [w["x0"] for k, w in enumerate(hl) if k == 0 or w["x0"] - hl[k - 1]["x1"] > 5]
        if len(starts) < 2:
            continue
        col = lambda w: max([i for i, s in enumerate(starts) if s <= w["x0"] + 3] or [0])
        hdr, rows, prev = [[] for _ in starts], [], hl
        for ln in lines[hi + 1:]:
            cells, first = [[] for _ in starts], {}
            for w in ln:
                cells[col(w)].append(w["text"]); first.setdefault(col(w), w["x0"])
            if ln[0]["top"] - prev[0]["bottom"] > 3 * (prev[0]["bottom"] - prev[0]["top"]) or \
                    any(abs(x - starts[i]) > 2 for i, x in first.items()):
                break
            if re.fullmatch(r"\d{1,5}", " ".join(cells[-1])):
                rows.append(cells)
            elif rows:
                for i, c in enumerate(cells):
                    rows[-1][i] += c
            else:
                for i, c in enumerate(cells):
                    hdr[i] += c
            prev = ln
        if rows:
            head = [" ".join([w["text"] for w in hl if col(w) == i] + hdr[i]) for i in range(len(starts))]
            out.append([head] + [[" ".join(c) for c in r] for r in rows])
    return out


def _tables(doc: DocumentRecord, spec: dict) -> dict:
    out = {}
    tspec = spec.get("tables") or {}
    if not tspec or doc.is_scanned or not doc.path.lower().endswith(".pdf"):
        return out
    try:
        import pdfplumber
        with pdfplumber.open(doc.path) as pdf:
            raw = [t for p in pdf.pages for t in p.extract_tables()]
            words = [t for p in pdf.pages for t in _word_tables(p)] if not raw else []
    except Exception:
        return out
    for tname, ts in tspec.items():
        for t in raw + words:
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


def _cell_fields(doc: DocumentRecord, spec: dict) -> dict:
    """WK22, text PDFs: a field with `cell_labels` is read from the grid cell right of the cell that starts with one of the
    labels (a short qualifier such as "/University" may follow). Wrapped cell lines are joined with spaces."""
    want = {n: [l.lower() for l in fs["cell_labels"]] for n, fs in (spec.get("fields") or {}).items() if fs.get("cell_labels")}
    if not want or doc.is_scanned or not doc.path.lower().endswith(".pdf"):
        return {}
    import pdfplumber
    out = {}
    with pdfplumber.open(doc.path) as pdf:
        for pno, page in enumerate(pdf.pages[:2], start=1):
            for t in page.find_tables():
                for row in t.rows:
                    texts = [page.within_bbox(c).extract_text() if c else "" for c in row.cells]
                    for j, txt in enumerate(texts[:-1]):
                        head = re.sub(r"\s+", " ", txt or "").strip().lower()
                        for name, labs in want.items():
                            if name in out or not any(head.startswith(l) and len(head) <= len(l) + 20 for l in labs):
                                continue
                            val = re.sub(r"\s+", " ", texts[j + 1] or "").strip()
                            c = row.cells[j + 1]
                            if val and c:
                                W, H = float(page.width), float(page.height)
                                out[name] = ExtractedField(name=name, value=val, confidence=0.9, method="table",
                                                           evidence=Evidence(doc_id=doc.doc_id, page=pno, text=val[:200],
                                                                             bbox={"x0": c[0] / W, "y0": c[1] / H, "x1": c[2] / W, "y1": c[3] / H}))
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
        try:
            best_fields.update(_cell_fields(doc, best))
        except Exception:
            pass                                    # grid not readable: keep the pattern result
        return doc.model_copy(update={"doc_type": best["doc_type"], "doc_type_confidence": round(best_score, 3),
                                      "fields": best_fields, "tables": _tables(doc, best)})
    except Exception as e:
        md = dict(doc.metadata); md["extract_error"] = f"{type(e).__name__}: {str(e)[:120]}"
        return doc.model_copy(update={"metadata": md})
