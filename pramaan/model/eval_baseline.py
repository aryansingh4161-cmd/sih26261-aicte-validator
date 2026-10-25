"""Run the non-learned ELA baseline on a dataset.  python -m pramaan.model.eval_baseline --data data/synthetic/v1 [--n_max 100]
Appends to eval/results.csv. OWNER: Manviraj."""
import argparse

from . import baseline as B
from .eval_common import evaluate

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", default="eval/results.csv")
    ap.add_argument("--n_max", type=int, default=None)
    a = ap.parse_args()
    evaluate("ela_baseline", B.score, a.data, B.predict_mask, a.out, a.n_max)
