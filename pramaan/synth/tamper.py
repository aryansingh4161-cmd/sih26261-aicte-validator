"""Tamper operations on page images. Each returns (new_image, mask) where mask is 255 on edited pixels.
Training uses T1-T3. T4 and T5 are HELD OUT (never trained on) to test generalisation. OWNER: Manviraj.
NOT covered (say so in the deck): AI-inpainting, whole-page re-scans, edits of the PDF text layer itself."""
from __future__ import annotations

import os
import random
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw, ImageFont

FONT_DIR = os.path.join(os.path.dirname(__file__), "fonts")
TRAIN_OPS = ("replace_digits", "copy_move", "splice")
HELDOUT_OPS = ("erase", "font_swap")
ALL_OPS = TRAIN_OPS + HELDOUT_OPS
PAD = 2


def _font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(os.path.join(FONT_DIR, name), max(size, 6))


def _bg_color(img: Image.Image, box) -> Tuple[int, int, int]:
    x0, y0, x1, y1 = box
    w, h = img.size
    a = np.asarray(img)
    ring = []
    for (rx0, ry0, rx1, ry1) in [(x0 - 6, y0 - 6, x1 + 6, y0 - 1), (x0 - 6, y1 + 1, x1 + 6, y1 + 6)]:
        rx0, ry0, rx1, ry1 = max(rx0, 0), max(ry0, 0), min(rx1, w), min(ry1, h)
        if rx1 > rx0 and ry1 > ry0:
            ring.append(a[ry0:ry1, rx0:rx1].reshape(-1, 3))
    if not ring:
        return (255, 255, 255)
    return tuple(int(v) for v in np.median(np.concatenate(ring), axis=0))


def _ink_color(img: Image.Image, box) -> Tuple[int, int, int]:
    x0, y0, x1, y1 = box
    a = np.asarray(img.crop((x0, y0, x1, y1))).reshape(-1, 3)
    if len(a) == 0:
        return (20, 20, 20)
    lum = a.sum(axis=1)
    idx = np.argsort(lum)[: max(len(a) // 20, 1)]
    return tuple(int(v) for v in a[idx].mean(axis=0))


def _change_digits(text: str, rng: random.Random) -> str:
    out = list(text)
    pos = [i for i, ch in enumerate(out) if ch.isdigit()]
    if not pos:
        return text
    for i in rng.sample(pos, k=min(len(pos), rng.choice([1, 1, 2]))):
        out[i] = rng.choice([d for d in "0123456789" if d != out[i]])
    return "".join(out)


def _draw_text(img: Image.Image, box, text: str, font_name: str, scale: float, ink) -> None:
    x0, y0, x1, y1 = box
    sz = int(round((y1 - y0) / 1.05 * scale))
    f = _font(font_name, sz)
    d = ImageDraw.Draw(img)
    baseline = y1 - 0.25 * (y1 - y0) / 1.05
    d.text((x0, baseline), text, font=f, fill=ink, anchor="ls")


def apply_tamper(img: Image.Image, op: str, box, text: str, rng: random.Random,
                 donor_img: Optional[Image.Image] = None, donor_box=None) -> Tuple[Image.Image, Image.Image]:
    """box = (x0,y0,x1,y1) pixels of the token to edit; text = its original text."""
    out = img.copy()
    x0, y0, x1, y1 = [int(v) for v in box]
    W, H = out.size
    px0, py0, px1, py1 = max(x0 - PAD, 0), max(y0 - PAD, 0), min(x1 + PAD, W), min(y1 + PAD, H)
    bg = _bg_color(out, (px0, py0, px1, py1))
    ink = _ink_color(out, (x0, y0, x1, y1))
    mask = Image.new("L", out.size, 0)
    d = ImageDraw.Draw(out)
    if op in ("replace_digits", "font_swap"):
        new = _change_digits(text, rng)
        d.rectangle([px0, py0, px1 - 1, py1 - 1], fill=bg)
        if op == "replace_digits":
            _draw_text(out, (x0, y0, x1, y1), new, "DejaVuSans.ttf", 0.92, ink)
        else:
            font = rng.choice(["DejaVuSerif.ttf", "DejaVuSansMono.ttf"])
            _draw_text(out, (x0, y0, x1, y1), new, font, rng.uniform(1.05, 1.2), ink)
    elif op == "erase":
        d.rectangle([px0, py0, px1 - 1, py1 - 1], fill=bg)
    elif op in ("copy_move", "splice"):
        src_img, sb = (out, donor_box) if op == "copy_move" else (donor_img, donor_box)
        if src_img is None or sb is None:
            raise ValueError("copy_move/splice need donor_box (and donor_img for splice)")
        crop = src_img.crop(tuple(int(v) for v in sb)).resize((px1 - px0, py1 - py0))
        out.paste(crop, (px0, py0))
    else:
        raise ValueError("unknown op " + op)
    ImageDraw.Draw(mask).rectangle([px0, py0, px1 - 1, py1 - 1], fill=255)
    return out, mask
