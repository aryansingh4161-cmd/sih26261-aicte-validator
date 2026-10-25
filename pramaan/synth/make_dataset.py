"""Build the tamper-detection dataset (images + masks + manifest.csv) from synthetic documents.
Usage:  python -m pramaan.synth.make_dataset --out data/synthetic/v1 --n_train 2400 --n_val 300 --n_test 300 --seed 7
Every sample, tampered or not, goes through the SAME pipeline (render -> scan effect -> JPEG q1 -> [tamper] -> JPEG q2)
so the model cannot cheat by spotting a file-format difference. OWNER: Manviraj."""
from __future__ import annotations

import argparse
import csv
import os
import random
import tempfile
from typing import Dict, List

from PIL import Image

from . import content as C
from . import docs as D
from .raster import jpeg_roundtrip, render_page, scan_effect
from .tamper import ALL_OPS, HELDOUT_OPS, TRAIN_OPS, apply_tamper

SPLITS = {
    # name: (layouts, tamper ops, share of images that are tampered)
    "train": (("A", "B"), TRAIN_OPS, 0.5),
    "val": (("A", "B"), TRAIN_OPS, 0.5),
    "test_id": (("A", "B"), TRAIN_OPS, 0.5),
    "test_ood_layout": (("C",), TRAIN_OPS, 0.5),
    "test_ood_tamper": (("A", "B"), HELDOUT_OPS, 0.5),
    "test_ood_both": (("C",), HELDOUT_OPS, 0.5),
}
FIELDS = ["split", "image", "mask", "doc_type", "layout", "tampered", "tamper_op", "field", "x0", "y0", "x1", "y1",
          "jpeg_q1", "jpeg_q2", "seed"]


def _page(doc_type, layout, rng, tmpdir, tag):
    inst = C.make_institute(rng)
    det = D.default_details(rng, inst)
    pdf = os.path.join(tmpdir, f"{tag}.pdf")
    info = D.render_pdf(doc_type, layout, inst, det, pdf)
    img = render_page(pdf, dpi=100)
    W, H = img.size
    boxes = []
    for b in info["boxes"]:
        x0, y0, x1, y1 = b["bbox"]
        boxes.append({"field": b["field"], "text": b["text"], "digits": b["digits"],
                      "px": (int(x0 * W), int(y0 * H), int(x1 * W) + 1, int(y1 * H) + 1)})
    os.remove(pdf)
    return img, boxes


def make_one(split: str, idx: int, out_dir: str, seed: int, tmpdir: str) -> Dict:
    layouts, ops, share = SPLITS[split]
    rng = random.Random(f"{seed}-{split}-{idx}")
    doc_type = rng.choice(D.DOC_TYPES)
    layout = rng.choice(layouts)
    img, boxes = _page(doc_type, layout, rng, tmpdir, f"{split}{idx}")
    img = scan_effect(img, rng, strength=rng.uniform(0.6, 1.3))
    q1, q2 = rng.randint(72, 92), rng.randint(62, 95)
    img = jpeg_roundtrip(img, q1)                     # "scanner" output
    tampered = rng.random() < share
    row = {"split": split, "doc_type": doc_type, "layout": layout, "tampered": int(tampered), "tamper_op": "", "field": "",
           "x0": "", "y0": "", "x1": "", "y1": "", "jpeg_q1": q1, "jpeg_q2": q2, "seed": f"{seed}-{split}-{idx}", "mask": ""}
    mask = None
    if tampered:
        cands = [b for b in boxes if b["digits"] and b["field"]]
        tgt = rng.choice(cands)
        op = rng.choice(ops)
        donor_img = donor_box = None
        if op == "copy_move":
            others = [b for b in cands if b is not tgt]
            donor_box = rng.choice(others)["px"] if others else tgt["px"]
        if op == "splice":
            dt, dl = rng.choice(D.DOC_TYPES), rng.choice(layouts)
            donor_img, dboxes = _page(dt, dl, rng, tmpdir, f"{split}{idx}d")
            donor_img = jpeg_roundtrip(scan_effect(donor_img, rng, 1.0), q1)
            dc = [b for b in dboxes if b["digits"] and b["field"]]
            donor_box = rng.choice(dc)["px"]
        img, mask = apply_tamper(img, op, tgt["px"], tgt["text"], rng, donor_img, donor_box)
        row.update(tamper_op=op, field=tgt["field"], x0=tgt["px"][0], y0=tgt["px"][1], x1=tgt["px"][2], y1=tgt["px"][3])
    name = f"{split}_{idx:05d}"
    os.makedirs(os.path.join(out_dir, split), exist_ok=True)
    row["image"] = os.path.join(split, name + ".jpg")
    img.save(os.path.join(out_dir, row["image"]), quality=q2)   # forger's final save (second JPEG generation) for ALL samples
    if mask is not None:
        row["mask"] = os.path.join(split, name + "_mask.png")
        mask.save(os.path.join(out_dir, row["mask"]))
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--n_train", type=int, default=2400)
    ap.add_argument("--n_val", type=int, default=300)
    ap.add_argument("--n_test", type=int, default=300)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    counts = {"train": a.n_train, "val": a.n_val}
    counts.update({s: a.n_test for s in SPLITS if s.startswith("test")})
    rows: List[Dict] = []
    with tempfile.TemporaryDirectory() as tmp:
        for split, n in counts.items():
            for i in range(n):
                rows.append(make_one(split, i, a.out, a.seed, tmp))
                if (i + 1) % 200 == 0:
                    print(f"{split}: {i + 1}/{n}", flush=True)
    with open(os.path.join(a.out, "manifest.csv"), "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(rows)
    print("wrote", len(rows), "images and manifest.csv to", a.out)


if __name__ == "__main__":
    main()
