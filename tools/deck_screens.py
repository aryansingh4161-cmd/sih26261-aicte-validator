"""Deck screenshots of the dashboard pages (Playwright + the installed Google Chrome; no browser download), 1600x900.
Needs a running dashboard:  streamlit run dashboard/app.py --server.port 8599 --server.headless true
  python -m tools.deck_screens [--base http://127.0.0.1:8599] [--only wk23_1,wk23_3]   -> out/deck/<name>.png
Each shot = (name, page path, steps); a step is ("select", label, option), ("click", button text), ("tab", text),
("expand", text), ("signin", user name) or ("scroll", text). Synthetic demo data only. OWNER: Aryan."""
from __future__ import annotations

import argparse
import os

SHOTS = [
    ("wk23_1", "Desk", [("select", "Open application", "APP-02"), ("scroll", "Letter of Deficiency (draft)")]),
    ("wk23_2", "Desk", [("select", "Open application", "APP-19"), ("scroll", "Resubmission of")]),
    ("wk23_3", "Desk", [("select", "Open application", "APP-02"), ("expand", "R05"), ("scroll", "Checklist")]),
    ("wk23_6", "Desk", [("select", "Open application", "APP-02"), ("click", "Seal for export"), ("scroll", "Download sealed HTML")]),
    ("wk23_8", "Checks", [("scroll", "Serial reuse across institutes")]),
    ("wk23_9", "Checks", [("select", "Open application", "APP-03"), ("scroll", "Verification board")]),
    ("wk23_11", "Checks", [("select", "Open application", "APP-17"), ("expand", "JPEG tables"), ("click", "False alarm"),
                           ("scroll", "Findings")]),
    ("wk23_10", "Calendar_Exports", [("scroll", "Certificate expiries")]),
    ("wk23_12", "Calendar_Exports", [("signin", "Demo Officer South-East"), ("scroll", "My queue")]),
    ("wk23_13", "Calendar_Exports", [("click", "Build case ZIP"), ("scroll", "RTI / appeal case export")]),
]


def run(base: str, only: set | None, out_dir: str = "out/deck") -> list[str]:
    from playwright.sync_api import sync_playwright
    os.makedirs(out_dir, exist_ok=True)
    done = []
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        for name, page, steps in SHOTS:
            if only and name not in only:
                continue
            pg = b.new_page(viewport={"width": 1600, "height": 900})
            try:
                pg.goto(f"{base}/{page}", wait_until="networkidle")
                pg.get_by_text("Sign in as").first.wait_for(timeout=60000)
                pg.wait_for_timeout(1500)
                for st in steps:
                    if st[0] == "select":
                        box = pg.get_by_label(st[1]).first                # type into the combobox, then Enter
                        box.click(); box.fill(st[2]); pg.wait_for_timeout(400); box.press("Enter")
                    elif st[0] == "signin":
                        pg.get_by_label("Sign in as").first.click(); pg.wait_for_timeout(300)
                        pg.get_by_role("option", name=st[1], exact=False).first.click()
                    elif st[0] == "click":
                        pg.get_by_role("button", name=st[1]).first.click()
                    elif st[0] == "tab":
                        pg.get_by_role("tab", name=st[1]).click()
                    elif st[0] == "expand":
                        pg.get_by_text(st[1], exact=False).first.click()
                    elif st[0] == "scroll":                            # headings first (text matches can be hidden nodes)
                        h = pg.get_by_role("heading", name=st[1])
                        (h.first if h.count() else pg.get_by_text(st[1]).locator("visible=true").first).scroll_into_view_if_needed()
                    pg.wait_for_timeout(1500)
                path = os.path.join(out_dir, f"{name}.png")
                pg.screenshot(path=path)
                done.append(path); print("wrote", path, flush=True)
            except Exception as e:                                 # report and continue with the next shot
                print(f"FAILED {name}: {type(e).__name__}: {str(e).splitlines()[0][:120]}", flush=True)
            pg.close()
        b.close()
    return done


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8599"); ap.add_argument("--only", default="")
    a = ap.parse_args()
    run(a.base, set(a.only.split(",")) - {""} or None)
