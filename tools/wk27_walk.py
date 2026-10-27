"""WK27 G: the officer walkthrough (Regulation Bureau), recorded as screenshots out/review/wk27/walk_<lang>_<nn>_<step>.png.
Sign in -> Home -> APP-07 -> open the full case -> confirm its findings -> magnifier -> draft the letter -> seal -> verify in Letters;
APP-17 (photos) -> mark one Correct -> letter -> seal; Analytics chart / table. Needs the app running (demo or live).
  python -m tools.wk27_walk [--base http://127.0.0.1:5173] [--langs hi,en]"""
from __future__ import annotations

import argparse
import json
import os

from tools.wk27_check import OUT, ready, tr


def walk(b, base: str, lang: str) -> list[str]:
    notes: list[str] = []
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script("try{if(!sessionStorage.getItem('w')){localStorage.clear();" + "".join(
        f"localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in {"pramaan.lang": lang, "pramaan.theme": "light"}.items())
        + "sessionStorage.setItem('w','1');}}catch(e){}")
    pg = ctx.new_page()
    n = [0]

    def snap(step: str):
        n[0] += 1
        pg.screenshot(path=f"{OUT}/walk_{lang}_{n[0]:02d}_{step}.png")

    pg.goto(f"{base}/#/sign-in"); ready(pg, 300); snap("sign_in")
    pg.locator(".signin .btn.primary").click(); ready(pg); snap("home")
    pg.locator(".qrow", has_text="APP-07").click(); ready(pg); snap("home_app07")
    pg.locator(".pv .btn.brand").click(); ready(pg); snap("case_evidence")
    for card in pg.locator(".issue").all():
        card.get_by_role("button", name=tr("Correct", lang)).click(); pg.wait_for_timeout(150)
    snap("confirmed")
    pg.locator(".issue", has=pg.locator(".evnum")).filter(has=pg.locator(".rule", has_text="X-NAME")).click(); pg.wait_for_timeout(700); snap("magnifier")
    pg.locator(".casehead .btn.primary").click(); ready(pg); snap("letter")
    ticked = pg.locator(".incl input:checked").count()
    notes.append(f"APP-07 letter: {ticked} of {pg.locator('.incl input').count()} ticked after confirming")
    pg.get_by_role("button", name=tr("Seal and issue", lang)).click(); pg.wait_for_timeout(1800); snap("sealed")
    pg.goto(f"{base}/#/letters"); ready(pg)
    row = pg.locator("tr", has_text="APP-07").first
    row.get_by_role("button", name=tr("Verify", lang)).click(); pg.wait_for_timeout(500); snap("letters_verify")
    notes.append("Verify: " + row.inner_text().replace("\n", " | ")[-160:])
    pg.goto(f"{base}/#/?file=APP-17"); ready(pg); snap("home_app17")
    pg.locator(".pv .btn.brand").click(); ready(pg)
    ph = pg.locator(".isec", has=pg.locator(".isec-title", has_text=tr("Photos and metadata", lang)))
    ph.locator(".issue").first.click(); pg.wait_for_timeout(500); snap("app17_photo")
    ph.locator(".issue").first.get_by_role("button", name=tr("Correct", lang)).click(); pg.wait_for_timeout(200)
    notes.append("APP-17 next line: " + pg.locator(".nextline").inner_text())
    pg.locator(".casehead .btn.primary").click(); ready(pg); snap("app17_letter")
    pg.get_by_role("button", name=tr("Seal and issue", lang)).click(); pg.wait_for_timeout(1800); snap("app17_sealed")
    pg.goto(f"{base}/#/analytics"); ready(pg); snap("analytics_chart")
    pg.locator(".seg.tall button").nth(1).click(); pg.wait_for_timeout(300); snap("analytics_table")
    ctx.close()
    return notes


if __name__ == "__main__":
    from playwright.sync_api import sync_playwright
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5173"); ap.add_argument("--langs", default="hi,en")
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        for lang in a.langs.split(","):
            for x in walk(b, a.base, lang):
                print(lang, x)
        b.close()
