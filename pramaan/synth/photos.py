"""Synthetic campus photos for the demo bundles: a 'camera' JPEG (GPS, Make/Model, DateTimeOriginal, embedded thumbnail,
camera-style quantisation tables) and a simulated software edit. SYNTHETIC only. OWNER: Manviraj / Aryan."""
from __future__ import annotations

import io
from datetime import datetime, timedelta

import numpy as np
from PIL import Image, ImageDraw

from ..image_meta import camera_qtables, exif_thumbnail, with_thumbnail


def photo(path, rng, lat, lon, seed_img=None, taken: datetime | None = None):
    """Synthetic CAMERA photo: GPS + Make/Model + DateTimeOriginal + embedded thumbnail + camera-style JPEG tables."""
    a = np.zeros((480, 640, 3), np.uint8)
    a[:240] = (rng.randint(120, 200), rng.randint(160, 220), 235)
    a[240:] = (rng.randint(90, 140), rng.randint(110, 160), rng.randint(60, 100))
    img = Image.fromarray(a); dr = ImageDraw.Draw(img)
    for _ in range(4):
        x, w, h = rng.randint(20, 520), rng.randint(60, 160), rng.randint(60, 180)
        dr.rectangle([x, 240 - h, x + w, 300], fill=(rng.randint(150, 230),) * 3, outline=(40, 40, 40), width=3)
        for k in range(3):
            dr.rectangle([x + 10 + 30 * k, 250 - h + 20, x + 30 + 30 * k, 250 - h + 50], fill=(60, 90, 140))
    img = seed_img or img
    ex = Image.Exif()
    def dms(v):
        v = abs(v); d = int(v); m = int((v - d) * 60); return (float(d), float(m), round(((v - d) * 60 - m) * 60, 2))
    ex[0x8825] = {1: "N" if lat >= 0 else "S", 2: dms(lat), 3: "E" if lon >= 0 else "W", 4: dms(lon)}
    ex[0x010F], ex[0x0110] = "SynthCam (synthetic)", "SC-1"
    if taken is not None:
        ex[0x0132] = taken.strftime("%Y:%m:%d %H:%M:%S"); ex[0x8769] = {0x9003: taken.strftime("%Y:%m:%d %H:%M:%S")}
    th = io.BytesIO(); img.convert("RGB").resize((160, 120)).save(th, "JPEG", quality=80)
    img.save(path, exif=with_thumbnail(ex.tobytes(), th.getvalue()), qtables=camera_qtables())
    return img


def edit_photo(path, taken: datetime):
    """Simulated edit: paste a block into the picture, re-save in 'Photoshop' (standard libjpeg tables at q90),
    keep the camera's original thumbnail and taken date, set the modified date 5 days later."""
    img = Image.open(path); raw = img.info["exif"]; ex = img.getexif()
    th = exif_thumbnail(img)
    im = img.convert("RGB"); ImageDraw.Draw(im).rectangle([360, 150, 600, 330], fill=(205, 205, 200), outline=(40, 40, 40), width=3)
    ex[0x0131] = "Adobe Photoshop 25.0 (Macintosh)"; ex[0x0132] = (taken + timedelta(days=5)).strftime("%Y:%m:%d %H:%M:%S")
    im.save(path, quality=90, exif=with_thumbnail(ex.tobytes(), th) if th else raw)
