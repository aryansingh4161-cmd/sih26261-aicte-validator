"""Evaluate the trained U-Net on the four held-out test sets with the SAME harness as the baseline.
python -m pramaan.model.eval_model --data /content/v1 --weights /content/drive/MyDrive/pramaan_data/tamper_unet.pt
Appends rows 'unet.*' to eval/results.csv. UNTESTED by the author (no torch). OWNER: Manviraj."""
from __future__ import annotations

import argparse

import numpy as np
import torch

from .eval_common import evaluate
from .features import image_score, pad32, to_input


def load(weights: str, dev: str):
    from .train_unet import build_model
    ck = torch.load(weights, map_location=dev, weights_only=False)
    m = build_model(); m.load_state_dict(ck["state_dict"]); m.to(dev).eval()
    return m


def predict_fn(model, dev):
    @torch.no_grad()
    def predict(img):
        x, (h, w) = pad32(to_input(img))
        was = model.training; model.eval()
        p = torch.sigmoid(model(torch.from_numpy(x)[None].to(dev)))[0, 0, :h, :w].float().cpu().numpy()
        model.train(was)
        return image_score(p), p
    return predict


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--weights", required=True)
    ap.add_argument("--out", default="eval/results.csv"); ap.add_argument("--n_max", type=int, default=None)
    a = ap.parse_args()
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = load(a.weights, dev)
    # pixel mask = probability above 0.5 (fixed, stated in the notes); image threshold chosen on val inside evaluate()
    evaluate("unet", predict_fn(model, dev), a.data, lambda p, thr: p > 0.5, a.out, a.n_max)
