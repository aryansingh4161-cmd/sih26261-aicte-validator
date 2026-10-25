"""Train OUR tamper localiser: a U-Net (ResNet-18 encoder, ImageNet-pretrained, from segmentation_models_pytorch) that
outputs a per-pixel probability of "edited". Trained on our synthetic dataset (train split only); model selection on val.
Run on Colab GPU:  python -m pramaan.model.train_unet --data /content/v1 --out /content/drive/MyDrive/pramaan_data/tamper_unet.pt
UNTESTED by the author (no torch in his sandbox). OWNER: Manviraj."""
from __future__ import annotations

import argparse
import csv
import os
import random
import time

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image
from torch.utils.data import DataLoader, Dataset

from .features import IN_CHANNELS, to_input
from .metrics import auc


class Crops(Dataset):
    def __init__(self, rows, root, size=512, train=True):
        self.rows, self.root, self.size, self.train = rows, root, size, train

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        img = Image.open(os.path.join(self.root, r["image"])).convert("RGB")
        x = to_input(img)
        _, h, w = x.shape
        m = np.zeros((h, w), np.float32)
        if r["mask"]:
            m = (np.asarray(Image.open(os.path.join(self.root, r["mask"])).convert("L")) > 127).astype(np.float32)
        s = self.size
        if r["tampered"] == "1" and r["x0"] and random.random() < 0.7:        # crop around the edit most of the time
            cx, cy = (int(float(r["x0"])) + int(float(r["x1"]))) // 2, (int(float(r["y0"])) + int(float(r["y1"]))) // 2
            x0 = min(max(0, cx - random.randint(32, s - 32)), max(0, w - s)); y0 = min(max(0, cy - random.randint(32, s - 32)), max(0, h - s))
        else:
            x0, y0 = random.randint(0, max(0, w - s)), random.randint(0, max(0, h - s))
        x, m = x[:, y0:y0 + s, x0:x0 + s], m[y0:y0 + s, x0:x0 + s]
        ph, pw = s - x.shape[1], s - x.shape[2]
        if ph or pw:
            x = np.pad(x, ((0, 0), (0, ph), (0, pw)), mode="edge"); m = np.pad(m, ((0, ph), (0, pw)))
        return torch.from_numpy(x), torch.from_numpy(m)[None]


def build_model():
    import segmentation_models_pytorch as smp
    return smp.Unet("resnet18", encoder_weights="imagenet", in_channels=IN_CHANNELS, classes=1)


def dice_loss(logits, y):
    p = torch.sigmoid(logits)
    inter = (p * y).sum((1, 2, 3)); den = p.sum((1, 2, 3)) + y.sum((1, 2, 3))
    return (1 - (2 * inter + 1) / (den + 1)).mean()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--epochs", type=int, default=12); ap.add_argument("--bs", type=int, default=8)
    ap.add_argument("--lr", type=float, default=3e-4); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--n_val", type=int, default=150); ap.add_argument("--n_train", type=int, default=None)
    a = ap.parse_args()
    random.seed(a.seed); np.random.seed(a.seed); torch.manual_seed(a.seed)
    rows = list(csv.DictReader(open(os.path.join(a.data, "manifest.csv"))))
    tr = [r for r in rows if r["split"] == "train"][: a.n_train]; va = [r for r in rows if r["split"] == "val"][: a.n_val]
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    print("device", dev, "train", len(tr), "val", len(va), flush=True)
    model = build_model().to(dev)
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.CosineAnnealingLR(opt, T_max=a.epochs)
    dl = DataLoader(Crops(tr, a.data), batch_size=a.bs, shuffle=True, num_workers=2, drop_last=True)
    pos_w = torch.tensor([10.0], device=dev)                      # edited pixels are rare
    best, log = -1.0, []
    for ep in range(a.epochs):
        model.train(); t0, tot = time.time(), 0.0
        for x, y in dl:
            x, y = x.to(dev), y.to(dev)
            lg = model(x)
            loss = F.binary_cross_entropy_with_logits(lg, y, pos_weight=pos_w) + dice_loss(lg, y)
            opt.zero_grad(); loss.backward(); opt.step(); tot += loss.item()
        sched.step()
        from .eval_model import predict_fn
        pred = predict_fn(model, dev)
        ys, ss = [], []
        for r in va:
            s, _ = pred(Image.open(os.path.join(a.data, r["image"])).convert("RGB")); ys.append(int(r["tampered"])); ss.append(s)
        v = auc(ys, ss)
        log.append((ep, tot / max(1, len(dl)), v))
        print(f"epoch {ep + 1}/{a.epochs} loss {tot / max(1, len(dl)):.4f} val_auc {v:.4f} ({time.time() - t0:.0f}s)", flush=True)
        if v > best:
            best = v
            os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
            torch.save({"state_dict": model.state_dict(), "arch": "smp.Unet/resnet18", "in_channels": IN_CHANNELS,
                        "epoch": ep + 1, "val_auc": v, "seed": a.seed}, a.out)
            print("  saved best ->", a.out, flush=True)
    with open(os.path.splitext(a.out)[0] + "_trainlog.csv", "w") as f:
        f.write("epoch,train_loss,val_auc\n" + "".join(f"{e + 1},{l:.5f},{v:.5f}\n" for e, l, v in log))
    print("best val AUC", round(best, 4))


if __name__ == "__main__":
    main()
