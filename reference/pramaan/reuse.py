"""F8 reuse across applications. check_reuse(app, docs, index_db) -> list[Finding].
A small SQLite index of every application processed: photos (sha256, perceptual hash = ahash from photo_check, and a
64x64 greyscale copy), document sha256 and certificate numbers (certificate_no, ref_no, stamp_no). An application is compared only
with applications FIRST indexed before it, so re-running any application gives the same answer and never
matches itself. A photo match needs the SAME FILE (sha256) or BOTH a close ahash AND a small 64x64 mean-abs-diff
(WK15: ahash alone matched unrelated look-alike photos). Rule ids X-REUSE-PHOTO / X-REUSE-CERT, lane human_review. OWNER: Aryan."""
from __future__ import annotations

import hashlib
import os
import re
import sqlite3

import numpy as np
from PIL import Image

from .photo_check import ahash
from .schemas import Application, DocumentRecord, Evidence, Finding
from .util import similarity

CERT_FIELDS = ("certificate_no", "ref_no", "stamp_no")
CERT_MIN_LEN = 6                   # WK16: shorter numbers (e.g. 3-digit municipal certificate numbers) collide by chance
ISSUER_FIELD = {"fire_cert": "issuing_authority", "structural_cert": "issuing_authority", "noc_format2": "university_name"}
ISSUER_SIM = 0.85                  # same issuer / university required (doc types without an issuer field: number only)
# Chosen on the demo photos (WK15, n=35 photos, 593 unrelated pairs): re-saved / resized / brightness / contrast copies
# <= 0.025 and <= 16 bits; closest unrelated pair 0.205 (11 bits). A 3% crop (0.154) is NOT caught (margin too thin).
PHOTO_MAX_BITS = 20                # ahash (256 bits) distance: a loose first filter only
PHOTO_MAX_MAD = 0.10               # mean abs diff of the 64x64 greyscale images after brightness/contrast normalisation


def photo_signature(path: str) -> str:
    """'<ahash hex>|<sha256>|<64x64 grey as hex>' (stored in the index)."""
    img = Image.open(path)
    sha = hashlib.sha256(open(path, "rb").read()).hexdigest()
    return f"{ahash(img):x}|{sha}|{np.asarray(img.convert('L').resize((64, 64)), dtype=np.uint8).tobytes().hex()}"


def photo_distance(a: str, b: str) -> tuple[bool, int, float]:
    """(same file, ahash bits, normalised mean abs diff) between two signatures. Each 64x64 grey image is z-scored
    first, so a brightness or contrast change does not count as a difference."""
    (ha, sa, ga), (hb, sb, gb) = a.split("|"), b.split("|")
    z = lambda h: (lambda v: (v - v.mean()) / (v.std() + 1e-6))(np.frombuffer(bytes.fromhex(h), np.uint8).astype(float))
    return sa == sb, bin(int(ha, 16) ^ int(hb, 16)).count("1"), float(abs(z(ga) - z(gb)).mean())


def _db(path: str) -> sqlite3.Connection:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    c = sqlite3.connect(path)
    c.execute("CREATE TABLE IF NOT EXISTS apps (seq INTEGER PRIMARY KEY AUTOINCREMENT, app_id TEXT UNIQUE)")
    c.execute("CREATE TABLE IF NOT EXISTS items (app_id TEXT, kind TEXT, key TEXT, ref TEXT)")
    return c


def _items(app: Application, docs: list[DocumentRecord]) -> list[tuple[str, str, str]]:
    """(kind, key, ref) for this application. ref = doc_id or photo file name."""
    out = []
    for d in docs:
        out.append(("sha256", d.sha256, d.doc_id))
        for f in CERT_FIELDS:
            v = d.fields.get(f)
            num = (v.value or "").strip().upper() if v else ""
            if len(re.sub(r"[^A-Z0-9]", "", num)) >= CERT_MIN_LEN:     # the key also fixes the document type
                iss = d.fields.get(ISSUER_FIELD.get(d.doc_type, ""))
                out.append(("cert", f"{d.doc_type}:{f}:{num}", f"{d.doc_id}|{(iss.value or '') if iss else ''}"))
    for p in app.photos:
        try:
            out.append(("photo", photo_signature(p), os.path.basename(p)))
        except Exception:
            continue
    return out


def _finding(app, rid, title, reason, ref, doc_id, other_app, other_ref):
    return Finding(finding_id=f"{app.app_id}-{rid}-{ref}", app_id=app.app_id, doc_id=doc_id, source="crosscheck", rule_id=rid,
                   title=title, reason=reason[:400], severity="high", confidence=0.9, lane="human_review",
                   evidence=[Evidence(doc_id=doc_id or f"photo:{ref}", page=1, text=f"also in application {other_app} ({other_ref})"[:200])])


def check_reuse(app: Application, docs: list[DocumentRecord], index_db: str = "output/reuse.db") -> list[Finding]:
    items = _items(app, docs)
    c = _db(index_db)
    try:
        c.execute("INSERT OR IGNORE INTO apps (app_id) VALUES (?)", (app.app_id,))
        seq = c.execute("SELECT seq FROM apps WHERE app_id=?", (app.app_id,)).fetchone()[0]
        earlier = "SELECT i.app_id, i.key, i.ref FROM items i JOIN apps a ON a.app_id=i.app_id WHERE a.seq<? AND i.kind=?"
        out, seen = [], set()
        for kind, key, ref in items:
            if kind == "photo":
                hits = []
                for a, k, r in c.execute(earlier, (seq, "photo")):
                    if k.count("|") != 2:                      # index row from before WK15 (ahash only): not comparable
                        continue
                    same, bits, mad = photo_distance(key, k)
                    if same or (bits <= PHOTO_MAX_BITS and mad <= PHOTO_MAX_MAD):
                        hits.append((a, f"{r}; {'same file' if same else f'ahash {bits} bits, difference {mad:.3f}'}"))
            elif kind == "cert":
                ref, my_iss = ref.split("|", 1)
                need = key.split(":", 1)[0] in ISSUER_FIELD
                hits = [(a, r.split("|", 1)[0]) for a, k, r in c.execute(earlier, (seq, kind)) if k == key and "|" in r
                        and (not need or (my_iss and similarity(my_iss, r.split("|", 1)[1]) >= ISSUER_SIM))]
            else:
                hits = [(a, r) for a, k, r in c.execute(earlier, (seq, kind)) if k == key]
            rule = "X-REUSE-PHOTO" if kind == "photo" else "X-REUSE-CERT"
            if not hits or (rule, ref) in seen:
                continue
            seen.add((rule, ref)); other_app, other_ref = hits[0]
            if kind == "photo":
                out.append(_finding(app, "X-REUSE-PHOTO", "Campus photo also used in another application",
                                    f"{ref} looks the same as {other_ref} submitted with application {other_app}.",
                                    ref, None, other_app, other_ref))
            else:
                what = "the same file" if kind == "sha256" else f"the same {key.split(':')[1].replace('_', ' ')} {key.split(':', 2)[2]}"
                out.append(_finding(app, "X-REUSE-CERT", "Document also used in another application",
                                    f"{ref} carries {what} as {other_ref} in application {other_app}.",
                                    ref, ref, other_app, other_ref))
        c.execute("DELETE FROM items WHERE app_id=?", (app.app_id,))
        c.executemany("INSERT INTO items VALUES (?,?,?,?)", [(app.app_id, k, key, r) for k, key, r in items])
        c.commit()
        return out
    finally:
        c.close()
