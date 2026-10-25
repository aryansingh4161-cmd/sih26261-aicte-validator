"""The ONE input recipe used by training, evaluation and the app (keep them identical). OWNER: Manviraj.
4 channels: R, G, B scaled to 0..1, plus the ELA map at JPEG quality 90 scaled by 1/20 and clipped to 0..1."""
from __future__ import annotations

import numpy as np
from PIL import Image

from .baseline import ela_map

IN_CHANNELS = 4


def to_input(img: Image.Image) -> np.ndarray:
    rgb = np.asarray(img.convert("RGB"), dtype=np.float32) / 255.0
    ela = np.clip(ela_map(img, 90) / 20.0, 0, 1)[..., None]
    return np.concatenate([rgb, ela], axis=2).transpose(2, 0, 1).astype(np.float32)    # (4, H, W)


def pad32(x: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    """Pad (C,H,W) to multiples of 32 (U-Net needs it). Returns padded array and the original (H, W)."""
    _, h, w = x.shape
    H, W = (h + 31) // 32 * 32, (w + 31) // 32 * 32
    return np.pad(x, ((0, 0), (0, H - h), (0, W - w)), mode="edge"), (h, w)


def image_score(prob: np.ndarray) -> float:
    """Image-level score from the probability map: mean of the top 0.2% pixels (robust to single-pixel noise)."""
    flat = np.sort(prob.ravel())
    k = max(1, int(len(flat) * 0.002))
    return float(flat[-k:].mean())
