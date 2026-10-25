"""NON-LEARNED baseline: classic Error Level Analysis (ELA). Our trained model must beat this on held-out data.
No training happens here except choosing two thresholds on the VALIDATION split."""
from __future__ import annotations

import io
from typing import Tuple

import numpy as np
from PIL import Image


def ela_map(img: Image.Image, quality: int = 90) -> np.ndarray:
    """Per-pixel error level (float32, 0..255): |image - JPEG(image, quality)| averaged over channels."""
    buf = io.BytesIO()
    img.convert("RGB").save(buf, format="JPEG", quality=quality)
    buf.seek(0)
    re = Image.open(buf).convert("RGB")
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    b = np.asarray(re).astype(np.float32)
    return np.abs(a - b).mean(axis=2)


def box_filter(a: np.ndarray, k: int) -> np.ndarray:
    """Mean filter with a k x k window using cumulative sums (numpy only)."""
    pad = k // 2
    p = np.pad(a, pad, mode="edge")
    c = np.cumsum(np.cumsum(p, axis=0), axis=1)
    c = np.pad(c, ((1, 0), (1, 0)))
    h, w = a.shape
    s = c[k:k + h, k:k + w] - c[:h, k:k + w] - c[k:k + h, :w] + c[:h, :w]
    return s / (k * k)


def heatmap(img: Image.Image, k: int = 15) -> np.ndarray:
    e = ela_map(img)
    return box_filter(e, k)


def score(img: Image.Image) -> Tuple[float, np.ndarray]:
    """Image-level score = robust z-score of the hottest 15x15 window: (max - median) / MAD of the ELA heatmap.
    Returns (score, heatmap). On our first medium test (n=100 per set) AUC was 0.65 / 0.58 / 0.54 / 0.50 on
    test_id / ood_layout / ood_tamper / ood_both: a weak but honest baseline. Choose the variant on VALIDATION only."""
    h = heatmap(img)
    med = float(np.median(h))
    mad = float(np.median(np.abs(h - med))) + 1e-6
    return float((h.max() - med) / mad), h


def predict_mask(h: np.ndarray, thr: float) -> np.ndarray:
    """Pixel mask: heat more than thr robust-sigmas above the page median."""
    med = float(np.median(h))
    mad = float(np.median(np.abs(h - med))) + 1e-6
    return (h - med) / mad > thr
