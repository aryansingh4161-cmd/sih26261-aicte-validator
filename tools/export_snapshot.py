"""Static snapshot of the 23 SYNTHETIC demo cases for the web app's demo mode (WK26): no backend needed.
  python -m tools.export_snapshot [--out web/public/snapshot] [--langs en,hi,bn,ta,mr] [--today 2026-10-27]
Runs the pipeline on data/demo/apps into a fresh temporary folder, records a few officer actions (a sealed Letter of
Deficiency for APP-02, an assignment, a note, one feedback mark) so the screens are not empty, then writes every API view as
JSON: <out>/<lang>/<path>.json (path = the API path without /api/, e.g. cases/APP-07/checklist) plus page images, heatmaps and
photos once under <out>/img/. The web app's demo adapter reads exactly these files. Synthetic data only."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import tempfile
from datetime import date


def write(base: str, lang: str, path: str, obj) -> None:
    p = os.path.join(base, lang, path + ".json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"), default=str)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="web/public/snapshot"); ap.add_argument("--langs", default="en,hi,bn,ta,mr")
    ap.add_argument("--today", default="2026-10-27")
    a = ap.parse_args()
    work = tempfile.mkdtemp(prefix="pramaan_snapshot_")
    os.environ.update({"PRAMAAN_OUT": work, "PRAMAAN_TODAY": a.today, "PRAMAAN_OUTBOX": os.path.join(work, "outbox")})
    from pramaan.pipeline import run_application
    from api import actions, views_case as C, views_case2 as C2, views_global as G
    from api.ctx import ROLES, Ctx
    from api.images import page
    today = date.fromisoformat(a.today)
    ids = [f"APP-{k:02d}" for k in range(1, 24)]
    for app_id in ids:
        run_application(f"data/demo/apps/{app_id}.json", work, today, os.path.join(work, "audit.db"), reuse_db=os.path.join(work, "reuse.db"))
    c0 = Ctx(out=work, today=today)
    actions.assign(c0, "APP-07", "officer.se")
    actions.note(c0, "APP-07", "@officer.se did they apply for renewal before the expiry date?")
    actions.seal_issue(c0, "APP-02")
    first = C.case(c0, "APP-17")["findings"]
    if first:
        actions.feedback(c0, "APP-17", first[-1]["finding_id"], "false alarm", "weak signal on its own")
    if os.path.exists(a.out):
        shutil.rmtree(a.out)
    img = os.path.join(a.out, "img")
    for lang in a.langs.split(","):
        c = Ctx(out=work, today=today, lang=lang)
        for role in ROLES:
            write(a.out, lang, f"queue/{role}", C.queue(Ctx(out=work, today=today, lang=lang, role=role)))
            write(a.out, lang, f"analytics/{role}", G.analytics(Ctx(out=work, today=today, lang=lang, role=role)))
        for app_id in ids:
            write(a.out, lang, f"cases/{app_id}", C.case(c, app_id))
            write(a.out, lang, f"cases/{app_id}/checklist", C.checklist(c, app_id))
            src = C2.sources(c, app_id)
            write(a.out, lang, f"cases/{app_id}/sources", src)
            for row in src["rows"]:
                if row["preview"]:
                    write(a.out, lang, f"cases/{app_id}/sources/{row['id']}/preview", C2.preview(c, app_id, row["id"]))
            write(a.out, lang, f"cases/{app_id}/changes", C2.changes(c, app_id))
            write(a.out, lang, f"cases/{app_id}/resubmission", C2.resubmission(c, app_id))
            write(a.out, lang, f"cases/{app_id}/letter", C2.letter_draft(c, app_id))
            write(a.out, lang, f"cases/{app_id}/evc", G.evc(Ctx(out=work, today=today, lang=lang, role="evc"), app_id))
            from pramaan.notes import list_notes
            write(a.out, lang, f"cases/{app_id}/notes", list_notes(c.db, app_id))
        for name, fn in (("letters", G.letters), ("outbox", G.outbox), ("calendar", G.calendar), ("appeals", G.appeals), ("batch", G.batch)):
            write(a.out, lang, name, fn(c))
        write(a.out, lang, "search/_all", G.search(c, ""))
        write(a.out, lang, "roles", [{"id": k, "name": c.tr(v["name"])} for k, v in ROLES.items()])
        print(f"{lang}: views written", flush=True)
    for name in ("privacy", "terms", "accessibility"):
        write(a.out, "en", f"docs/{name}", G.policy(c0, name))
    n = 0
    for app_id in ids:
        r = c0.result(app_id)
        for d in r.documents:
            for k in range(1, max(1, d.pages) + 1):
                im = page(c0, app_id, d.doc_id, k)
                if im is not None:
                    p = os.path.join(img, "documents", app_id, d.doc_id, "page", f"{k}.png")
                    os.makedirs(os.path.dirname(p), exist_ok=True); im.save(p, optimize=True); n += 1
                h = os.path.join(work, "heatmaps", f"{d.doc_id}_p{k}.png")
                if os.path.exists(h):
                    p = os.path.join(img, "documents", app_id, d.doc_id, "heatmap", f"{k}.png")
                    os.makedirs(os.path.dirname(p), exist_ok=True); shutil.copy(h, p)
        for ph in c0.manifest(app_id).get("photos", []):
            p = os.path.join(img, "photos", app_id, os.path.basename(ph))
            os.makedirs(os.path.dirname(p), exist_ok=True)
            from PIL import Image
            im = Image.open(ph).convert("RGB"); im.thumbnail((720, 720)); im.save(p, quality=78, optimize=True)   # display copy
    letters = os.path.join(a.out, "letters"); os.makedirs(letters, exist_ok=True)
    for f in os.listdir(os.path.join(work, "letters")):
        shutil.copy(os.path.join(work, "letters", f), letters)
    json.dump({"today": a.today, "langs": a.langs.split(","), "cases": len(ids), "pages": n, "synthetic": True},
              open(os.path.join(a.out, "meta.json"), "w"))
    print(f"snapshot: {len(ids)} cases, {n} page images -> {a.out}")


if __name__ == "__main__":
    main()
