"""Run OUR trained tamper localiser on scanned pages. tamper_check(app_id, doc, weights_path) -> list[Finding].
Returns [] (and the pipeline notes it) if torch or the weights file is missing. Output wording: "possible alteration".
OWNER: Manviraj (reference version). UNTESTED by the author (no torch in his sandbox)."""
from __future__ import annotations

import os

import numpy as np
from PIL import Image

from .schemas import BBox, DocumentRecord, Evidence, Finding

_CACHE: dict = {}


def available(weights_path: str) -> bool:
    try:
        import torch  # noqa: F401
        import segmentation_models_pytorch  # noqa: F401
    except Exception:
        return False
    return os.path.exists(weights_path)


def _pages(doc: DocumentRecord, max_pages: int = 3):
    if doc.path.lower().endswith((".jpg", ".jpeg", ".png", ".tif", ".tiff")):
        return [(1, Image.open(doc.path).convert("RGB"))]
    from .synth.raster import render_page
    return [(i + 1, render_page(doc.path, dpi=100, page=i)) for i in range(min(doc.pages, max_pages))]


def tamper_check(app_id: str, doc: DocumentRecord, weights_path: str = "data/models/tamper_unet.pt",
                 threshold: float = 0.5) -> list[Finding]:
    if not doc.is_scanned or doc.pages == 0 or not available(weights_path):
        return []
    import torch
    from .model.eval_model import load, predict_fn
    if weights_path not in _CACHE:
        _CACHE[weights_path] = predict_fn(load(weights_path, "cpu"), "cpu")
    predict = _CACHE[weights_path]
    out = []
    for page, img in _pages(doc):
        score, prob = predict(img)
        if score < threshold:
            continue
        ys, xs = np.where(prob > 0.5)
        H, W = prob.shape
        bb = BBox(x0=xs.min() / W, y0=ys.min() / H, x1=(xs.max() + 1) / W, y1=(ys.max() + 1) / H) if len(xs) else None
        heat_path = os.path.join("output", "heatmaps", f"{doc.doc_id}_p{page}.png")
        try:
            os.makedirs(os.path.dirname(heat_path), exist_ok=True)
            Image.fromarray((np.clip(prob, 0, 1) * 255).astype(np.uint8)).save(heat_path)
        except Exception:
            heat_path = ""
        out.append(Finding(finding_id=f"{app_id}-F-TAMPER-{doc.doc_id}-p{page}", app_id=app_id, doc_id=doc.doc_id,
                           source="tamper_model", rule_id="F-TAMPER", title="Possible alteration in a scanned page",
                           reason=f"Our trained model marks a region on page {page} as possibly edited (score {score:.2f}, "
                                  f"threshold {threshold:.2f}). Heatmap: {heat_path or 'not saved'}.",
                           severity="high" if score > 0.8 else "medium", confidence=round(float(score), 3), lane="human_review",
                           evidence=[Evidence(doc_id=doc.doc_id, page=page, bbox=bb, text="highlighted region")]))
    return out
