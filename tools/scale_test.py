"""Scale test: N synthetic applications (random mix of the demo scenario defects) through the full pipeline.
  python -m tools.scale_test --n 200 [--seed 7] [--today 2026-10-26] [--no-csv]
Writes everything under data/scale/ (git-ignored; own mock records, mock issuers and trust root, so data/demo is untouched).
Generation and the pipeline run in separate processes so peak memory (resource.ru_maxrss) is per phase.
Appends scale.* rows to eval/results.csv (label measured, set synthetic_scale_<N>). OWNER: Aryan."""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import random
import resource
import shutil
import subprocess
import sys
import time
from collections import Counter
from datetime import date

OUT = "data/scale"
STEPS = ("ingest", "classify_extract", "forensics", "verification", "rules", "crosscheck", "reuse", "photos", "report")
MACHINE = "machine = Aryan's M1 MacBook Air (MacBookAir10,1, 8 GB), CPU only"


def _peak_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return r / 2**20 if sys.platform == "darwin" else r / 1024       # macOS bytes, Linux KiB


def scenarios(n: int, seed: int):
    """Random mix of the demo scenarios; reuse defects copy from a random EARLIER app (reuse needs it processed first)."""
    from pramaan.synth.bundles import REUSE_FROM, SCENARIOS
    rng, pool = random.Random(seed), list(SCENARIOS.values())
    reuse_defects = {SCENARIOS[a][0][0] for a in REUSE_FROM}
    sc, src = {}, {}
    for i in range(n):
        app_id = f"S-{i + 1:04d}"
        defects, expect, lane = rng.choice(pool)
        if reuse_defects & set(defects):
            if not sc:
                defects, expect, lane = SCENARIOS["APP-01"]
            else:
                src[app_id] = rng.choice(list(sc))
        sc[app_id] = (defects, expect, lane)
    return sc, src


def gen(n: int, seed: int, today: date) -> dict:
    from pramaan.synth import bundles
    shutil.rmtree(OUT, ignore_errors=True)
    sc, src = scenarios(n, seed)
    t = time.perf_counter()
    bundles.build(OUT, today, seed, scenarios=sc, data_dir=OUT, root_copy=f"{OUT}/trust/scale_root.pem", reuse_from=src)
    return {"gen_seconds": time.perf_counter() - t, "gen_peak_mb": _peak_mb()}


def run(today: date) -> dict:
    import numpy as np
    from pramaan import issuer
    from pramaan.pipeline import run_application
    issuer.MOCK_DIR = f"{OUT}/mock_issuers"                    # scale mock issuers, not the demo ones
    out_dir = f"{OUT}/output"
    shutil.rmtree(out_dir, ignore_errors=True)
    secs, steps, lanes = [], [], Counter()
    t0 = time.perf_counter()
    for m in sorted(glob.glob(f"{OUT}/apps/*.json")):
        tm: dict = {}
        t = time.perf_counter()
        r = run_application(m, out_dir, today, f"{out_dir}/audit.db", records_path=f"{OUT}/aicte_records.json",
                            trust_dir=f"{OUT}/trust", timings=tm)
        secs.append(time.perf_counter() - t); steps.append(tm); lanes[r.lane] += 1
    wall = time.perf_counter() - t0
    return {"n": len(secs), "wall_seconds": wall, "apps_per_minute": 60 * len(secs) / wall, "mean_s": float(np.mean(secs)),
            "p95_s": float(np.percentile(secs, 95)), "steps": {s: float(np.mean([x.get(s, 0.0) for x in steps])) for s in STEPS},
            "lanes": dict(lanes), "run_peak_mb": _peak_mb()}


def rows(n: int, g: dict, r: dict) -> list[dict]:
    st, notes = f"synthetic_scale_{n}", f"{MACHINE}; Python {sys.version.split()[0]}; no tamper weights"
    def row(mid, metric, value, unit, extra=""):
        return dict(metric_id=f"scale.{mid}", metric=metric, value=round(value, 4) if isinstance(value, float) else value, unit=unit,
                    n=r["n"], set=st, label="measured", source_file="tools/scale_test.py", notes=notes + extra)
    out = [row("gen_seconds", "Generation time (synthetic docs, signing, photos)", g["gen_seconds"], "seconds"),
           row("wall_seconds", "Pipeline wall time, all applications", r["wall_seconds"], "seconds"),
           row("apps_per_minute", "Applications per minute (pipeline)", r["apps_per_minute"], "apps/min"),
           row("mean_seconds_per_app", "Mean seconds per application", r["mean_s"], "seconds"),
           row("p95_seconds_per_app", "p95 seconds per application", r["p95_s"], "seconds"),
           row("peak_mem_mb.pipeline", "Peak memory, pipeline process", r["run_peak_mb"], "MB", "; ru_maxrss"),
           row("peak_mem_mb.generation", "Peak memory, generation process", g["gen_peak_mb"], "MB", "; ru_maxrss")]
    out += [row(f"step_seconds.{s}", f"Mean seconds per application in step {s}", v, "seconds") for s, v in r["steps"].items()]
    out += [row(f"lanes.{k}", f"Applications in lane {k}", v, "count") for k, v in sorted(r["lanes"].items())]
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=200); ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--today", default="2026-10-26"); ap.add_argument("--no-csv", action="store_true")
    ap.add_argument("--phase", choices=["gen", "run"], default=None, help=argparse.SUPPRESS)
    a = ap.parse_args()
    td = date.fromisoformat(a.today)
    if a.phase:
        print("RESULT " + json.dumps(gen(a.n, a.seed, td) if a.phase == "gen" else run(td)))
        sys.exit(0)
    res = {}
    for ph in ("gen", "run"):
        p = subprocess.run([sys.executable, "-m", "tools.scale_test", "--phase", ph, "--n", str(a.n), "--seed", str(a.seed),
                            "--today", a.today], capture_output=True, text=True)
        line = next((ln for ln in p.stdout.splitlines() if ln.startswith("RESULT ")), None)
        if line is None:
            sys.exit(f"phase {ph} failed:\n{p.stderr[-2000:]}")
        res[ph] = json.loads(line[7:])
    rs = rows(a.n, res["gen"], res["run"])
    if not a.no_csv:
        from pramaan.model.eval_common import RESULT_COLS
        with open("eval/results.csv", "a", newline="") as f:
            csv.DictWriter(f, fieldnames=RESULT_COLS).writerows(rs)
    for r in rs:
        print(f'{r["metric_id"]:38s} {r["value"]}')
