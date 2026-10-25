"""F16: a held-out test set of edits made by an AI INPAINTING model (Stable Diffusion inpainting, run on Colab GPU).
Our U-Net never sees these during training. Adds rows with split "test_ai_inpaint" to <data>/manifest.csv.
  python -m pramaan.synth.ai_inpaint --data /content/v1 --n 150            (needs: pip install diffusers transformers accelerate)
  python -m pramaan.synth.ai_inpaint --data /content/v1 --n 150 --method classical   (OpenCV inpainting, no GPU, fallback)
Same pipeline as the main dataset: render -> scan effect -> JPEG q1 -> [edit] -> JPEG q2, layouts A/B, half edited.
The AI pipeline part is UNTESTED by the author (no diffusers/GPU in his sandbox). OWNER: Manviraj."""
from __future__ import annotations

import argparse
import csv
import os
import random
import tempfile

import numpy as np
from PIL import Image

from .make_dataset import FIELDS, _page
from .raster import jpeg_roundtrip, scan_effect

MODEL_IDS = ["stabilityai/stable-diffusion-2-inpainting", "diffusers/stable-diffusion-xl-1.0-inpainting-0.1"]
PROMPT = "scanned paper document, black printed numbers and text on white paper, sharp, high quality"
NEG = "blurry, colourful, picture, drawing, handwriting"


def load_ai():
    import torch
    from diffusers import AutoPipelineForInpainting
    last = None
    for mid in MODEL_IDS:
        for kw in ({"variant": "fp16"}, {}):
            try:
                pipe = AutoPipelineForInpainting.from_pretrained(mid, torch_dtype=torch.float16, **kw).to("cuda")
                pipe.set_progress_bar_config(disable=True)
                print("loaded", mid, kw, flush=True)
                return pipe
            except Exception as e:
                last = e
    raise RuntimeError(f"no inpainting model could be loaded: {last}")


def edit_ai(pipe, img: Image.Image, box, rng):
    W, H = img.size
    x0, y0, x1, y1 = box
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    S = 512
    left, top = min(max(0, cx - S // 2), max(0, W - S)), min(max(0, cy - S // 2), max(0, H - S))
    crop = img.crop((left, top, left + S, top + S))
    m = Image.new("L", (S, S), 0)
    pad = 2
    m.paste(255, (x0 - left - pad, y0 - top - pad, x1 - left + pad, y1 - top + pad))
    out = pipe(prompt=PROMPT, negative_prompt=NEG, image=crop, mask_image=m, num_inference_steps=25,
               guidance_scale=7.0, height=S, width=S).images[0].convert("RGB").resize((S, S))
    mm = np.array(m) > 127
    res = np.array(crop).copy(); res[mm] = np.array(out)[mm]            # only the masked pixels change
    img = img.copy(); img.paste(Image.fromarray(res), (left, top))
    full = np.zeros((H, W), np.uint8); full[top:top + S, left:left + S][mm] = 255
    return img, Image.fromarray(full)


def edit_classical(img: Image.Image, box, rng):
    import cv2
    a = np.array(img)
    x0, y0, x1, y1 = box
    m = np.zeros(a.shape[:2], np.uint8); m[y0 - 2:y1 + 2, x0 - 2:x1 + 2] = 255
    out = cv2.inpaint(a, m, 5, cv2.INPAINT_TELEA)
    return Image.fromarray(out), Image.fromarray(m)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=99); ap.add_argument("--method", choices=["ai", "classical"], default="ai")
    a = ap.parse_args()
    split = "test_ai_inpaint" if a.method == "ai" else "test_classical_inpaint"
    pipe = load_ai() if a.method == "ai" else None
    os.makedirs(os.path.join(a.data, split), exist_ok=True)
    rows = []
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        for i in range(a.n):
            rng = random.Random(f"{a.seed}-{split}-{i}")
            from .docs import DOC_TYPES
            img, boxes = _page(rng.choice(DOC_TYPES), rng.choice("AB"), rng, tmp, f"{split}{i}")
            img = scan_effect(img, rng, strength=rng.uniform(0.6, 1.3))
            q1, q2 = rng.randint(72, 92), rng.randint(62, 95)
            img = jpeg_roundtrip(img, q1)
            row = {k: "" for k in FIELDS}
            row.update(split=split, doc_type="", layout="", tampered=0, jpeg_q1=q1, jpeg_q2=q2, seed=f"{a.seed}-{split}-{i}")
            name = f"{split}_{i:05d}"
            if i % 2 == 1:
                tgt = rng.choice([b for b in boxes if b["digits"] and b["field"]])
                img, mask = (edit_ai(pipe, img, tgt["px"], rng) if pipe else edit_classical(img, tgt["px"], rng))
                row.update(tampered=1, tamper_op=f"{a.method}_inpaint", field=tgt["field"], x0=tgt["px"][0], y0=tgt["px"][1], x1=tgt["px"][2], y1=tgt["px"][3])
                row["mask"] = os.path.join(split, name + "_mask.png"); mask.save(os.path.join(a.data, row["mask"]))
            row["image"] = os.path.join(split, name + ".jpg")
            img.save(os.path.join(a.data, row["image"]), quality=q2)
            rows.append(row)
            if (i + 1) % 25 == 0:
                print(f"{i + 1}/{a.n}", flush=True)
    man = os.path.join(a.data, "manifest.csv")
    keep = [r for r in csv.DictReader(open(man)) if r["split"] != split]
    with open(man, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS); w.writeheader(); w.writerows(keep + rows)
    print(f"wrote {len(rows)} images to split {split}; manifest updated")


if __name__ == "__main__":
    main()
