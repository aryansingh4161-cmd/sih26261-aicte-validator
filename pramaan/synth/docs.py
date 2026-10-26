"""Render FAKE documents as PDFs with reportlab. Returns ground truth (fields, tables) and the boxes of every
number/date that a forger could change (used by tamper.py). OWNER: Manviraj.

Three LAYOUTS (A, B, C) per document type: same facts, different fonts/positions/lines so that a model can be tested
on a layout it never saw during training."""
from __future__ import annotations

import os
import random
from datetime import date, datetime, timedelta, timezone
from typing import Dict, List, Optional

from reportlab.lib.colors import Color, black, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

from . import content as C

PAGE_W, PAGE_H = A4
LAYOUTS = ("A", "B", "C")
DOC_TYPES = ("eoa_letter", "affidavit_2", "noc_format2", "fire_cert", "structural_cert")

STYLES = {
    "A": dict(font="Helvetica", bold="Helvetica-Bold", size=10, margin=55, top=60, title_align="center", grid=True,
              inline=False, leading=15, header_fill=0.92, border=False),
    "B": dict(font="Times-Roman", bold="Times-Bold", size=11, margin=72, top=70, title_align="left", grid=False,
              inline=True, leading=17, header_fill=1.0, border=False),
    "C": dict(font="Courier", bold="Courier-Bold", size=9.5, margin=42, top=48, title_align="center", grid=True,
              inline=False, leading=14, header_fill=0.82, border=True),
}


class Painter:
    def __init__(self, path: str, layout: str, producer: str):
        self.s = STYLES[layout]
        self.c = canvas.Canvas(path, pagesize=A4)
        self.c.setProducer(producer)
        self.c.setCreator(producer)
        self.c.setTitle("SYNTHETIC SAMPLE")
        self.c.setAuthor("synthetic generator")
        self.x0 = self.s["margin"]
        self.x1 = PAGE_W - self.s["margin"]
        self.y = PAGE_H - self.s["top"]
        self.boxes: List[Dict] = []
        self.font_override: Dict[str, str] = {}      # field -> font name (used to simulate an edited field)
        if self.s["border"]:
            self.c.setLineWidth(1.2)
            self.c.rect(24, 24, PAGE_W - 48, PAGE_H - 48)

    # -- low level -------------------------------------------------------------------------------------------
    def put(self, x, y, s, bold=False, size=None, field: Optional[str] = None) -> float:
        f = self.s["bold"] if bold else self.s["font"]
        if field and field in self.font_override:
            f = self.font_override[field]
        sz = size or self.s["size"]
        self.c.setFont(f, sz)
        self.c.drawString(x, y, s)
        w = stringWidth(s, f, sz)
        if field:
            self.boxes.append({"field": field, "text": s, "digits": any(ch.isdigit() for ch in s),
                               "x0": x, "y0": y - sz * 0.25, "x1": x + w, "y1": y + sz * 0.80})
        return w

    def wrap(self, text: str, width: float, bold=False, size=None) -> List[str]:
        f = self.s["bold"] if bold else self.s["font"]
        sz = size or self.s["size"]
        words, lines, cur = text.split(), [], ""
        for w in words:
            t = (cur + " " + w).strip()
            if stringWidth(t, f, sz) <= width:
                cur = t
            else:
                lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    # -- blocks ----------------------------------------------------------------------------------------------
    def title(self, text, size=14):
        f, sz = self.s["bold"], size
        w = stringWidth(text, f, sz)
        x = (PAGE_W - w) / 2 if self.s["title_align"] == "center" else self.x0
        self.put(x, self.y, text, bold=True, size=sz)
        self.y -= sz + 8

    def rule(self):
        self.c.setLineWidth(0.6)
        self.c.line(self.x0, self.y + 4, self.x1, self.y + 4)
        self.y -= 8

    def para(self, text, bold=False, field_words: Optional[Dict[str, str]] = None):
        for ln in self.wrap(text, self.x1 - self.x0, bold):
            self.put(self.x0, self.y, ln, bold=bold)
            self.y -= self.s["leading"]
        self.y -= 4

    def pair(self, left, right, lf=None, rf=None):
        """Two items on one line: left aligned and right aligned."""
        self.put(self.x0, self.y, left, field=lf)
        w = stringWidth(right, self.s["font"], self.s["size"])
        self.put(self.x1 - w, self.y, right, field=rf)
        self.y -= self.s["leading"]

    def kv(self, label, value, field=None):
        lead = self.s["leading"]
        if self.s["inline"]:
            w = self.put(self.x0, self.y, label + ":", bold=True)
            self.put(self.x0 + max(w + 8, 170), self.y, value, field=field)
            self.y -= lead
        else:
            self.put(self.x0, self.y, label, bold=True)
            self.y -= lead
            for ln in self.wrap(value, self.x1 - self.x0 - 10):
                self.put(self.x0 + 10, self.y, ln, field=field)
                self.y -= lead
            self.y -= 2

    def table(self, headers: List[str], rows: List[List[str]], widths: List[float], fields: Optional[List[List[Optional[str]]]] = None):
        total = self.x1 - self.x0
        xs = [self.x0]
        for w in widths:
            xs.append(xs[-1] + total * w)
        sz = self.s["size"] - 1
        line_h = sz + 1.5

        def cell_lines(txt, i, bold=False):
            return self.wrap(txt, total * widths[i] - 8, bold=bold, size=sz)[:4]

        h_lines = [cell_lines(h, i, True) for i, h in enumerate(headers)]
        h_rh = max(len(x) for x in h_lines) * line_h + 8
        top = self.y
        if self.s["header_fill"] < 1.0:
            self.c.setFillColor(Color(self.s["header_fill"], self.s["header_fill"], self.s["header_fill"]))
            self.c.rect(self.x0, top - h_rh, total, h_rh, stroke=0, fill=1)
            self.c.setFillColor(black)
        for i, lines in enumerate(h_lines):
            for k, ln in enumerate(lines):
                self.put(xs[i] + 4, top - 10 - k * line_h, ln, bold=True, size=sz)
        y = top - h_rh
        ys = [top, y]
        for r, row in enumerate(rows):
            cl = [cell_lines(cell, i) for i, cell in enumerate(row)]
            rh = max(len(x) for x in cl) * line_h + 8
            for i, lines in enumerate(cl):
                fld = fields[r][i] if fields and fields[r][i] else None
                for k, ln in enumerate(lines):
                    self.put(xs[i] + 4, y - 10 - k * line_h, ln, size=sz, field=fld if k == 0 else None)
            y -= rh
            ys.append(y)
        bottom = y
        self.c.setLineWidth(0.6)
        if self.s["grid"]:
            for yy in ys:
                self.c.line(self.x0, yy, self.x1, yy)
            for x in xs:
                self.c.line(x, top, x, bottom)
        else:
            for yy in (ys[0], ys[1], ys[-1]):
                self.c.line(self.x0, yy, self.x1, yy)
        self.y = bottom - 14

    def qr(self, payload: str, x: float, y: float, size: float = 70):
        from reportlab.graphics import renderPDF
        from reportlab.graphics.barcode.qr import QrCodeWidget
        from reportlab.graphics.shapes import Drawing
        w = QrCodeWidget(payload)
        b = w.getBounds()
        d = Drawing(size, size, transform=[size / (b[2] - b[0]), 0, 0, size / (b[3] - b[1]), 0, 0])
        d.add(w)
        renderPDF.draw(d, self.c, x, y)

    def finish(self, footer_extra: str = ""):
        self.c.setFont(self.s["font"], 8)
        self.c.drawCentredString(PAGE_W / 2, 30, ("SYNTHETIC SAMPLE " + footer_extra).strip())
        self.c.save()

    def norm_boxes(self) -> List[Dict]:
        out = []
        for b in self.boxes:
            out.append({"field": b["field"], "text": b["text"], "digits": b["digits"],
                        "bbox": [b["x0"] / PAGE_W, 1 - b["y1"] / PAGE_H, b["x1"] / PAGE_W, 1 - b["y0"] / PAGE_H]})
        return out


# ---------------------------------------------------------------------------------------------------------------
# document builders. Each returns (truth_fields, truth_tables)
# ---------------------------------------------------------------------------------------------------------------
def _eoa(P: Painter, inst: Dict, d: Dict, layout: str):
    ay = inst["academic_year"]
    P.title("EXAMPLE COUNCIL FOR TECHNICAL EDUCATION (SYNTHETIC)", 13)
    P.title(f"APPROVAL PROCESS {ay} - Extension of Approval (EoA)", 11)
    year = ay[:4]
    fno = f"{inst['region']}/{inst['application_id']}/{year}/EOA"
    appr = d["approval_date"]
    P.pair(f"F.No. {fno}", f"Date of Approval: {C.fmt_dMy(appr)}", "file_no", "approval_date")
    P.y -= 4
    P.para(f"Sub: Extension of Approval for the Academic Year {ay}")
    P.pair(f"Permanent Id {inst['permanent_id']}", f"Application Id {inst['application_id']}", "permanent_id", "application_id")
    P.y -= 4
    P.kv("Name of the Institution", inst["institute_name"], "institute_name")
    P.kv("Institution Address", inst["address"])
    P.kv("Name of the Society/Trust", inst["trust_name"])
    P.para(f"To conduct following Programs/Courses with the Intake indicated below for the Academic Year {ay}")
    headers = ["Level", "Program", "Course", "Affiliating Body (University /Body)",
               f"Intake Approved for {inst['prev_academic_year']}", f"Intake Approved for {ay}"]
    rows, flds = [], []
    for i, p in enumerate(inst["programs"]):
        rows.append([p["level"], p["program"], p["course"], inst["university"], p["intake_prev"], p["intake_curr"]])
        flds.append([None, None, None, None, f"intake_prev_{i}", f"intake_curr_{i}"])
    P.table(headers, rows, [0.13, 0.17, 0.26, 0.16, 0.14, 0.14], flds)
    P.para("Note: Validity of the Course details may be verified at the official council website.")
    P.y = 70
    P.put(P.x0, P.y, f"Application No:{inst['application_id']} EXAMPLE COUNCIL Page 1 of 1 Note: This is a Computer generated Report. No signature is required.", size=7)
    P.y -= 10
    P.put(P.x0, P.y, f"Printed By : {inst['user_id']} Letter Printed On:{C.fmt_long(d['printed_on'])}", size=7, field="printed_on")
    truth = {"file_no": fno, "approval_date": appr.isoformat(), "permanent_id": inst["permanent_id"],
             "application_id": inst["application_id"], "institute_name": inst["institute_name"], "academic_year": ay,
             "printed_on": d["printed_on"].isoformat()}
    tables = {"programs": [{"course": p["course"], "intake_prev": p["intake_prev"], "intake_curr": p["intake_curr"]} for p in inst["programs"]]}
    return truth, tables


def _affidavit(P: Painter, inst: Dict, d: Dict, layout: str):
    P.title("AFFIDAVIT 2", 15)
    P.para(f"(To be executed on non-judicial / e-stamp paper of {C.money_words()})")
    P.kv("E-Stamp certificate no", d["stamp_no"], "stamp_no")
    P.kv("Stamp value", str(d.get("stamp_value", "100")), "stamp_value")
    P.y -= 4
    P.para(f"I, {inst['signatory']}, {inst['signatory_designation']} of {inst['trust_name']}, running {inst['institute_name']} (Application Id {inst['application_id']}), do hereby solemnly affirm and declare as under:")
    for k, t in enumerate(["That the information given in the online application is true and correct.",
                           "That all supporting documents uploaded are authentic copies of the originals.",
                           "That the Institution fulfils the norms of the Approval Process Handbook for the intake applied.",
                           "That nothing has been concealed and I understand that false statements invite action."], 1):
        P.para(f"{k}. {t}")
    P.y -= 6
    P.pair("Place: " + inst["city"], f"Deponent: {inst['signatory']}")
    P.y -= 8
    P.put(P.x0, P.y, f"Sworn before me on {C.fmt_dmy(d['sworn_on'])}", field="sworn_date")
    P.y -= P.s["leading"]
    P.put(P.x0, P.y, f"Notary: {inst['notary']}")
    truth = {"stamp_value": str(d.get("stamp_value", "100")), "stamp_no": d["stamp_no"], "signatory_name": inst["signatory"],
             "signatory_designation": inst["signatory_designation"], "institute_name": inst["institute_name"],
             "application_id": inst["application_id"], "sworn_date": d["sworn_on"].isoformat(), "notary_name": inst["notary"]}
    return truth, {}


def _noc(P: Painter, inst: Dict, d: Dict, layout: str):
    P.title("FORMAT-2: NO OBJECTION CERTIFICATE", 13)
    P.pair(f"Ref No: {d['noc_ref']}", f"Date: {C.fmt_dmy(d['noc_date'])}", "ref_no", "issue_date")
    P.y -= 6
    P.kv("Issued by", inst["university"], "university_name")
    P.para(f"This is to certify that {inst['university']} has no objection to {inst['institute_name']} offering the following programmes for the Academic Year {inst['academic_year']}:")
    rows, flds = [], []
    for i, p in enumerate(d["noc_programs"]):
        rows.append([p["course"], p["intake_curr"]])
        flds.append([None, f"noc_intake_{i}"])
    P.table(["Programme", "Approved Intake"], rows, [0.7, 0.3], flds)
    P.para("This certificate is issued on the request of the institution for submission to the council.")
    P.y -= 12
    P.put(P.x0, P.y, "Registrar (Synthetic)")
    truth = {"university_name": inst["university"], "institute_name": inst["institute_name"], "ref_no": d["noc_ref"],
             "issue_date": d["noc_date"].isoformat(), "academic_year": inst["academic_year"]}
    tables = {"programs": [{"course": p["course"], "intake_curr": p["intake_curr"]} for p in d["noc_programs"]]}
    return truth, tables


def _fire(P: Painter, inst: Dict, d: Dict, layout: str):
    P.title("FIRE SAFETY CERTIFICATE", 15)
    P.kv("Certificate No", d["fire_no"], "certificate_no")
    P.kv("Issued by", d["fire_auth"])
    P.para(f"This is to certify that the building of {inst['institute_name']}, {inst['address']}, has been inspected and found to comply with the fire safety norms.")
    P.kv("Date of Issue", C.fmt_dmy(d["issue_date"]), "issue_date")
    P.kv("Valid Until", C.fmt_dmy(d["valid_until"]), "valid_until")
    P.y -= 10
    P.put(P.x0, P.y, "Fire Officer (Synthetic)")
    if layout == "B":
        P.qr(f"mock-issuer://fire/{d['fire_no']}", P.x1 - 80, 90, 70)
    truth = {"certificate_no": d["fire_no"], "issuing_authority": d["fire_auth"], "institute_name": inst["institute_name"],
             "issue_date": d["issue_date"].isoformat(), "valid_until": d["valid_until"].isoformat()}
    return truth, {}


def _occupancy(P: Painter, inst: Dict, d: Dict, layout: str):
    P.title("OCCUPANCY CERTIFICATE", 15)
    P.kv("Certificate No", d["occ_no"], "certificate_no")
    P.kv("Issued by", d["occ_auth"])
    P.para(f"This is to certify that the building of {inst['institute_name']}, {inst['address']}, has been completed as per the approved plans and is fit for occupation.")
    P.kv("Date of Issue", C.fmt_dmy(d["occ_issue_date"]), "issue_date")
    P.kv("Type of Certificate", d["occ_kind"], "certificate_kind")
    P.y -= 10
    P.put(P.x0, P.y, "Competent Authority (Synthetic)")
    if layout == "B":
        P.qr(f"mock-issuer://occupancy/{d['occ_no']}", P.x1 - 80, 90, 70)
    truth = {"certificate_no": d["occ_no"], "issuing_authority": d["occ_auth"], "institute_name": inst["institute_name"],
             "issue_date": d["occ_issue_date"].isoformat(), "certificate_kind": d["occ_kind"]}
    return truth, {}


def _struct(P: Painter, inst: Dict, d: Dict, layout: str):
    P.title(d["struct_auth"].upper(), 12)
    P.pair(f"No.: {d['struct_no']}", f"Date: {C.fmt_dmy(d['issue_date'])}", "certificate_no", "issue_date")
    P.y -= 6
    P.para(f"To, {inst['institute_name']}, {inst['address']}")
    P.para(f"Sub:- Regarding Safety certificate of Building {inst['institute_name']}, {inst['address']}", bold=True)
    P.para("It is to inform you that the above building has been inspected on the basis of the recommendation and affidavit furnished by the owner; it is certified that this building is safe in normal conditions, excluding natural disasters such as earthquake or cyclone.")
    n = d["validity_years"]
    P.para(f"This Certificate is valid for a period of {n} ({C.NUM_WORDS[n]} Years) from the issued date and is subject to regular upkeep and annual maintenance.", )
    P.y -= 10
    P.put(P.x0, P.y, "Executive Engineer (Synthetic)")
    truth = {"certificate_no": d["struct_no"], "issue_date": d["issue_date"].isoformat(), "validity_years": str(n),
             "issuing_authority": d["struct_auth"], "institute_name": inst["institute_name"]}
    return truth, {}


def _area(P: Painter, inst: Dict, d: Dict, layout: str):
    P.title("STATEMENT OF BUILT-UP AREA (SYNTHETIC)", 13)
    P.kv("Name of the Institution", inst["institute_name"], "institute_name")
    P.para(f"Instructional and other areas of {inst['institute_name']} as constructed on the date of this statement:")
    rows = [[a["room_type"], str(a["count"]), str(a["area_sqm"])] for a in d["areas"]]
    P.table(["Room type", "Number", "Area (sq m)"], rows, [0.5, 0.2, 0.3],
            [[None, f"area_count_{i}", f"area_sqm_{i}"] for i in range(len(rows))])
    total = d.get("total_built_up_area_sqm") or round(sum(a["area_sqm"] for a in d["areas"]) * 1.4)
    P.kv("Total built-up area (sq m)", str(total), "total_built_up_area_sqm")
    P.y -= 10
    P.put(P.x0, P.y, "Architect (Synthetic)")
    truth = {"institute_name": inst["institute_name"], "total_built_up_area_sqm": str(total)}
    return truth, {"areas": [{k: str(v) for k, v in a.items()} for a in d["areas"]]}


_NORMS: list = []


def area_rows(inst: Dict, norms_path: str = "config/area_norms.yaml") -> List[Dict]:
    """Rooms that MEET the norms file (so the demo follows Saanvi's numbers when they replace the placeholder).
    Own RNG seeded from the institute, so other random values in default_details do not shift."""
    if not _NORMS:
        try:
            import yaml
            with open(norms_path) as f:
                _NORMS.extend((yaml.safe_load(f) or {}).get("norms", []))
        except Exception:
            _NORMS.append({"room_type": "classroom", "min_rooms_number": 4, "min_area_per_room_sqm": 66})
    rng = random.Random(f"area-{inst['permanent_id']}")
    out = []
    for n in _NORMS:
        cnt = int(n.get("min_rooms_number") or rng.randint(3, 6)) + rng.randint(0, 3)
        per = float(n.get("min_area_per_room_sqm") or 30) * rng.uniform(1.05, 1.35)
        out.append({"room_type": n["room_type"].replace("_", " ").title(), "count": cnt, "area_sqm": round(cnt * per)})
    if not any(n.get("room_type") == "library" for n in _NORMS):     # the real norms include a library row (400 sq m)
        out.append({"room_type": "Library", "count": 1, "area_sqm": rng.randint(300, 500)})
    return out


BUILDERS = {"eoa_letter": _eoa, "affidavit_2": _affidavit, "noc_format2": _noc, "fire_cert": _fire, "structural_cert": _struct,
            "area_statement": _area, "occupancy_cert": _occupancy}
OCC_AUTH = ("Building Permission Cell, Municipal Corporation (Synthetic)", "Urban Development Authority (Synthetic)",
            "Town Planning Department (Synthetic)")


def default_details(rng: random.Random, inst: Dict) -> Dict:
    """Per-document details (dates, numbers) that are valid by default."""
    ay0 = int(inst["academic_year"][:4])
    appr = C.rand_date(rng, date(ay0, 2, 20), date(ay0, 4, 25))
    issue_fire = C.rand_date(rng, date(ay0 - 1, 6, 1), date(ay0, 1, 31))
    return {
        "approval_date": appr, "printed_on": appr + timedelta(days=rng.randint(0, 3)),
        "stamp_no": f"IN-{rng.choice(['DL', 'MH', 'KA', 'TN'])}{rng.randint(10**13, 10**14 - 1)}",
        "sworn_on": C.rand_date(rng, date(ay0, 1, 5), date(ay0, 3, 30)),
        "noc_ref": f"REG/NOC/{ay0}/{rng.randint(100, 9999)}", "noc_date": C.rand_date(rng, date(ay0 - 1, 11, 1), date(ay0, 2, 28)),
        "noc_programs": [{"course": p["course"], "intake_curr": p["intake_curr"]} for p in inst["programs"]],
        "fire_no": f"FS/{ay0 - 1}/{rng.randint(1000, 99999)}", "fire_auth": rng.choice(C.FIRE_AUTH),
        "issue_date": issue_fire, "valid_until": issue_fire + timedelta(days=365 * 3),
        "struct_no": str(rng.randint(100, 999)), "struct_auth": rng.choice(C.STRUCT_AUTH), "validity_years": rng.choice([3, 5]),
        "areas": area_rows(inst),
        **_occ_details(inst),
    }


def _occ_details(inst: Dict) -> Dict:
    """Occupancy certificate: full, issued 5-20 years before the academic year. Own random source, so adding it changed
    no other generated value (existing demo documents and the tamper dataset stay identical)."""
    r, ay0 = random.Random(f"occ-{inst['permanent_id']}"), int(inst["academic_year"][:4])
    issued = C.rand_date(r, date(ay0 - 20, 1, 1), date(ay0 - 5, 6, 30))
    return {"occ_no": f"OC/{issued.year}/{r.randint(10000, 99999)}", "occ_auth": r.choice(OCC_AUTH), "occ_issue_date": issued,
            "occ_kind": "Full"}


CREATED_FROM = {"eoa_letter": "printed_on", "affidavit_2": "sworn_on", "noc_format2": "noc_date", "fire_cert": "issue_date",
                "structural_cert": "issue_date", "area_statement": "noc_date",
                "occupancy_cert": "occ_issue_date"}


def render_pdf(doc_type: str, layout: str, inst: Dict, details: Dict, out_path: str,
               producer: str = "SYNTH-PORTAL Renderer 1.0", font_override: Optional[Dict[str, str]] = None) -> Dict:
    """Write one PDF. Returns {truth, tables, boxes (normalised), layout, doc_type, path}."""
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    when = details.get(CREATED_FROM.get(doc_type, ""))          # synthetic timeline: file created on its printed date
    old = os.environ.get("SOURCE_DATE_EPOCH")
    if isinstance(when, date):
        os.environ["SOURCE_DATE_EPOCH"] = str(int(datetime(when.year, when.month, when.day, 11, 0, tzinfo=timezone.utc).timestamp()))
    try:
        P = Painter(out_path, layout, producer)                 # reportlab reads SOURCE_DATE_EPOCH for CreationDate/ModDate
    finally:
        if old is None:
            os.environ.pop("SOURCE_DATE_EPOCH", None)
        else:
            os.environ["SOURCE_DATE_EPOCH"] = old
    P.font_override = dict(font_override or {})
    truth, tables = BUILDERS[doc_type](P, inst, details, layout)
    P.finish()
    return {"doc_type": doc_type, "layout": layout, "path": out_path, "truth": truth, "tables": tables,
            "boxes": P.norm_boxes()}
