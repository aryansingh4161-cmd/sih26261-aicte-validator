"""REAL checks on the PDF file itself (no mocks): structure/metadata/font consistency, and digital-signature validation
with pyHanko. Findings say "possible alteration, needs human review", never "forged". OWNER: Jasraj (reference version).
signature_check is UNTESTED in the author's sandbox (pyHanko not installable there): test it on a Mac (Jasraj W3)."""
from __future__ import annotations

import re
from collections import Counter

from .schemas import DocumentRecord, Evidence, Finding, VerificationResult
from .util import now_iso


def _family(font: str) -> str:
    f = re.sub(r"^[A-Z]{6}\+", "", font or "")
    f = re.split(r"[-,]", f)[0]
    return re.sub(r"(MT|PS|Bold|Italic|Oblique|Roman)$", "", f).lower()


def _f(app_id, doc, rid, title, reason, sev, ev=None, conf=0.7):
    return Finding(finding_id=f"{app_id}-{rid}-{doc.doc_id}", app_id=app_id, doc_id=doc.doc_id, source="pdf_forensics",
                   rule_id=rid, title=title, reason=reason[:400], severity=sev, confidence=conf, lane="human_review",
                   evidence=ev or [Evidence(doc_id=doc.doc_id, page=1, text=doc.filename[:200])])


def _pdfdate(s):
    m = re.search(r"(\d{14})", str(s or ""))
    return m.group(1) if m else None


def pdf_structure_checks(app_id: str, doc: DocumentRecord, spec: dict) -> list[Finding]:
    out: list[Finding] = []
    if doc.pages == 0 or not doc.path.lower().endswith(".pdf"):
        return out
    md, spec = doc.metadata, spec or {}
    prod = str(md.get("producer") or "")
    exp = spec.get("expected_producers") or []
    if exp and not any(e.lower() in prod.lower() for e in exp):
        out.append(_f(app_id, doc, "F-PDF-PRODUCER", "PDF made by unexpected software",
                      f"Documents of this type are normally produced by {', '.join(exp)}; this file says '{prod or 'none'}'.", "medium"))
    if int(md.get("eof_markers") or 0) > 1 and not md.get("has_signature_field"):
        out.append(_f(app_id, doc, "F-PDF-INCREMENTAL", "File was saved again after it was created",
                      f"{md.get('eof_markers')} end-of-file markers found (incremental updates) and no signature.", "low"))
    c, m = _pdfdate(md.get("creation_date")), _pdfdate(md.get("mod_date"))
    if c and m and m[:8] > c[:8]:
        out.append(_f(app_id, doc, "F-PDF-MODDATE", "File modified after creation",
                      f"Created {c[:8]}, modified {m[:8]}.", "low", conf=0.5))
    try:
        import pdfplumber
        with pdfplumber.open(doc.path) as pdf:
            chars = [(i, ch) for i, p in enumerate(pdf.pages, start=1) for ch in p.chars]
            dims = {i: (float(p.width), float(p.height)) for i, p in enumerate(pdf.pages, start=1)}
        fam = Counter(_family(ch.get("fontname")) for _, ch in chars)
        total = sum(fam.values()) or 1
        seen = set()
        for name, fld in doc.fields.items():
            ev = fld.evidence
            if not ev or not ev.bbox or ev.page not in dims or (ev.page, ev.bbox.y0) in seen:
                continue
            W, H = dims[ev.page]
            inside = [ch for p, ch in chars if p == ev.page and ch["x0"] >= ev.bbox.x0 * W - 1 and ch["x1"] <= ev.bbox.x1 * W + 1
                      and ch["top"] >= ev.bbox.y0 * H - 1 and ch["bottom"] <= ev.bbox.y1 * H + 1]
            rare = {_family(ch.get("fontname")) for ch in inside if fam[_family(ch.get("fontname"))] / total < 0.05}
            if rare:
                seen.add((ev.page, ev.bbox.y0))
                out.append(_f(app_id, doc, f"F-PDF-FONT-MIX-{name}", f"Different font inside the '{name}' value",
                              f"The text of {name} uses font {', '.join(sorted(rare))}, which appears almost nowhere else in this file.",
                              "medium", [ev], 0.75))
    except Exception:
        pass
    return out


def _vr(doc, status, note, source="pyHanko validation (real)"):
    return VerificationResult(doc_id=doc.doc_id, method="digital_signature", source=source, mock=False,
                              timestamp=now_iso(), status=status, note=note[:300])


def signature_check(doc: DocumentRecord, trust_roots: list[str]) -> VerificationResult:
    if not doc.path.lower().endswith(".pdf") or doc.pages == 0:
        return _vr(doc, "manual_review_required", "not a readable PDF")
    try:
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.sign.validation import validate_pdf_signature
        from pyhanko_certvalidator import ValidationContext
        try:
            from pyhanko.keys import load_cert_from_pemder
        except ImportError:
            from pyhanko.sign.general import load_cert_from_pemder
    except Exception as e:
        return _vr(doc, "manual_review_required", f"pyHanko not installed: {e}")
    try:
        roots = [load_cert_from_pemder(p) for p in trust_roots]
        with open(doc.path, "rb") as f:
            sigs = PdfFileReader(f).embedded_signatures
            if not sigs:
                return _vr(doc, "manual_review_required", "no digital signature found")
            st = validate_pdf_signature(sigs[0], ValidationContext(trust_roots=roots, allow_fetching=False))
            cov = str(getattr(st, "coverage", ""))
        if not st.intact or not st.valid:
            return _vr(doc, "mismatch_detected", "signature does not match the document content (changed after signing)")
        if "ENTIRE_FILE" not in cov:
            return _vr(doc, "manual_review_required", f"content was added after signing ({cov})")
        if not st.trusted:
            return _vr(doc, "manual_review_required", "signature intact but signer certificate is not from a trusted root")
        return _vr(doc, "verified", f"signature intact and trusted; signer: {getattr(st, 'signing_cert', None) and st.signing_cert.subject.human_friendly}")
    except Exception as e:
        msg = str(e)
        if "expired" in msg.lower():
            return _vr(doc, "expired", f"signer certificate expired: {msg[:150]}")
        return _vr(doc, "manual_review_required", f"could not validate: {type(e).__name__}: {msg[:150]}")
