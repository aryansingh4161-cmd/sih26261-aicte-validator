"""Page images for the viewer (WK26): rendered once from the submitted file and cached in <out>/pages/. Width 820 px."""
from __future__ import annotations

import os

from PIL import Image

from .ctx import Ctx

WIDTH = 820


def page(ctx: Ctx, app_id: str, doc_id: str, n: int):
    r = ctx.result(app_id)
    d = next((d for d in r.documents if d.doc_id == doc_id), None)
    if d is None:
        raise KeyError(doc_id)
    cache = os.path.join(ctx.out, "pages", f"{doc_id}_p{n}.png")
    if os.path.exists(cache):
        return Image.open(cache)
    try:
        if d.path.lower().endswith((".jpg", ".jpeg", ".png")):
            img = Image.open(d.path).convert("RGB")
        else:
            from pramaan.synth.raster import render_page
            img = render_page(d.path, dpi=110, page=n - 1)
    except Exception:
        return None
    img = img.resize((WIDTH, round(img.height * WIDTH / img.width)), Image.LANCZOS)
    img = img.quantize(colors=48, method=Image.Quantize.MEDIANCUT)     # paper, ink, a few greys: ~4x smaller, no visible loss
    os.makedirs(os.path.dirname(cache), exist_ok=True)
    img.save(cache, optimize=True)
    return img
