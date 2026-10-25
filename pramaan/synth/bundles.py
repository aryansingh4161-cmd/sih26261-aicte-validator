"""Demo applications with KNOWN injected problems (all synthetic). Writes:
  data/demo/apps/APP-xx.json (manifests), data/demo/docs/..., data/demo/photos/..., data/demo/truth.json,
  data/aicte_records.json (MOCK AICTE records), data/mock_issuers/fire.json, university.json, config/trust/demo_root.pem
Run:  python -m pramaan.synth.bundles --out data/demo --today 2026-10-26      OWNER: Manviraj / Aryan."""
from __future__ import annotations

import argparse
import copy
import json
import os
import random
from datetime import date, datetime, timedelta

from PIL import Image

from . import content as C
from . import docs as D
from .demo_pki import can_sign, make_pki, sign_pdf
from .pdf_edit import incremental_text_edit
from .photos import edit_photo as _edit_photo, photo as _photo
from .raster import jpeg_roundtrip, render_page, scan_effect
from .tamper import apply_tamper

# app id -> (defects, expected rule_id prefixes, expected lane). R-SIG is expected everywhere if signing is unavailable.
SCENARIOS = {
    "APP-01": ([], [], "clear"),
    "APP-02": (["missing_fire"], ["R-MISS-fire_cert"], "return_for_rectification"),
    "APP-03": (["expired_fire"], ["R-EXP-fire_cert"], "return_for_rectification"),
    "APP-04": (["struct_short_validity"], ["R-EXP-structural_cert"], "return_for_rectification"),
    "APP-05": (["struct_missing_old_building"], ["R-MISS-structural_cert"], "return_for_rectification"),
    "APP-06": (["edited_fire_pdf"], ["F-PDF-FONT-MIX", "V-issuer_portal"], "human_review"),
    "APP-07": (["name_mismatch", "intake_mismatch"], ["X-NAME", "X-INTAKE", "V-issuer_portal"], "human_review"),
    "APP-08": (["eoa_other_institute", "fee_unpaid"], ["X-PERMID", "R-REC-ter_paid"], "human_review"),
    "APP-09": (["photo_far", "photo_duplicate"], ["F-PHOTO-GPS", "F-PHOTO-DUPLICATE"], "human_review"),
    "APP-10": (["stamp_50", "sworn_after_submit"], ["R-FLD-affidavit_2-stamp_value", "X-SWORN-AFTER-SUBMIT", "F-META-DATES"], "human_review"),
    "APP-11": (["fire_not_in_issuer_db"], [], "clear"),
    "APP-12": (["scanned_struct_tampered"], ["F-TAMPER"], "human_review"),
    # F8 reuse across applications: needs the source app processed first (sorted order does that)
    "APP-13": (["photo_reused_from_app09"], ["X-REUSE-PHOTO"], "human_review"),
    "APP-14": (["fire_no_reused_from_app03"], ["X-REUSE-CERT", "V-issuer_portal"], "human_review"),
    # F9: one room type below its per-room minimum (classroom, or the first norm row); expected rule set in build()
    "APP-15": (["area_below_norm"], ["R-AREA-classroom"], "return_for_rectification"),
    # WK14 metadata forensics: an incremental update that rewrote the validity date; a photo edited in software
    "APP-16": (["fire_incremental_edit"], ["F-META-REVISION-DIFF", "F-PDF-INCREMENTAL", "F-PDF-MODDATE", "V-issuer_portal"], "human_review"),
    "APP-17": (["photo_edited_software"], ["F-META-EXIF-SOFTWARE", "F-META-EXIF-THUMB", "F-META-EXIF-DATES", "F-META-JPEG-QT"],
               "human_review"),
}


def _sidecar_from_pdf(pdf_path, img_path):
    """MOCKED OCR: writes the generator's own text lines as an OCR sidecar (real OCR is a separate step)."""
    import pdfplumber
    with pdfplumber.open(pdf_path) as pdf:
        p = pdf.pages[0]; W, H = float(p.width), float(p.height)
        items = [{"page": 1, "text": l["text"], "bbox": [l["x0"] / W, l["top"] / H, l["x1"] / W, l["bottom"] / H], "conf": 0.9}
                 for l in p.extract_text_lines()]
    with open(img_path + ".ocr.json", "w") as f:
        json.dump(items, f)


REUSE_FROM = {"APP-13": "APP-09", "APP-14": "APP-03"}     # reuse defect -> the earlier app it copies from


def build(out: str, today: date, seed: int = 11, scenarios: dict | None = None, data_dir: str = "data",
          root_copy: str = "config/trust/demo_root.pem", reuse_from: dict | None = None) -> dict:
    """Defaults = the demo set. tools/scale_test.py passes its own scenarios / data_dir / root_copy so the demo is untouched."""
    scenarios, reuse_from = scenarios or SCENARIOS, reuse_from or REUSE_FROM
    rng = random.Random(seed)
    os.makedirs(os.path.join(out, "apps"), exist_ok=True)
    records, fire_db, uni_db, truth = {}, {}, {}, {}
    shared = {}                                         # values later apps reuse (F8)
    signing = can_sign()
    pki = make_pki(os.path.join(out, "pki"), root_copy=root_copy) if signing else None
    ay0 = today.year if today.month >= 7 else today.year - 1
    ay0 = ay0 + 1                                       # applications are for the NEXT academic year
    for app_id, (defects, expect, lane) in scenarios.items():
        r = random.Random(f"{seed}-{app_id}")
        inst = C.make_institute(r, ay0)
        if "struct_missing_old_building" in defects or "struct_short_validity" in defects or "scanned_struct_tampered" in defects:
            inst["building_completion_date"] = date(r.randint(1980, 1992), 6, 1).isoformat()
        prev = copy.deepcopy(inst); prev["academic_year"] = inst["prev_academic_year"]; prev["prev_academic_year"] = f"{ay0 - 2}-{str(ay0 - 1)[-2:]}"
        prev["application_id"] = f"1-{r.randint(10000000000, 99999999999)}"     # last year's application had its own id
        det = D.default_details(r, inst); pdet = D.default_details(r, prev)
        det["issue_date"] = today - timedelta(days=r.randint(200, 500)); det["valid_until"] = det["issue_date"] + timedelta(days=365 * 3)
        submitted = today - timedelta(days=r.randint(5, 20))
        det["sworn_on"] = submitted - timedelta(days=r.randint(3, 30))
        det["noc_date"] = submitted - timedelta(days=r.randint(20, 60))
        sdet = dict(det)                                  # structural certificate has its own dates
        sdet["issue_date"] = today - timedelta(days=r.randint(200, 600))
        layout = r.choice("ABC")
        ddir = os.path.join(out, "docs", app_id); os.makedirs(ddir, exist_ok=True)
        docs = {}
        def render(dt, i=inst, d=det, lay=layout, **kw):
            p = os.path.join(ddir, f"{dt}.pdf"); D.render_pdf(dt, lay, i, d, p, **kw); docs[dt] = p; return p
        render("eoa_letter", prev, pdet, producer="Oracle BI Publisher 11.1.1.9.0 (synthetic)")
        aff_inst = inst
        if "stamp_50" in defects:
            det["stamp_value"] = "50"
        if "sworn_after_submit" in defects:
            det["sworn_on"] = submitted + timedelta(days=2)
        render("affidavit_2", aff_inst)
        noc_det = det
        if "intake_mismatch" in defects:
            noc_det = dict(det); noc_det["noc_programs"] = [dict(p) for p in det["noc_programs"]]
            noc_det["noc_programs"][0]["intake_curr"] = str(int(noc_det["noc_programs"][0]["intake_curr"]) + 60)
        render("noc_format2", inst, noc_det)
        if "area_below_norm" in defects:
            det["areas"] = [dict(a) for a in det["areas"]]
            low = next((a for a in det["areas"] if a["room_type"] == "Classroom"), det["areas"][0])
            low["area_sqm"] = round(low["area_sqm"] * 0.8 / 1.2)      # generated at 1.05-1.35 x norm -> now 0.70-0.90 x norm
            expect = [f"R-AREA-{low['room_type'].lower().replace(' ', '_')}"]
        render("area_statement", inst, det)
        real_valid = det["valid_until"]
        if "expired_fire" in defects:
            det["issue_date"] = today - timedelta(days=365 * 3 + 40); det["valid_until"] = today - timedelta(days=40); real_valid = det["valid_until"]
        shared.setdefault(app_id, {}).update(fire_no=det["fire_no"], fire_auth=det["fire_auth"])
        if "fire_no_reused_from_app03" in defects:                  # a copied certificate keeps its number AND issuer
            det["fire_no"], det["fire_auth"] = shared[reuse_from[app_id]]["fire_no"], shared[reuse_from[app_id]]["fire_auth"]
        fire_inst = inst
        if "name_mismatch" in defects:
            fire_inst = dict(inst); fire_inst["institute_name"] = inst["institute_name"].split()[0] + " Global Academy"
        if "edited_fire_pdf" in defects:
            real_valid = today - timedelta(days=25)
            det["issue_date"] = real_valid - timedelta(days=365 * 3)
            det["valid_until"] = today + timedelta(days=700)      # the forger pushed the date out
            render("fire_cert", fire_inst, det, producer="Generic PDF Editor 9.1 (synthetic)",
                   font_override={"valid_until": "Times-Roman" if layout != "B" else "Helvetica"})
        elif "fire_incremental_edit" in defects:                 # issued with the true (expired) date, edited AFTER saving
            real_valid = today - timedelta(days=25)
            det["issue_date"] = real_valid - timedelta(days=365 * 3); det["valid_until"] = real_valid
            fp = render("fire_cert", fire_inst, det)
            incremental_text_edit(fp, C.fmt_dmy(real_valid), C.fmt_dmy(today + timedelta(days=700)),
                                  datetime.combine(submitted - timedelta(days=3), datetime.min.time()).replace(hour=11))
        elif "missing_fire" not in defects:
            render("fire_cert", fire_inst)
        if "struct_short_validity" in defects:
            sdet["issue_date"] = today - timedelta(days=365 * 4); sdet["validity_years"] = 3
        if "struct_missing_old_building" not in defects:
            p = render("structural_cert", inst, sdet)
            if "scanned_struct_tampered" in defects:
                img = jpeg_roundtrip(scan_effect(render_page(p, dpi=100), r, 1.0), 85)
                info = D.render_pdf("structural_cert", layout, inst, sdet, p)
                W, H = img.size
                b = next(b for b in info["boxes"] if b["field"] == "issue_date")
                box = (int(b["bbox"][0] * W), int(b["bbox"][1] * H), int(b["bbox"][2] * W) + 1, int(b["bbox"][3] * H) + 1)
                img, _ = apply_tamper(img, "replace_digits", box, b["text"], r)
                jp = os.path.join(ddir, "structural_cert_scan.jpg"); img.save(jp, quality=88)
                _sidecar_from_pdf(p, jp); os.remove(p); docs["structural_cert"] = jp
        if signing and "affidavit_2" in docs:
            sign_pdf(docs["affidavit_2"], docs["affidavit_2"], pki,
                     when=datetime.combine(det["sworn_on"], datetime.min.time()).replace(hour=12).astimezone())
        if "fire_cert" in docs and not {"fire_not_in_issuer_db", "fire_no_reused_from_app03"} & set(defects):
            fire_db[det["fire_no"]] = {"valid_until": real_valid.isoformat(), "institute_name": inst["institute_name"]}
        uni_db[det["noc_ref"]] = {"institute_name": inst["institute_name"]}
        pid = inst["permanent_id"]
        if "eoa_other_institute" in defects:
            other = C.make_institute(random.Random(f"other-{app_id}"), ay0 - 1)
            prev2 = copy.deepcopy(prev); prev2["permanent_id"] = other["permanent_id"]
            render("eoa_letter", prev2, pdet, producer="Oracle BI Publisher 11.1.1.9.0 (synthetic)")
        records[pid] = {"institute_name": inst["institute_name"], "trust_name": inst["trust_name"], "address": inst["address"],
                        "building_completion_date": inst["building_completion_date"], "latitude": inst["latitude"],
                        "longitude": inst["longitude"], "ter_paid": "fee_unpaid" not in defects, "last_eoa_year": prev["academic_year"],
                        "approved_programs": [{"course": p["course"], "intake_prev": p["intake_curr"]} for p in inst["programs"]]}
        pdir = os.path.join(out, "photos", app_id); os.makedirs(pdir, exist_ok=True)
        photos = []
        for k in range(2):
            lat, lon = inst["latitude"] + r.uniform(-0.002, 0.002), inst["longitude"] + r.uniform(-0.002, 0.002)
            if "photo_far" in defects and k == 0:
                lat += 0.45
            pp = os.path.join(pdir, f"campus_{k + 1}.jpg"); photos.append(pp)
            im = _photo(pp, r, lat, lon, taken=datetime.combine(submitted - timedelta(days=10 + k), datetime.min.time()).replace(hour=10))
        shared[app_id]["photo"] = photos[0]
        if "photo_reused_from_app09" in defects:            # same picture, re-tagged with this campus GPS
            _photo(photos[0], r, inst["latitude"], inst["longitude"], seed_img=Image.open(shared[reuse_from[app_id]]["photo"]).copy())
        if "photo_edited_software" in defects:
            _edit_photo(photos[0], datetime.combine(submitted - timedelta(days=10), datetime.min.time()).replace(hour=10))
        if "photo_duplicate" in defects:
            pp = os.path.join(pdir, "campus_3.jpg"); _photo(pp, r, inst["latitude"], inst["longitude"], seed_img=Image.open(photos[1]).copy()); photos.append(pp)
        man = {"app_id": app_id, "category": "eoa_existing_regular", "academic_year": inst["academic_year"], "permanent_id": pid,
               "submitted_on": submitted.isoformat(), "declared": {"institute_name": inst["institute_name"], "latitude": inst["latitude"],
               "longitude": inst["longitude"]}, "documents": [{"slot": k, "path": v} for k, v in docs.items()], "photos": photos}
        with open(os.path.join(out, "apps", f"{app_id}.json"), "w") as f:
            json.dump(man, f, indent=2)
        truth[app_id] = {"defects": defects, "expected_rules": expect + ([] if signing else ["R-SIG-affidavit_2"]),
                         "expected_lane": lane if signing or lane != "clear" else "return_for_rectification", "layout": layout,
                         "needs_model": "scanned_struct_tampered" in defects}
    os.makedirs(os.path.join(data_dir, "mock_issuers"), exist_ok=True)
    json.dump(records, open(os.path.join(data_dir, "aicte_records.json"), "w"), indent=2)
    json.dump(fire_db, open(os.path.join(data_dir, "mock_issuers", "fire.json"), "w"), indent=2)
    json.dump(uni_db, open(os.path.join(data_dir, "mock_issuers", "university.json"), "w"), indent=2)
    json.dump({"today": today.isoformat(), "signed_affidavits": signing, "apps": truth}, open(os.path.join(out, "truth.json"), "w"), indent=2)
    return truth


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/demo"); ap.add_argument("--today", default="2026-10-26"); ap.add_argument("--seed", type=int, default=11)
    a = ap.parse_args()
    t = build(a.out, date.fromisoformat(a.today), a.seed)
    print(f"wrote {len(t)} demo applications to {a.out}/apps; signed affidavits: {can_sign()} (needs pyHanko)")
