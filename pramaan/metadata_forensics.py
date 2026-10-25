"""Metadata forensics. check_metadata(app_id, doc, submitted_on=None, photo=False) -> list[Finding], rule ids F-META-*.
PDFs (source pdf_forensics): REVISION-DIFF (text of earlier incremental revisions vs the final one), XMP-HISTORY, DATES.
Images (source photo; photos and scanned certificates): EXIF-SOFTWARE, EXIF-THUMB, EXIF-DATES, and for photos JPEG-QT
(weak signal). Wording: "possible alteration, needs human review". Never raises. OWNER: Jasraj / Aryan."""
from __future__ import annotations

import difflib
import glob
import io
import os
import re
from datetime import date, datetime

import yaml

from .image_meta import exif_tags, exif_thumbnail, qt_info, thumb_diff
from .schemas import BBox, DocumentRecord, Evidence, Finding

EDITORS = ("photoshop", "gimp", "snapseed", "lightroom", "canva", "edited", "picsart", "pixlr", "affinity")
THUMB_DIFF = 2.0          # mean abs diff 0..255 at 64x64; chosen on clean demo photos (n=34, max 0.25); edited APP-17 = 7.8
THUMB_STRONG = 6.0        # WK16: 2.0-6.0 is only a weak signal (a real unedited phone photo measured 2.35, n=5 real photos)
PRINTED = ("printed_on", "issue_date", "approval_date", "sworn_date")
_SPECS: dict = {}


def _f(app_id, doc, rid, title, reason, sev, ev, conf=0.9, photo=False):
    return Finding(finding_id=f"{app_id}-{rid}-{doc.doc_id}", app_id=app_id, doc_id=None if photo else doc.doc_id,
                   source="photo" if photo or not doc.path.lower().endswith(".pdf") else "pdf_forensics", rule_id=rid,
                   title=title, reason=(reason + " Possible alteration, needs human review.")[:400], severity=sev,
                   confidence=conf, lane="human_review", evidence=ev or [Evidence(doc_id=doc.doc_id, page=1, text=doc.filename[:200])])


def _d(s) -> date | None:
    m = re.search(r"(\d{4})[-:]?(\d{2})[-:]?(\d{2})", str(s or ""))
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3))) if m else None
    except ValueError:
        return None


def _revisions(raw: bytes) -> list[bytes]:
    """Byte prefixes ending at each %%EOF except the last. The first one is skipped for linearized files."""
    ends = [m.end() for m in re.finditer(rb"%%EOF[\r\n]*", raw)]
    revs = [raw[:e] for e in ends[:-1]]
    return revs[1:] if revs and b"/Linearized" in raw[:1024] else revs


def _lines(data: bytes):
    import pdfplumber
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        pages = [[(" ".join(l["text"].split()), (l["x0"] / float(p.width), l["top"] / float(p.height),
                   l["x1"] / float(p.width), l["bottom"] / float(p.height))) for l in p.extract_text_lines()] for p in pdf.pages]
        return pages, dict(pdf.metadata or {})


def _diff(old_pages, new_pages, doc_id) -> list[Evidence]:
    ev = []
    for pno, (a, b) in enumerate(zip(old_pages, new_pages), start=1):
        sm = difflib.SequenceMatcher(a=[t for t, _ in a], b=[t for t, _ in b], autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal":
                continue
            old, new = " / ".join(t for t, _ in a[i1:i2]) or "(nothing)", " / ".join(t for t, _ in b[j1:j2]) or "(removed)"
            box = b[j1][1] if j2 > j1 else (a[i1][1] if i2 > i1 else None)
            ev.append(Evidence(doc_id=doc_id, page=pno, bbox=BBox(x0=box[0], y0=box[1], x1=box[2], y1=box[3]) if box else None,
                               text=f"'{old}' -> '{new}'"[:200]))
    return ev


def _xmp(raw: bytes) -> dict:
    pk = re.findall(rb"<x:xmpmeta.*?</x:xmpmeta>", raw, re.S)
    if not pk:
        return {}
    x = pk[-1].decode("utf-8", "replace")

    def val(tag):                                  # attribute form tag="v" or element form <tag>v</tag>
        m = re.search(rf"{tag}\s*=\s*\"([^\"]*)\"|<{tag}>([^<]*)</{tag}>", x)
        return (m.group(1) or m.group(2)) if m else None
    acts = re.findall(r"stEvt:action\s*=\s*\"([^\"]+)\"|<stEvt:action>([^<]+)</stEvt:action>", x)
    agents = re.findall(r"stEvt:softwareAgent\s*=\s*\"([^\"]+)\"|<stEvt:softwareAgent>([^<]+)</stEvt:softwareAgent>", x)
    return {"creator_tool": val("xmp:CreatorTool"), "producer": val("pdf:Producer"), "doc_id": val("xmpMM:DocumentID"),
            "instance_id": val("xmpMM:InstanceID"), "actions": [a or b for a, b in acts], "agents": [a or b for a, b in agents]}


def _spec(doc_type: str, specs_dir: str) -> dict:
    if not _SPECS:
        for p in glob.glob(os.path.join(specs_dir, "*.yaml")):
            with open(p) as f:
                s = yaml.safe_load(f) or {}
            _SPECS[s.get("doc_type")] = s
    return _SPECS.get(doc_type, {})


def _pdf(app_id, doc, submitted_on, specs_dir) -> list[Finding]:
    out, raw = [], open(doc.path, "rb").read()
    final, fmeta = _lines(raw)
    last_mod = fmeta.get("ModDate")
    revs = _revisions(raw)
    for i, rev in enumerate(revs):
        try:
            pages, meta = _lines(rev)
        except Exception:
            continue
        ev = _diff(pages, final, doc.doc_id)
        if not ev and i == len(revs) - 1 and doc.metadata.get("has_signature_field"):
            last_mod = meta.get("ModDate")          # last revision only adds the signature: its date is not an edit
        if ev and not any(f.rule_id == "F-META-REVISION-DIFF" for f in out):
            out.append(_f(app_id, doc, "F-META-REVISION-DIFF", "Text changed in a later revision of this PDF",
                          f"The PDF keeps an earlier revision (saved before the last update); {len(ev)} line(s) differ: "
                          f"{ev[0].text}.", "high", ev[:5], 0.95))
    x = _xmp(raw)
    if x:
        exp = [e.lower() for e in _spec(doc.doc_type, specs_dir).get("expected_producers") or []]
        tools = {t for t in [x["creator_tool"], x["producer"], *x["agents"]] if t}
        odd = sorted(t for t in tools if exp and not any(e in t.lower() for e in exp))
        later = [a for a in x["actions"][1:] if a.lower() in ("saved", "converted", "edited", "modified")]
        if odd or later:
            ids = " DocumentID and InstanceID differ (saved again)." if x["doc_id"] and x["instance_id"] and x["doc_id"] != x["instance_id"] else ""
            out.append(_f(app_id, doc, "F-META-XMP-HISTORY", "Editing history in the PDF's XMP metadata",
                          (f"Tools not expected for {doc.doc_type}: {', '.join(odd)}." if odd else "")
                          + (f" History after creation: {', '.join(later)}." if later else "") + ids, "medium" if odd else "low",
                          [Evidence(doc_id=doc.doc_id, page=1, text=f"XMP tools: {', '.join(sorted(tools))}"[:200])], 0.7))
    cdate, mdate = _d(fmeta.get("CreationDate")), _d(last_mod)
    printed = next(((k, _d(doc.fields[k].value)) for k in PRINTED if k in doc.fields and _d(doc.fields[k].value)), None)
    why = []
    if cdate and printed and (cdate - printed[1]).days > 30:
        why.append(f"file created {cdate} but the document says {printed[0].replace('_', ' ')} {printed[1]} "
                   f"({(cdate - printed[1]).days} days earlier; a later download would also explain this)")
    if mdate and _d(submitted_on) and mdate > _d(submitted_on):
        why.append(f"file modified {mdate}, after the application was submitted on {submitted_on}")
    if why:
        out.append(_f(app_id, doc, "F-META-DATES", "PDF dates do not fit the document", "; ".join(why).capitalize() + ".", "low",
                      [Evidence(doc_id=doc.doc_id, page=1, text=f"CreationDate {cdate}, ModDate {mdate}")], 0.6))
    return out


def _img(app_id, doc, submitted_on, photo) -> list[Finding]:
    from PIL import Image
    out, img = [], Image.open(doc.path)
    tags = exif_tags(img)
    with open(doc.path, "rb") as fh:                         # editors such as Canva name themselves in XMP, not EXIF (WK15)
        m = re.search(rb"xmp:CreatorTool(?:>|=\")([^<\"]{1,80})", fh.read(512 * 1024))
    xmp_tool = m.group(1).decode("utf-8", "replace").strip() if m else None
    sw = " / ".join(t for t in (tags["software"], tags["processing"], xmp_tool) if t)
    if sw and any(e in sw.lower() for e in EDITORS):
        out.append(_f(app_id, doc, "F-META-EXIF-SOFTWARE", "Image was saved by editing software",
                      f"EXIF Software / XMP CreatorTool says '{sw[:80]}'.", "medium",
                      [Evidence(doc_id=doc.doc_id, page=1, text=f"Software: {sw}"[:200])], 0.8, photo))
    th = exif_thumbnail(img)
    if th:
        diff = thumb_diff(img, th)
        if diff > THUMB_DIFF:
            strong = diff > THUMB_STRONG
            out.append(_f(app_id, doc, "F-META-EXIF-THUMB", "Embedded thumbnail differs from the picture" + ("" if strong else " (weak signal)"),
                          f"The camera thumbnail stored inside the file does not match the main image (difference {diff:.1f}; "
                          + (f"above {THUMB_STRONG:g}: a strong sign the picture was edited after it was taken)." if strong else
                             f"between {THUMB_DIFF:g} and {THUMB_STRONG:g}: weak signal, real unedited phone photos can reach this)."),
                          "high" if strong else "low", [Evidence(doc_id=doc.doc_id, page=1, text=f"thumbnail difference {diff:.1f}")],
                          0.85 if strong else 0.4, photo))
    taken, mod, why = _d(tags["datetime_original"]), _d(tags["datetime"]), []
    if taken and mod and (mod - taken).days > 1:
        why.append(f"modified {mod}, {(mod - taken).days} days after it was taken ({taken})")
    if taken and _d(submitted_on) and taken > _d(submitted_on):
        why.append(f"taken {taken}, after the application was submitted on {submitted_on}")
    if why:
        out.append(_f(app_id, doc, "F-META-EXIF-DATES", "Photo dates do not fit", "; ".join(why).capitalize() + ".", "medium",
                      [Evidence(doc_id=doc.doc_id, page=1, text=f"DateTimeOriginal {taken}, DateTime {mod}")], 0.7, photo))
    if photo and img.format == "JPEG":
        h, q = qt_info(img)
        if q is not None:
            out.append(_f(app_id, doc, "F-META-JPEG-QT", "JPEG tables typical of re-saving in software (weak signal)",
                          f"Quantisation tables are the standard libjpeg set at quality {q} (hash {h}), typical of a re-save by "
                          "editing or conversion software rather than a camera. Weak signal on its own.", "low",
                          [Evidence(doc_id=doc.doc_id, page=1, text=f"JPEG tables {h} = libjpeg q{q}")], 0.4, photo))
    return out


def check_metadata(app_id: str, doc: DocumentRecord, submitted_on: str | None = None, photo: bool = False,
                   specs_dir: str = "config/doc_specs") -> list[Finding]:
    try:
        if doc.path.lower().endswith(".pdf"):
            return _pdf(app_id, doc, submitted_on, specs_dir)
        if doc.path.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
            return _img(app_id, doc, submitted_on, photo)
    except Exception:
        return []
    return []
