"""Shared evaluation helpers. Any model (ELA baseline, U-Net) plugs in as a function  predict(img)->(score, heatmap).
Rows are appended to eval/results.csv with columns: metric_id,metric,value,unit,n,set,label,source_file,notes"""
from __future__ import annotations

import csv
import os
from typing import Callable, Dict, List, Tuple

import numpy as np
from PIL import Image

from . import metrics as M

RESULT_COLS = ["metric_id", "metric", "value", "unit", "n", "set", "label", "source_file", "notes"]
TEST_SETS = ["test_id", "test_ood_layout", "test_ood_tamper", "test_ood_both", "test_ai_inpaint", "test_classical_inpaint"]


def load_manifest(data_dir: str) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    with open(os.path.join(data_dir, "manifest.csv"), newline="") as f:
        for r in csv.DictReader(f):
            out.setdefault(r["split"], []).append(r)
    return out


def score_split(rows: List[dict], data_dir: str, predict: Callable, want_heat: bool = False):
    ys, ss, heats, masks = [], [], [], []
    for r in rows:
        img = Image.open(os.path.join(data_dir, r["image"])).convert("RGB")
        s, h = predict(img)
        ys.append(int(r["tampered"])); ss.append(s)
        if want_heat and r["tampered"] == "1" and r["mask"]:
            heats.append(h); masks.append(np.array(Image.open(os.path.join(data_dir, r["mask"])).convert("L")) > 127)
    return ys, ss, heats, masks


def evaluate(name: str, predict: Callable, data_dir: str, mask_fn: Callable, out_csv: str, n_max: int | None = None,
             label: str = "measured") -> List[dict]:
    """mask_fn(heatmap, threshold)->bool mask. Threshold is chosen on VALIDATION only."""
    man = load_manifest(data_dir)
    val_rows = man["val"][:n_max] if n_max else man["val"]
    yv, sv, _, _ = score_split(val_rows, data_dir, predict)
    thr = M.best_threshold(yv, sv)
    res: List[dict] = []
    for sp in TEST_SETS:
        rows = man.get(sp, [])
        rows = rows[:n_max] if n_max else rows
        if not rows:
            continue
        y, s, hs, ms = score_split(rows, data_dir, predict, want_heat=True)
        a, lo, hi = M.auc_ci(y, s)
        f = M.image_f1(y, s, thr)
        pm = [mask_fn(h, thr) for h in hs]
        px = M.pixel_prf(pm, ms) if hs else {"f1": float("nan"), "iou": float("nan")}
        base = dict(n=len(y), set=sp, label=label, source_file=out_csv, notes=f"model={name}; thr chosen on val={thr:.3f}; 95% CI by bootstrap")
        res += [dict(metric_id=f"{name}.auc.{sp}", metric=f"{name} image AUC", value=round(a, 4), unit="auc", **base),
                dict(metric_id=f"{name}.auc_lo.{sp}", metric=f"{name} AUC CI low", value=round(lo, 4), unit="auc", **base),
                dict(metric_id=f"{name}.auc_hi.{sp}", metric=f"{name} AUC CI high", value=round(hi, 4), unit="auc", **base),
                dict(metric_id=f"{name}.f1.{sp}", metric=f"{name} image F1", value=round(f["f1"], 4), unit="f1", **base),
                dict(metric_id=f"{name}.pixel_f1.{sp}", metric=f"{name} pixel F1", value=round(px["f1"], 4), unit="f1", **base),
                dict(metric_id=f"{name}.iou.{sp}", metric=f"{name} pixel IoU", value=round(px["iou"], 4), unit="iou", **base)]
    new = not os.path.exists(out_csv)
    os.makedirs(os.path.dirname(out_csv) or ".", exist_ok=True)
    with open(out_csv, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_COLS)
        if new:
            w.writeheader()
        w.writerows(res)
    for r in res:
        if r["metric_id"].startswith(f"{name}.auc.") or ".f1." in r["metric_id"]:
            print(r["metric_id"], r["value"], "n=", r["n"])
    return res
