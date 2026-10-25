"""Image metadata helpers for pramaan/metadata_forensics.py and the synthetic generator: EXIF tags, the embedded EXIF
thumbnail (IFD1), JPEG quantisation tables vs the standard libjpeg (IJG) tables. Pillow + struct only. OWNER: Aryan."""
from __future__ import annotations

import hashlib
import io
import struct
from functools import lru_cache

from PIL import Image

T_SOFTWARE, T_DATETIME, T_PROC, T_EXIF_IFD, T_DTO, T_MAKE = 0x0131, 0x0132, 0x000B, 0x8769, 0x9003, 0x010F


def exif_tags(img: Image.Image) -> dict:
    """{'software', 'processing', 'datetime', 'datetime_original', 'make'} (missing -> None)."""
    ex = img.getexif()
    sub = ex.get_ifd(T_EXIF_IFD) if T_EXIF_IFD in ex else {}
    g = lambda v: str(v).strip("\x00 ").strip() if v else None
    return {"software": g(ex.get(T_SOFTWARE)), "processing": g(ex.get(T_PROC)), "datetime": g(ex.get(T_DATETIME)),
            "datetime_original": g(sub.get(T_DTO)), "make": g(ex.get(T_MAKE))}


def _tiff(raw: bytes):
    t = raw[6:] if raw.startswith(b"Exif\x00\x00") else raw
    if t[:2] not in (b"II", b"MM"):
        return None, None
    return t, "<" if t[:2] == b"II" else ">"


def exif_thumbnail(img: Image.Image) -> bytes | None:
    """JPEG bytes of the IFD1 thumbnail, or None."""
    t, e = _tiff(img.info.get("exif") or b"")
    if t is None:
        return None
    try:
        off = struct.unpack(e + "I", t[4:8])[0]
        n = struct.unpack(e + "H", t[off:off + 2])[0]
        ifd1 = struct.unpack(e + "I", t[off + 2 + 12 * n: off + 6 + 12 * n])[0]
        if not ifd1:
            return None
        m = struct.unpack(e + "H", t[ifd1:ifd1 + 2])[0]
        vals = {}
        for i in range(m):
            tag, _, _, v = struct.unpack(e + "HHII", t[ifd1 + 2 + 12 * i: ifd1 + 14 + 12 * i])
            vals[tag] = v
        if 0x0201 in vals and 0x0202 in vals:
            return t[vals[0x0201]: vals[0x0201] + vals[0x0202]]
    except (struct.error, IndexError):
        return None
    return None


def with_thumbnail(exif_bytes: bytes, thumb_jpeg: bytes) -> bytes:
    """Append an IFD1 thumbnail to EXIF bytes made by Pillow (Exif.tobytes()). Used by the synthetic 'camera'."""
    head = b"Exif\x00\x00" if exif_bytes.startswith(b"Exif\x00\x00") else b""
    t, e = _tiff(exif_bytes)
    t = bytearray(t)
    off = struct.unpack(e + "I", t[4:8])[0]
    n = struct.unpack(e + "H", t[off:off + 2])[0]
    t += b"\x00" * (len(t) % 2)
    ifd1 = len(t)
    t[off + 2 + 12 * n: off + 6 + 12 * n] = struct.pack(e + "I", ifd1)
    data_at = ifd1 + 2 + 12 * 3 + 4
    t += struct.pack(e + "H", 3) + struct.pack(e + "HHII", 0x0103, 3, 1, 6)
    t += struct.pack(e + "HHII", 0x0201, 4, 1, data_at) + struct.pack(e + "HHII", 0x0202, 4, 1, len(thumb_jpeg))
    t += struct.pack(e + "I", 0) + thumb_jpeg
    return head + bytes(t)


def thumb_diff(img: Image.Image, thumb_jpeg: bytes) -> float:
    """Mean absolute difference (0..255) between main image and thumbnail, both as 64x64 greyscale."""
    import numpy as np
    a = np.asarray(img.convert("L").resize((64, 64)), dtype=float)
    b = np.asarray(Image.open(io.BytesIO(thumb_jpeg)).convert("L").resize((64, 64)), dtype=float)
    return float(abs(a - b).mean())


@lru_cache(maxsize=1)
def _ijg_tables() -> dict:
    """Standard libjpeg tables for quality 1..100, read back exactly as Pillow reports them."""
    out, im = {}, Image.new("RGB", (16, 16), (128, 128, 128))
    for q in range(1, 101):
        buf = io.BytesIO(); im.save(buf, "JPEG", quality=q)
        out[q] = {k: list(v) for k, v in Image.open(buf).quantization.items()}
    return out


def qt_info(img: Image.Image) -> tuple[str | None, int | None]:
    """(sha256[:16] of the tables, IJG quality if they are exactly the standard libjpeg tables, else None)."""
    qt = getattr(img, "quantization", None)
    if not qt:
        return None, None
    tabs = {k: list(v) for k, v in qt.items()}
    h = hashlib.sha256(repr(sorted(tabs.items())).encode()).hexdigest()[:16]
    return h, next((q for q, t in _ijg_tables().items() if t == tabs), None)


def camera_qtables(seed: int = 3) -> list[list[int]]:
    """Synthetic 'camera' tables: IJG q92 with a fixed non-standard perturbation (cameras rarely use plain IJG)."""
    base = _ijg_tables()[92]
    return [[max(1, v + ((i * 7 + seed + k) % 3 == 0)) for i, v in enumerate(base[k])] for k in sorted(base)]
