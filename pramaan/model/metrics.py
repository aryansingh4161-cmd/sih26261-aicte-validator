"""Metrics with no sklearn dependency. AUC is rank based; CI by bootstrap."""
from __future__ import annotations

from typing import Dict, Sequence, Tuple

import numpy as np


def auc(y_true: Sequence[int], score: Sequence[float]) -> float:
    y = np.asarray(y_true).astype(int)
    s = np.asarray(score).astype(float)
    pos, neg = s[y == 1], s[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")
    order = np.argsort(np.concatenate([pos, neg]), kind="mergesort")
    allv = np.concatenate([pos, neg])[order]
    ranks = np.empty(len(allv))
    i = 0
    while i < len(allv):                      # average ranks for ties
        j = i
        while j + 1 < len(allv) and allv[j + 1] == allv[i]:
            j += 1
        ranks[i:j + 1] = (i + j) / 2 + 1
        i = j + 1
    r_pos = ranks[np.argsort(order)][: len(pos)]
    return float((r_pos.sum() - len(pos) * (len(pos) + 1) / 2) / (len(pos) * len(neg)))


def auc_ci(y_true, score, n_boot: int = 1000, seed: int = 0) -> Tuple[float, float, float]:
    y = np.asarray(y_true).astype(int)
    s = np.asarray(score).astype(float)
    base = auc(y, s)
    rng = np.random.default_rng(seed)
    vals = []
    for _ in range(n_boot):
        idx = rng.integers(0, len(y), len(y))
        v = auc(y[idx], s[idx])
        if not np.isnan(v):
            vals.append(v)
    if not vals:
        return base, float("nan"), float("nan")
    return base, float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def pixel_prf(pred_masks, true_masks) -> Dict[str, float]:
    """Micro-averaged pixel precision / recall / F1 / IoU over tampered images."""
    tp = fp = fn = 0
    for p, t in zip(pred_masks, true_masks):
        p, t = p.astype(bool), t.astype(bool)
        tp += int((p & t).sum())
        fp += int((p & ~t).sum())
        fn += int((~p & t).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    iou = tp / (tp + fp + fn) if tp + fp + fn else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "iou": iou}


def best_threshold(y_true, score) -> float:
    """Threshold maximising F1 for image-level detection (call on VALIDATION data only)."""
    y = np.asarray(y_true).astype(int)
    s = np.asarray(score).astype(float)
    best_t, best_f = float(np.median(s)), -1.0
    for t in np.unique(np.quantile(s, np.linspace(0.02, 0.98, 97))):
        p = s >= t
        tp = int((p & (y == 1)).sum()); fp = int((p & (y == 0)).sum()); fn = int((~p & (y == 1)).sum())
        f = 2 * tp / (2 * tp + fp + fn) if (2 * tp + fp + fn) else 0.0
        if f > best_f:
            best_f, best_t = f, float(t)
    return best_t


def image_f1(y_true, score, thr: float) -> Dict[str, float]:
    y = np.asarray(y_true).astype(int)
    p = np.asarray(score).astype(float) >= thr
    tp = int((p & (y == 1)).sum()); fp = int((p & (y == 0)).sum()); fn = int((~p & (y == 1)).sum()); tn = int((~p & (y == 0)).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    return {"precision": prec, "recall": rec, "f1": f1, "tp": tp, "fp": fp, "fn": fn, "tn": tn}
