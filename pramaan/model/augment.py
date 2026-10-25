"""Image-level augmentation for train_unet.py --augment (model v2 option, WK16). Applied BEFORE features.to_input, so the
input recipe (RGB + ELA q90) and the weights format are unchanged. Geometric steps (scale 0.85-1.15, rotation +-2 deg)
are applied identically to image and mask; photometric steps (blur, brightness/contrast, JPEG re-compression q60-95,
Gaussian noise) to the image only. No new edit types: test_ood_tamper / AI-inpaint stay unseen. OWNER: Manviraj."""
from __future__ import annotations

import io
import random

import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def augment(img: Image.Image, mask: Image.Image, rng: random.Random) -> tuple[Image.Image, Image.Image]:
    """img RGB, mask L (0/255) of the same size -> augmented pair of the SAME size as the input."""
    W, H = img.size
    s = rng.uniform(0.85, 1.15)
    nw, nh = max(32, int(W * s)), max(32, int(H * s))
    img, mask = img.resize((nw, nh), Image.BICUBIC), mask.resize((nw, nh), Image.NEAREST)
    canvas, mcanvas = Image.new("RGB", (W, H), (255, 255, 255)), Image.new("L", (W, H), 0)
    ox, oy = (W - nw) // 2, (H - nh) // 2                     # centre: crop when larger, white paper border when smaller
    canvas.paste(img, (ox, oy)); mcanvas.paste(mask, (ox, oy))
    img, mask = canvas, mcanvas
    ang = rng.uniform(-2.0, 2.0)
    img = img.rotate(ang, resample=Image.BICUBIC, fillcolor=(255, 255, 255))
    mask = mask.rotate(ang, resample=Image.NEAREST, fillcolor=0)
    if rng.random() < 0.3:
        img = img.filter(ImageFilter.GaussianBlur(rng.uniform(0.3, 1.2)))
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.85, 1.15))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.85, 1.15))
    if rng.random() < 0.5:
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=rng.randint(60, 95)); buf.seek(0)
        img = Image.open(buf).convert("RGB")
    if rng.random() < 0.3:
        a = np.asarray(img, np.float32) + np.random.default_rng(rng.randint(0, 2**31)).normal(0, rng.uniform(1, 6), (H, W, 3))
        img = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
    return img, mask
