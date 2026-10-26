"""WK22: model 1 / model 2 / ensemble (mean heatmap) side by side on the tamper test sets. No retraining.
  python -m tools.ensemble_eval --data /kaggle/working/v1 --m1 data/models/tamper_unet.pt --m2 data/models/model2_tamper_unet.pt
  [--sets test_id,test_ood_layout,test_ai_inpaint] [--n_max 300]
Thresholds: each model's image threshold is chosen on VALIDATION only = the 95th percentile of the
clean val pages' scores (the rule behind model 1's 0.136). Pixel mask = heatmap > 0.5 (same as eval_model). Both models run in ONE
pass per image, so the ensemble costs nothing extra. Writes eval/results_ensemble.csv (append) and prints the decision rule:
  switch to ensemble only if AUC(ens) > AUC(m1) on test_ood_layout AND AUC(ens) >= AUC(m1) - 0.02 on every other set.
"Any layer" here = model only: the font-mix and PDF-revision checks read PDFs, these test pages are images, so they add
nothing on this set (designed limitation, stated in the output). OWNER: Aryan / Manviraj."""
from __future__ import annotations

import argparse
import csv
import os
import time

import numpy as np
from PIL import Image

from pramaan.model import metrics as M
from pramaan.model.eval_common import RESULT_COLS, TEST_SETS, load_manifest
from pramaan.model.features import image_score

FPR_TARGET = 0.05
MARGIN = 0.02


def val_threshold(y, s, target: float = FPR_TARGET) -> float:
    """Same rule as model 1's 0.136 (WK15): the (1 - target) quantile of the clean VALIDATION scores."""
    clean = [v for t, v in zip(y, s) if t == 0]
    return float(np.percentile(clean, 100 * (1 - target))) if clean else 0.5


def score_all(rows, data_dir, preds, want_heat):
    """One pass: every model's heatmap per image; the ensemble = their mean."""
    out = {n: {"y": [], "s": [], "h": [], "m": []} for n in list(preds) + ["ensemble"]}
    for r in rows:
        img = Image.open(os.path.join(data_dir, r["image"])).convert("RGB")
        heats = {n: p(img)[1] for n, p in preds.items()}
        heats["ensemble"] = np.mean(list(heats.values()), axis=0)
        mask = None
        if want_heat and r["tampered"] in ("1", 1) and r.get("mask"):
            mask = np.array(Image.open(os.path.join(data_dir, r["mask"])).convert("L")) > 127
        for n, h in heats.items():
            o = out[n]; o["y"].append(int(r["tampered"])); o["s"].append(image_score(h))
            if mask is not None:
                o["h"].append(h > 0.5); o["m"].append(mask)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True); ap.add_argument("--m1", default="data/models/tamper_unet.pt")
    ap.add_argument("--m2", default="data/models/model2_tamper_unet.pt"); ap.add_argument("--sets", default=",".join(TEST_SETS))
    ap.add_argument("--n_max", type=int, default=None); ap.add_argument("--out", default="eval/results_ensemble.csv")
    a = ap.parse_args()
    import torch
    from pramaan.model.eval_model import load, predict_fn
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    preds = {"model1": predict_fn(load(a.m1, dev), dev), "model2": predict_fn(load(a.m2, dev), dev)}
    man, t0 = load_manifest(a.data), time.time()
    cut = (lambda r: r[:a.n_max]) if a.n_max else (lambda r: r)
    val = score_all(cut(man["val"]), a.data, preds, False)
    thr = {n: val_threshold(v["y"], v["s"]) for n, v in val.items()}
    res, auc = [], {}
    note = lambda n: f"{n}; threshold {thr[n]:.4f} tuned on val (FPR<=5%, n={len(val[n]['y'])}); measured on this test set; 95% CI bootstrap"
    for sp in a.sets.split(","):
        rows = cut(man.get(sp, []))
        if not rows:
            print(f"skip {sp}: not in {a.data}/manifest.csv"); continue
        out = score_all(rows, a.data, preds, True)
        for n, o in out.items():
            y, s = o["y"], o["s"]
            au, lo, hi = M.auc_ci(y, s); auc[(n, sp)] = au
            px = M.pixel_prf(o["h"], o["m"]) if o["h"] else {"f1": float("nan")}
            caught = sum(1 for t, v in zip(y, s) if t == 1 and v >= thr[n]); edits = sum(y)
            fa = sum(1 for t, v in zip(y, s) if t == 0 and v >= thr[n]); clean = len(y) - edits
            base = dict(unit="", n=len(y), set=sp, label="measured", source_file=a.out, notes=note(n))
            res += [dict(base, metric_id=f"{n}.auc.{sp}", metric=f"{n} image AUC", value=round(au, 4)),
                    dict(base, metric_id=f"{n}.auc_lo.{sp}", metric=f"{n} AUC 95% CI low", value=round(lo, 4)),
                    dict(base, metric_id=f"{n}.auc_hi.{sp}", metric=f"{n} AUC 95% CI high", value=round(hi, 4)),
                    dict(base, metric_id=f"{n}.pixel_f1.{sp}", metric=f"{n} pixel F1 (heatmap > 0.5)", value=round(px["f1"], 4)),
                    dict(base, metric_id=f"{n}.anylayer_caught.{sp}", metric=f"{n} edits caught at val threshold (any layer = model only)",
                         value=f"{caught}/{edits}"),
                    dict(base, metric_id=f"{n}.anylayer_false_alarms.{sp}", metric=f"{n} clean pages flagged at val threshold",
                         value=f"{fa}/{clean}")]
            print(f"{sp:22s} {n:9s} AUC {au:.3f} [{lo:.3f},{hi:.3f}] pixF1 {px['f1']:.3f} caught {caught}/{edits} false {fa}/{clean}")
        print(f"  ({time.time() - t0:.0f} s so far)", flush=True)
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_COLS)
        if new:
            w.writeheader()
        w.writerows(res)
    print("val thresholds (tuned on val, FPR<=5%):", {k: round(v, 4) for k, v in thr.items()})
    sets = sorted({sp for _, sp in auc})
    if "test_ood_layout" in sets:
        win = auc[("ensemble", "test_ood_layout")] > auc[("model1", "test_ood_layout")]
        ok = all(auc[("ensemble", sp)] >= auc[("model1", sp)] - MARGIN for sp in sets if sp != "test_ood_layout")
        print(f"DECISION: {'SWITCH to ensemble' if win and ok else 'KEEP model 1'} (beats m1 on ood_layout: {win}; "
              f"no set below m1 by more than {MARGIN}: {ok}; sets evaluated: {', '.join(sets)})")
        print(f"if switching: tamper_mode: ensemble, tamper_threshold_ensemble: {thr['ensemble']:.4f}")


if __name__ == "__main__":
    main()
