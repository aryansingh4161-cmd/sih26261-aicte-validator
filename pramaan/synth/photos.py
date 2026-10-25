"""Synthetic campus photos for the demo bundles: a 'camera' JPEG (GPS, Make/Model, DateTimeOriginal, embedded thumbnail,
camera-style quantisation tables) and a simulated software edit. SYNTHETIC only. OWNER: Manviraj / Aryan."""
from __future__ import annotations

import io
import random
from datetime import datetime, timedelta

import numpy as np
from PIL import Image, ImageDraw

from ..image_meta import camera_qtables, exif_thumbnail, with_thumbnail


def scene(r: random.Random, W: int = 640, H: int = 480) -> Image.Image:
    """A varied synthetic campus scene: random horizon, sky gradient, textured ground, 1-6 coloured buildings with
    window grids and optional roofs, trees, a road, sensor noise. Unrelated scenes must not look like near-duplicates."""
    hz = r.randint(int(H * 0.3), int(H * 0.7))
    top, bot = np.array([r.randint(60, 200), r.randint(90, 210), r.randint(150, 255)]), np.array([r.randint(150, 255)] * 2 + [r.randint(170, 255)])
    t = np.linspace(0, 1, hz)[:, None, None]
    a = np.zeros((H, W, 3), np.float32)
    a[:hz] = top * (1 - t) + bot * t
    g = np.array([r.randint(40, 150), r.randint(60, 170), r.randint(20, 110)], np.float32)
    rs = np.random.default_rng(r.randint(0, 2**31))
    a[hz:] = g + rs.normal(0, r.uniform(6, 20), (H - hz, W, 1))
    img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)); dr = ImageDraw.Draw(img)
    if r.random() < 0.6:                                         # a road / path
        x = r.randint(0, W); dr.polygon([(x - 20, hz), (x + 20, hz), (x + r.randint(80, 260), H), (x - r.randint(80, 260), H)],
                                        fill=(r.randint(70, 130),) * 3)
    for _ in range(r.randint(1, 6)):
        w, h = r.randint(50, 240), r.randint(40, int(hz * 0.9))
        x, base = r.randint(-30, W - 30), hz + r.randint(0, 40)
        col = tuple(r.randint(90, 240) for _ in range(3))
        dr.rectangle([x, base - h, x + w, base], fill=col, outline=tuple(max(0, c - 70) for c in col), width=r.randint(1, 4))
        rows, cols = r.randint(1, max(1, h // 30)), r.randint(1, max(1, w // 28))
        wc = (r.randint(30, 120), r.randint(60, 140), r.randint(100, 200))
        for i in range(rows):
            for j in range(cols):
                x0, y0 = x + 6 + j * (w - 8) // cols, base - h + 8 + i * (h - 12) // rows
                dr.rectangle([x0, y0, x0 + max(4, (w - 8) // cols - 8), y0 + max(4, (h - 12) // rows - 10)], fill=wc)
        if r.random() < 0.4:
            dr.polygon([(x - 6, base - h), (x + w + 6, base - h), (x + w // 2, base - h - r.randint(15, 60))],
                       fill=tuple(r.randint(80, 180) for _ in range(3)))
    for _ in range(r.randint(0, 6)):
        cx, cy, rad = r.randint(0, W), hz + r.randint(-10, 60), r.randint(12, 45)
        dr.ellipse([cx - rad, cy - 2 * rad, cx + rad, cy], fill=(r.randint(20, 70), r.randint(80, 150), r.randint(20, 70)))
    a = np.asarray(img, np.float32) + rs.normal(0, r.uniform(2, 7), (H, W, 3))
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def photo(path, rng, lat, lon, seed_img=None, taken: datetime | None = None):
    """Synthetic CAMERA photo: GPS + Make/Model + DateTimeOriginal + embedded thumbnail + camera-style JPEG tables."""
    img = seed_img or scene(random.Random(rng.random()))
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
