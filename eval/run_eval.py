"""Stage E harness: every number on the deck comes from here. Appends rows to eval/results.csv.
  python -m eval.run_eval --demo data/demo --today 2026-10-26
Measures (all on SYNTHETIC data, label "measured"): field extraction accuracy per document type and layout, detection of
the injected problems in the demo applications (recall), unexpected findings, lane agreement, seconds per application.
OWNER: Aryan."""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import tempfile
import time
from datetime import date

from pramaan.classify_extract import classify_and_extract
from pramaan.ingest import ingest
from pramaan.model.eval_common import RESULT_COLS
from pramaan.pipeline import run_application
from pramaan.synth import content as C
from pramaan.synth import docs as D
from pramaan.util import norm_name


def extraction(n_inst: int, seed: int = 101):
    rows, per = [], {}
    with tempfile.TemporaryDirectory() as tmp:
        for k in range(n_inst):
            rng = random.Random(seed + k); inst = C.make_institute(rng); det = D.default_details(rng, inst)
            for dt in D.BUILDERS:
                for lay in D.LAYOUTS:
                    r = D.render_pdf(dt, lay, inst, det, os.path.join(tmp, f"{k}{dt}{lay}.pdf"))
                    d = classify_and_extract(ingest(r["path"], "x"))
                    s = per.setdefault((dt, lay), [0, 0, 0, 0])
                    s[2] += 1; s[3] += int(d.doc_type == dt)
                    for f, v in r["truth"].items():
                        got = d.fields[f].value if f in d.fields else None
                        s[0] += int(norm_name(str(got)) == norm_name(str(v))); s[1] += 1
    tot_ok = sum(v[0] for v in per.values()); tot = sum(v[1] for v in per.values())
    rows.append(dict(metric_id="extract.field_acc.all", metric="Field extraction accuracy (synthetic, " + f"{len(D.BUILDERS)} types x 3 layouts)",
                     value=round(tot_ok / tot, 4), unit="fraction", n=tot, set="synthetic_docs", label="measured"))
    rows.append(dict(metric_id="extract.type_acc.all", metric="Document type accuracy (synthetic)",
                     value=round(sum(v[3] for v in per.values()) / sum(v[2] for v in per.values()), 4), unit="fraction",
                     n=sum(v[2] for v in per.values()), set="synthetic_docs", label="measured"))
    for (dt, lay), v in sorted(per.items()):
        rows.append(dict(metric_id=f"extract.field_acc.{dt}.{lay}", metric=f"Field accuracy {dt} layout {lay}", value=round(v[0] / v[1], 4),
                         unit="fraction", n=v[1], set="synthetic_docs", label="measured"))
    return rows


def demo(demo_dir: str, today: date):
    truth = json.load(open(os.path.join(demo_dir, "truth.json")))
    hit = exp = extra = lane_ok = n = 0
    secs, detail = [], []
    with tempfile.TemporaryDirectory() as tmp:
        for app_id, t in truth["apps"].items():
            t0 = time.time()
            res = run_application(os.path.join(demo_dir, "apps", f"{app_id}.json"), tmp, today, os.path.join(tmp, "audit.db"))
            secs.append(time.time() - t0)
            got = [f.rule_id for f in res.findings]
            wanted = [e for e in t["expected_rules"] if not (e == "F-TAMPER" and not any(g == "F-TAMPER" for g in got) and t.get("needs_model"))]
            h = [e for e in wanted if any(g.startswith(e) for g in got)]
            hit += len(h); exp += len(wanted)
            ex = [g for g in got if not any(g.startswith(e) for e in t["expected_rules"])]
            extra += len(ex); n += 1; lane_ok += int(res.lane == t["expected_lane"])
            detail.append(f"{app_id}: missed {sorted(set(wanted) - set(h))} unexpected {ex} lane {res.lane}")
    rows = [dict(metric_id="demo.recall", metric="Injected problems found (demo applications)", value=round(hit / max(1, exp), 4),
                 unit="fraction", n=exp, set="demo_apps", label="measured"),
            dict(metric_id="demo.unexpected_findings", metric="Findings not matching an injected problem", value=extra, unit="count", n=n,
                 set="demo_apps", label="measured"),
            dict(metric_id="demo.lane_agreement", metric="Lane equals the designed lane", value=round(lane_ok / max(1, n), 4),
                 unit="fraction", n=n, set="demo_apps", label="measured"),
            dict(metric_id="demo.seconds_per_app", metric="Seconds per application (this laptop)", value=round(sum(secs) / max(1, n), 2),
                 unit="seconds", n=n, set="demo_apps", label="measured")]
    return rows, detail


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--demo", default="data/demo"); ap.add_argument("--today", default="2026-10-26")
    ap.add_argument("--n_inst", type=int, default=20); ap.add_argument("--out", default="eval/results.csv")
    a = ap.parse_args()
    rows = extraction(a.n_inst)
    r2, detail = demo(a.demo, date.fromisoformat(a.today))
    rows += r2
    for r in rows:
        r.update(source_file=a.out, notes=r.get("notes", "synthetic data; see eval/run_eval.py"))
    new = not os.path.exists(a.out)
    with open(a.out, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=RESULT_COLS)
        if new:
            w.writeheader()
        w.writerows(rows)
    for r in rows:
        if r["metric_id"].count(".") <= 2:
            print(f'{r["metric_id"]:32s} {r["value"]}  (n={r["n"]})')
    print("\n".join(detail))
