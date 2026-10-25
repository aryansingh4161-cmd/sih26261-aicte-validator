"""PDF -> image, scan-like degradation, JPEG round trips. OWNER: Manviraj."""
from __future__ import annotations

import io
import random
from typing import Tuple

import numpy as np
from PIL import Image, ImageFilter


def render_page(pdf_path: str, dpi: int = 100, page: int = 0) -> Image.Image:
    import pypdfium2 as pdfium
    pdf = pdfium.PdfDocument(pdf_path)
    img = pdf[page].render(scale=dpi / 72.0).to_pil().convert("RGB")
    pdf.close()
    return img


def jpeg_roundtrip(img: Image.Image, quality: int) -> Image.Image:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=int(quality))
    buf.seek(0)
    return Image.open(buf).convert("RGB")


def scan_effect(img: Image.Image, rng: random.Random, strength: float = 1.0) -> Image.Image:
    """Cheap 'scanner/phone' look: blur, paper tint gradient, grain, contrast jitter. No rotation (keeps boxes exact)."""
    a = np.asarray(img).astype(np.float32)
    h, w, _ = a.shape
    blur = rng.uniform(0.3, 0.9) * strength
    im = Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(blur))
    a = np.asarray(im).astype(np.float32)
    # paper tint + soft vertical/horizontal illumination gradient
    tint = np.array([rng.uniform(0.94, 1.0), rng.uniform(0.94, 1.0), rng.uniform(0.90, 0.99)], dtype=np.float32)
    gx = np.linspace(rng.uniform(0.93, 1.0), rng.uniform(0.93, 1.0), w, dtype=np.float32)[None, :, None]
    gy = np.linspace(rng.uniform(0.93, 1.0), rng.uniform(0.93, 1.0), h, dtype=np.float32)[:, None, None]
    a = a * tint[None, None, :] * gx * gy
    # grain
    sigma = rng.uniform(1.5, 5.0) * strength
    nrng = np.random.default_rng(rng.randint(0, 2**31 - 1))
    a = a + nrng.normal(0, sigma, size=a.shape).astype(np.float32)
    # contrast jitter
    c = rng.uniform(0.9, 1.1)
    a = (a - 128) * c + 128
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))
