"""Extra C: checks on campus photos. GPS (from EXIF) vs declared location, blur, exact/near duplicates.
check_photos(app, today) -> list[Finding]. OWNER: Geetansh (reference version)."""
from __future__ import annotations

import math
import os
from datetime import date

import numpy as np
from PIL import Image

from .schemas import Application, Evidence, Finding

GPS_IFD = 0x8825


def _deg(v):
    d, m, s = (float(x) for x in v)
    return d + m / 60 + s / 3600


def gps_of(path: str):
    try:
        g = Image.open(path).getexif().get_ifd(GPS_IFD)
        if not g or 2 not in g or 4 not in g:
            return None
        lat, lon = _deg(g[2]), _deg(g[4])
        if g.get(1) == "S":
            lat = -lat
        if g.get(3) == "W":
            lon = -lon
        return lat, lon
    except Exception:
        return None


def km(a, b) -> float:
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((la2 - la1) / 2) ** 2 + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(h))


def blur_score(img: Image.Image) -> float:
    g = np.asarray(img.convert("L").resize((512, 384)), dtype=float)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def ahash(img: Image.Image) -> int:
    a = np.asarray(img.convert("L").resize((16, 16)), dtype=float)
    bits = (a > a.mean()).flatten()
    return int("".join("1" if b else "0" for b in bits), 2)


def _f(app, rid, title, reason, sev, path, conf=0.7):
    return Finding(finding_id=f"{app.app_id}-{rid}-{os.path.basename(path)}", app_id=app.app_id, source="photo", rule_id=rid,
                   title=title, reason=reason[:400], severity=sev, confidence=conf, lane="human_review",
                   evidence=[Evidence(doc_id=f"photo:{os.path.basename(path)}", page=1, text=os.path.basename(path))])


def check_photos(app: Application, today: date, max_km: float = 1.0, blur_thr: float = 60.0) -> list[Finding]:
    out, hashes = [], {}
    dec = (app.declared.get("latitude"), app.declared.get("longitude"))
    for p in app.photos:
        try:
            img = Image.open(p)
        except Exception:
            out.append(_f(app, "F-PHOTO-UNREADABLE", "Photo could not be opened", p, "low", p))
            continue
        g = gps_of(p)
        if g is None:
            out.append(_f(app, "F-PHOTO-NO-GPS", "Photo has no location data", f"{os.path.basename(p)} carries no GPS tag, so its location cannot be checked.", "low", p, 0.5))
        elif None not in dec and km(g, dec) > max_km:
            out.append(_f(app, "F-PHOTO-GPS", "Photo taken far from the declared campus",
                          f"{os.path.basename(p)} was taken {km(g, dec):.1f} km from the declared location ({dec[0]:.4f}, {dec[1]:.4f}).", "medium", p, 0.8))
        b = blur_score(img)
        if b < blur_thr:
            out.append(_f(app, "F-PHOTO-BLUR", "Photo is too blurred to inspect", f"Sharpness score {b:.0f} (threshold {blur_thr:.0f}, an assumption).", "low", p, 0.6))
        h = ahash(img)
        for q, h2 in hashes.items():
            if bin(h ^ h2).count("1") <= 6:
                out.append(_f(app, "F-PHOTO-DUPLICATE", "Same photo uploaded twice",
                              f"{os.path.basename(p)} looks the same as {os.path.basename(q)}.", "medium", p, 0.8))
                break
        hashes[p] = h
    return out
