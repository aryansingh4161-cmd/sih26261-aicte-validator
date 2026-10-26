"""WK26 Playwright flows against the LIVE stack (no pytest): a fresh pipeline run of the 23 synthetic demo apps in a temp folder,
the API (uvicorn, port 8600) and the web app (Vite dev, live mode, port 5173), driven with the installed Google Chrome.
  python -m tests.test_web_flows [name ...]
Flows: sign in -> APP-07 -> DigiLocker preview -> draft + seal a Letter of Deficiency -> verify; batch approve with the spot check;
Hindi and Urdu (right to left); dark mode."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request
from datetime import date

BASE = "http://127.0.0.1:5173"
_PROCS: list = []


def _wait(url: str, secs: int = 120) -> None:
    end = time.time() + secs
    while time.time() < end:
        try:
            urllib.request.urlopen(url, timeout=2); return
        except Exception:
            time.sleep(0.5)
    raise TimeoutError(url)


def start() -> str:
    work = tempfile.mkdtemp(prefix="pramaan_web_flows_")
    env = {**os.environ, "PRAMAAN_OUT": work, "PRAMAAN_TODAY": "2026-10-27", "PRAMAAN_OUTBOX": os.path.join(work, "outbox")}
    os.environ.update({k: env[k] for k in ("PRAMAAN_OUT", "PRAMAAN_TODAY", "PRAMAAN_OUTBOX")})
    from pramaan.pipeline import run_application
    for k in range(1, 24):
        run_application(f"data/demo/apps/APP-{k:02d}.json", work, date(2026, 10, 27), os.path.join(work, "audit.db"),
                        reuse_db=os.path.join(work, "reuse.db"))
    _PROCS.append(subprocess.Popen([sys.executable, "-m", "uvicorn", "api.main:app", "--port", "8600"], env=env,
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    _PROCS.append(subprocess.Popen(["npm", "--prefix", "web", "run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort"],
                                   env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
    _wait("http://127.0.0.1:8600/api/health"); _wait(BASE)
    return work


def stop() -> None:
    for p in _PROCS:
        p.terminate()


def page(b, signed_in=True, theme="light", lang="en", role="regulation_bureau"):
    ctx = b.new_context(viewport={"width": 1440, "height": 900})
    ctx.add_init_script(f"""try{{localStorage.setItem('pramaan.signedIn','{'yes' if signed_in else ''}');localStorage.setItem('pramaan.theme','{theme}');
      localStorage.setItem('pramaan.lang','{lang}');localStorage.setItem('pramaan.role','{role}');}}catch(e){{}}""")
    return ctx.new_page()


def t_sign_in_letter_verify(b):
    pg = page(b, signed_in=False)
    pg.goto(f"{BASE}/#/sign-in"); pg.get_by_role("button", name="Continue with AICTE portal sign-in").click()
    pg.get_by_role("heading", name="Your queue.").wait_for(timeout=30000)
    assert pg.locator(".demo-pill").count() == 0, "live mode, not the demo"
    pg.goto(f"{BASE}/#/case/APP-07/sources")
    row = pg.locator("tr", has_text="DigiLocker").first
    row.get_by_role("button", name="Preview").click()
    drawer = pg.get_by_role("dialog", name="Preview")
    drawer.get_by_text("Answer hash").wait_for(timeout=20000)
    assert "DigiLocker" in drawer.inner_text() and "demo adapter" in drawer.inner_text()
    drawer.get_by_role("button", name="Close").click()
    pg.goto(f"{BASE}/#/case/APP-07/letter")
    pg.locator(".incl input").first.wait_for(timeout=20000)
    seal = pg.get_by_role("button", name="Seal and issue")
    if seal.is_disabled():                                            # APP-07 has only Human review items: the officer includes one
        pg.locator(".incl input").first.check()
        pg.locator(".letter-paper ol li").first.wait_for(timeout=20000)
    seal.click()
    pg.get_by_text("Sealed and issued.").wait_for(timeout=20000)
    txt = pg.locator(".sealresult").inner_text()
    assert "VALID: matches audit entry" in txt, txt
    pg.goto(f"{BASE}/#/letters")
    r = pg.locator("tr", has_text="APP-07").first
    r.wait_for(timeout=20000)
    r.get_by_role("button", name="Verify").click()
    pg.get_by_text("VALID: matches audit entry").first.wait_for(timeout=20000)


def t_batch_approve(b):
    pg = page(b)
    pg.goto(f"{BASE}/#/")
    pg.get_by_role("button", name="Approve clear files").click()
    dlg = pg.get_by_role("dialog")
    approve = dlg.get_by_role("button", name="and seal")
    assert approve.is_disabled(), "locked until the spot check"
    dlg.locator(".spotbox .btn.small").click()
    dlg.get_by_role("button", name="I opened it and agree").click()
    approve.click()
    dlg.get_by_text("Approved and sealed.").wait_for(timeout=20000)


def t_languages_and_dark(b):
    pg = page(b, lang="hi")
    pg.goto(f"{BASE}/#/"); pg.locator(".qrow").first.wait_for(timeout=30000)
    h = pg.locator("h1").first.inner_text()
    assert any(ord(ch) > 2303 for ch in h), f"Hindi heading expected, got {h!r}"
    assert pg.evaluate("document.documentElement.lang") == "hi"
    pg = page(b, lang="ur")
    pg.goto(f"{BASE}/#/"); pg.locator(".qrow").first.wait_for(timeout=30000)
    assert pg.evaluate("document.documentElement.dir") == "rtl"
    rail = pg.locator(".rail").bounding_box()
    assert rail["x"] > 1300, f"rail on the right in Urdu, x={rail['x']}"
    pg = page(b)
    pg.goto(f"{BASE}/#/"); pg.locator(".qrow").first.wait_for(timeout=30000)
    pg.get_by_role("button", name="Switch to dark mode").click()
    assert pg.evaluate("document.documentElement.dataset.theme") == "dark"
    bg = pg.evaluate("getComputedStyle(document.body).backgroundColor")
    assert bg == "rgb(17, 25, 21)", bg                               # --bg dark #111915


TESTS = {"sign_in_letter_verify": t_sign_in_letter_verify, "batch_approve": t_batch_approve, "languages_and_dark": t_languages_and_dark}

if __name__ == "__main__":
    want = sys.argv[1:] or list(TESTS)
    failed = 0
    start()
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            b = p.chromium.launch(channel="chrome", headless=True)
            for name in want:
                try:
                    TESTS[name](b); print(f"PASS {name}", flush=True)
                except Exception:
                    failed += 1; print(f"FAIL {name}", flush=True); traceback.print_exc(limit=3)
            b.close()
    finally:
        stop()
    print("ALL TESTS PASSED" if not failed else f"{failed} FAILED")
    sys.exit(1 if failed else 0)
