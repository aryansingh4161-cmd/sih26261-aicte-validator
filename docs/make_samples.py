import json
import math
import os
import sys

import fitz  # PyMuPDF
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas

PDF_NAME = "synthetic_letter_clean.pdf"
FONT_PATH = r"C:\Windows\Fonts\arial.ttf"
DPI = 150
SCALE = DPI / 72
PAGE_W, PAGE_H = A4
FONT, SIZE = "Helvetica", 11

PROGRAMMES = [
    ("Diploma in Sample Engineering", "Diploma", "120"),
    ("Bachelor of Demo Technology", "UG", "60"),
    ("Master of Example Management", "PG", "90"),
]
TARGET_ROW = 0      # 0 = first programme (original "120", same digit count as the new number)
NEW_INTAKE = "180"  # replaces the original number in the target row

COL_X = [50, 85, 330, 430, PAGE_W - 50]
TABLE_TOP = PAGE_H - 330
ROW_H = 26


def draw_pdf():
    """Draw the clean letter; return info about the target number."""
    c = canvas.Canvas(PDF_NAME, pagesize=A4)
    c.setFont("Helvetica-Bold", 18)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 60, "EXAMPLE COUNCIL (SYNTHETIC)")
    c.setFont(FONT, 10)
    c.drawCentredString(PAGE_W / 2, PAGE_H - 78,
                        "100 Demo Avenue, Sampletown, Exampleland - 000000")
    c.line(50, PAGE_H - 90, PAGE_W - 50, PAGE_H - 90)
    c.setFont(FONT, SIZE)
    c.drawString(50, PAGE_H - 120, "Ref No: EC/SYN/2026/000123")
    c.drawRightString(PAGE_W - 50, PAGE_H - 120, "Date: 01-01-2026")
    c.drawString(50, PAGE_H - 155, "To,")
    c.drawString(50, PAGE_H - 170, "The Director, Riverbend Demo Institute (Fictional)")
    c.drawString(50, PAGE_H - 185, "27 Sample Lane, Testville, Exampleland - 111111")
    c.setFont("Helvetica-Bold", SIZE)
    c.drawString(50, PAGE_H - 215,
                 "Subject: Extension of Approval for Academic Year 2026-27 (synthetic)")
    c.setFont(FONT, SIZE)
    c.drawString(50, PAGE_H - 245, "This is a made-up letter used only to test software.")
    c.drawString(50, PAGE_H - 260, "The following programmes and intakes are listed:")

    # table grid
    n_rows = len(PROGRAMMES) + 1
    for k in range(n_rows + 1):
        c.line(COL_X[0], TABLE_TOP - ROW_H * k, COL_X[-1], TABLE_TOP - ROW_H * k)
    for x in COL_X:
        c.line(x, TABLE_TOP, x, TABLE_TOP - ROW_H * n_rows)

    # header row
    c.setFont("Helvetica-Bold", SIZE)
    for x, text in zip(COL_X, ["No.", "Programme", "Level", "Intake"]):
        c.drawString(x + 8, TABLE_TOP - 17, text)

    # data rows
    c.setFont(FONT, SIZE)
    target = None
    for i, (name, level, intake) in enumerate(PROGRAMMES):
        row_top = TABLE_TOP - ROW_H * (i + 1)
        base = row_top - 17
        c.drawString(COL_X[0] + 8, base, str(i + 1))
        c.drawString(COL_X[1] + 8, base, name)
        c.drawString(COL_X[2] + 8, base, level)
        c.drawString(COL_X[3] + 8, base, intake)
        if i == TARGET_ROW:
            width = stringWidth(intake, FONT, SIZE)
            x0 = COL_X[3] + 8
            target = {"text": intake, "x": x0, "base": base,
                      "rect_pt": (x0 - 2, base - 3, x0 + width + 2, base + 10)}

    c.setFont(FONT, 9)
    c.drawCentredString(PAGE_W / 2, 30, "SYNTHETIC SAMPLE")
    c.save()
    return target


def main():
    if not os.path.exists(FONT_PATH):
        sys.exit("STOP: font not found at " + FONT_PATH)
    target = draw_pdf()
    print("made", PDF_NAME)

    page = fitz.open(PDF_NAME)[0]
    page.get_pixmap(dpi=DPI).save("clean.png")
    print("made clean.png")

    # PDF rectangle (y up) -> pixel rectangle (y down)
    px0, pb, px1, pt = target["rect_pt"]
    x0 = math.floor(px0 * SCALE)
    x1 = math.ceil(px1 * SCALE)
    y0 = math.floor((PAGE_H - pt) * SCALE)
    y1 = math.ceil((PAGE_H - pb) * SCALE)

    img = Image.open("clean.png").convert("RGB")
    draw = ImageDraw.Draw(img)
    draw.rectangle([x0, y0, x1 - 1, y1 - 1], fill="white")
    font = ImageFont.truetype(FONT_PATH, round(SIZE * SCALE))
    draw.text((target["x"] * SCALE, (PAGE_H - target["base"]) * SCALE),
              NEW_INTAKE, font=font, fill="black", anchor="ls")
    img.save("tampered.jpg", quality=85)
    print("made tampered.jpg")

    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
    mask.save("tampered_mask.png")
    print("made tampered_mask.png")

    truth = {
        "original_number": target["text"],
        "replacement_number": NEW_INTAKE,
        "bbox_pixels_x0_y0_x1_y1": [x0, y0, x1, y1],
        "bbox_note": "x1 and y1 are exclusive; origin top-left; same pixels as clean.png",
        "image_size_w_h": list(img.size),
        "dpi": DPI,
        "bbox_pdf_points_x0_ybottom_x1_ytop": [round(v, 2) for v in target["rect_pt"]],
        "synthetic": True,
    }
    with open("ground_truth.json", "w") as f:
        json.dump(truth, f, indent=2)
    print("made ground_truth.json")


main()
