"""Synthetic 'edit after saving': append an INCREMENTAL UPDATE to a PDF that replaces one text string on page 1
(like a PDF editor would). Written by hand (no pypdf / pikepdf needed): new content-stream object + new Info + xref + /Prev.
Used for demo APP-16 and the metadata contract test. SYNTHETIC only. OWNER: Manviraj / Aryan."""
from __future__ import annotations

import re
from datetime import datetime


def _pdf_date(dt: datetime) -> str:
    return dt.strftime("D:%Y%m%d%H%M%S+05'30'")


def incremental_text_edit(path: str, old: str, new: str, mod_date: datetime,
                          producer: str = "Generic PDF Editor 9.1 (synthetic)") -> None:
    from pdfminer.pdfdocument import PDFDocument
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfparser import PDFParser
    from pdfminer.pdftypes import PDFObjRef, resolve1
    raw = open(path, "rb").read()
    with open(path, "rb") as f:
        doc = PDFDocument(PDFParser(f))
        page = next(PDFPage.create_pages(doc))
        ref = page.attrs["Contents"]
        ref = ref[0] if isinstance(ref, list) else ref
        if not isinstance(ref, PDFObjRef):
            raise ValueError("page contents are not an indirect object")
        data = resolve1(ref).get_data()
        trailer = doc.xrefs[-1].get_trailer()
        info_ref, root_ref = trailer["Info"], trailer["Root"]
        info = {k: (v.decode("latin-1") if isinstance(v, bytes) else v) for k, v in resolve1(info_ref).items()}
        size = int(trailer["Size"])
    needle = b"(" + old.encode("latin-1") + b")"
    if needle not in data:
        raise ValueError(f"text {old!r} not found as one string in the page content")
    data = data.replace(needle, b"(" + new.encode("latin-1") + b")", 1)
    prev = int(re.findall(rb"startxref\s+(\d+)", raw)[-1])
    out = bytearray(raw if raw.endswith(b"\n") else raw + b"\n")
    offs = {}
    offs[ref.objid] = len(out)
    out += f"{ref.objid} 0 obj\n<< /Length {len(data)} >>\nstream\n".encode() + data + b"\nendstream\nendobj\n"
    info.update(Producer=producer, ModDate=_pdf_date(mod_date))
    esc = lambda s: str(s).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
    offs[info_ref.objid] = len(out)
    out += (f"{info_ref.objid} 0 obj\n<< " + " ".join(f"/{k} ({esc(v)})" for k, v in info.items() if isinstance(v, str))
            + " >>\nendobj\n").encode("latin-1")
    xref = len(out)
    out += b"xref\n0 1\n0000000000 65535 f \n"
    for oid in sorted(offs):
        out += f"{oid} 1\n{offs[oid]:010d} 00000 n \n".encode()
    out += (f"trailer\n<< /Size {size} /Root {root_ref.objid} 0 R /Info {info_ref.objid} 0 R /Prev {prev} >>\n"
            f"startxref\n{xref}\n%%EOF\n").encode()
    with open(path, "wb") as f:
        f.write(out)
