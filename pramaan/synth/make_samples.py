"""Make 5 sample PDFs (one per document type) into data/samples/.  Run: python -m pramaan.synth.make_samples"""
import os, random
from pramaan.synth import content as C, docs as D


def main(out="data/samples", seed=3):
    rng = random.Random(seed)
    inst = C.make_institute(rng)
    det = D.default_details(rng, inst)
    os.makedirs(out, exist_ok=True)
    for dt in D.BUILDERS:
        r = D.render_pdf(dt, "A", inst, det, os.path.join(out, f"{dt}.pdf"))
        print(dt, "->", r["path"], "| truth:", r["truth"])


if __name__ == "__main__":
    main()
