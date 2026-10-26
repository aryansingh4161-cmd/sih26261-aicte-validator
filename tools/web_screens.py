"""WK26 screenshots of the web app (Playwright + the installed Google Chrome), 1440x900, to out/deck/wk26_<nn>_<screen>.png.
Needs the app running: live (uvicorn api.main:app --port 8600 + npm run dev in web/) or the demo build (npm run preview).
  python -m tools.web_screens [--base http://127.0.0.1:5173] [--only 02_home,03_case_evidence]
Each shot: (name, hash route, settings, steps). settings = theme / lang / role, put in localStorage before the page loads.
Steps: ("click", text) / ("click_sel", css) / ("key", key) / ("type", css, text) / ("wait", ms). The shot waits until no
skeleton (.skel) is left on the page."""
from __future__ import annotations

import argparse
import json
import os

SHOTS = [
    ("02_shell_light", "/", {}, []),
    ("02_shell_dark", "/", {"theme": "dark"}, []),
    ("02_shell_hindi", "/", {"lang": "hi"}, []),
    ("02_shell_urdu", "/", {"lang": "ur"}, []),
    ("02_shell_profile", "/", {}, [("click_sel", "button.avatar")]),
]


def run(base: str, only: set | None, out_dir: str = "out/deck") -> None:
    from playwright.sync_api import sync_playwright
    os.makedirs(out_dir, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        for name, route, st, steps in SHOTS:
            if only and name not in only:
                continue
            ctx = b.new_context(viewport={"width": 1440, "height": 900})
            init = {"pramaan.signedIn": "yes", "pramaan.theme": st.get("theme", "light"), "pramaan.lang": st.get("lang", "en"),
                    "pramaan.role": st.get("role", "regulation_bureau")}
            if st.get("signed_out"):
                init["pramaan.signedIn"] = ""
            ctx.add_init_script("try{" + "".join(f"localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in init.items())
                                + "localStorage.removeItem('pramaan.demo.actions.v1');}catch(e){}")
            pg = ctx.new_page()
            try:
                pg.goto(f"{base}/#{route}", wait_until="networkidle")
                pg.wait_for_timeout(600)
                for s in steps:
                    if s[0] == "click":
                        pg.get_by_text(s[1], exact=False).first.click()
                    elif s[0] == "click_sel":
                        pg.locator(s[1]).first.click()
                    elif s[0] == "key":
                        pg.keyboard.press(s[1])
                    elif s[0] == "type":
                        pg.locator(s[1]).first.fill(s[2]); pg.keyboard.press("Enter")
                    elif s[0] == "wait":
                        pg.wait_for_timeout(s[1])
                    pg.wait_for_timeout(500)
                for _ in range(60):                                  # skeletons gone = data on screen
                    if pg.locator(".skel").count() == 0:
                        break
                    pg.wait_for_timeout(500)
                pg.wait_for_timeout(700)
                path = os.path.join(out_dir, f"wk26_{name}.png")
                pg.screenshot(path=path)
                print("wrote", path, flush=True)
            except Exception as e:
                print(f"FAILED {name}: {type(e).__name__}: {str(e).splitlines()[0][:140]}", flush=True)
            ctx.close()
        b.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5173"); ap.add_argument("--only", default="")
    a = ap.parse_args()
    run(a.base, set(a.only.split(",")) - {""} or None)
