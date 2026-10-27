"""WK27 fix checks (docs/WK27_FIXES.md): one Playwright check per fix ID, in English AND Hindi, against the running web app
(demo build: npm --prefix web run dev -- --mode demo). Each check asserts its acceptance test and saves
out/review/wk27/<ID>_<lang>.png. Prints PASS / FAIL per ID and language.
  python -m tools.wk27_check [--base http://127.0.0.1:5173] [--only A1,D2] [--langs en,hi]"""
from __future__ import annotations

import argparse
import json
import os
import re
import traceback
import zipfile

OUT = "out/review/wk27"
HI = json.load(open("web/src/i18n/hi.json", encoding="utf-8"))
_Q = json.load(open("web/public/snapshot/en/queue/regulation_bureau.json"))["items"]
INSTITUTES = {i["institute"] for i in _Q}
PLACES = {w for i in _Q for w in re.findall(r"[A-Z][a-z]+", i["place"])}          # synthetic place names are data, not UI text
ROUTES = ["/", "/?file=APP-07", "/case/APP-07", "/case/APP-17", "/case/APP-07/checklist", "/case/APP-07/sources", "/case/APP-20/changes",
          "/case/APP-19/resubmission", "/case/APP-07/letters", "/case/APP-07/notes", "/case/APP-07/timeline", "/case/APP-03/letter", "/letters",
          "/calendar", "/appeals", "/analytics", "/search?q=fire", "/visit/APP-15", "/privacy", "/sign-in"]
# Words that keep their capital inside a sentence: Handbook names, proper nouns, acronyms (DESIGN_SYSTEM.md section 9).
PROPER = {"Letter", "Deficiency", "Approval", "Extension", "Regulation", "Bureau", "Scrutiny", "Re-Scrutiny", "Committee", "Expert", "Visit",
          "Standing", "Hearing", "Executive", "Appellate", "Show", "Cause", "Notice", "Speaking", "Order", "AICTE", "Pramaan", "AI", "ZIP", "PDF",
          "CSV", "Permanent", "Id", "DigiLocker", "Handbook", "Ctrl", "K", "Enter", "Esc", "Regional", "Office", "Registrar", "Societies", "NBA",
          "Fire", "Department", "QR", "OK", "Correct", "English", "Hindi", "Urdu", "SSO", "Google", "Chrome", "Demo", "Officer", "South-East",
          "North-West", "Central", "West", "Exampleland", "North", "South", "East", "Institute", "Technology", "Campus", "Technical",
          # Handbook document names, as the engine writes them in rule titles and letters (pramaan/letters.py DOC_NAMES)
          "Safety", "Stability", "Certificate", "Completion", "Occupancy", "Building", "License", "Form", "D", "Format", "NOC", "EoA", "Rs", "R",
          "University", "Affidavit", "School", "College", "Engineering", "Management", "Sciences"}


def tr(text: str, lang: str) -> str:
    return HI.get(text, text) if lang == "hi" else text


def context(b, lang="en", theme="light", signed_in=True, reduced=False, keep=None):
    ctx = b.new_context(viewport={"width": 1440, "height": 900}, accept_downloads=True, reduced_motion="reduce" if reduced else "no-preference")
    init = {"pramaan.signedIn": "yes" if signed_in else "", "pramaan.theme": theme, "pramaan.lang": lang, "pramaan.role": "regulation_bureau",
            "pramaan.rail": "closed"}
    init.update(keep or {})
    ctx.add_init_script("try{if(!sessionStorage.getItem('wk27')){" + "".join(f"localStorage.setItem({json.dumps(k)},{json.dumps(v)});" for k, v in init.items())
                        + "localStorage.removeItem('pramaan.demo.actions.v1');sessionStorage.setItem('wk27','1');}}catch(e){}")
    return ctx


def ready(pg, ms=500):
    pg.wait_for_load_state("networkidle")
    for _ in range(60):
        if pg.locator(".skel").count() == 0:
            break
        pg.wait_for_timeout(250)
    pg.wait_for_timeout(ms)


def go(pg, base, route, ms=500):
    pg.goto(f"{base}/#{route}"); ready(pg, ms)


def shot(pg, fid, lang):
    global OUT
    os.makedirs(OUT, exist_ok=True)
    p = f"{OUT}/{fid}_{lang}.png"
    pg.screenshot(path=p)
    return p


WRAP_JS = """(sel) => {
  // a label wraps when its TEXT (not its icons) sits on more than one line
  const out = [];
  for (const el of document.querySelectorAll(sel)) {
    if (!el.offsetParent || !el.innerText.trim()) continue;
    const tw = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    const tops = [];
    for (let n = tw.nextNode(); n; n = tw.nextNode()) {
      if (!n.textContent.trim()) continue;
      const r = document.createRange(); r.selectNodeContents(n);
      for (const x of r.getClientRects()) if (x.width > 1) tops.push(x.top + x.height / 2);
    }
    const lh = parseFloat(getComputedStyle(el).fontSize) || 14;
    if (tops.length && Math.max(...tops) - Math.min(...tops) > lh * 0.9) out.push(el.innerText.trim().replace(/\\s+/g, ' ').slice(0, 40) + ' <' + el.tagName.toLowerCase() + '.' + el.className + '>');
  }
  return out;
}"""
CONTROLS = "button, .btn, .chip, .tabband a, .select, .dd-val, th, .rail-label, .seg button, .menu-item, .isec-title, .crumbs a"


# ---------------- checks: each returns a list of problems (empty = pass) ----------------
def a1(pg, base, lang):
    bad = []
    for sel in (".rail .logo", "a.wordmark"):
        go(pg, base, "/calendar")
        pg.locator(sel).first.click(); ready(pg)
        if not re.search(r"#/(\?.*)?$", pg.url):
            bad.append(f"{sel} -> {pg.url}")
    shot(pg, "A1", lang)
    return bad


def a2(pg, base, lang):
    go(pg, base, "/")
    w0 = pg.locator(".rail").bounding_box()["width"]
    pg.locator(".rail-toggle").click(); pg.wait_for_timeout(300)
    w1 = pg.locator(".rail").bounding_box()["width"]
    pg.reload(); ready(pg)
    w2 = pg.locator(".rail").bounding_box()["width"]
    labels = pg.locator(".rail-item .rail-label").all_inner_texts()
    shot(pg, "A2", lang)
    wraps = pg.evaluate(WRAP_JS, ".rail-label")
    pg.locator(".rail-toggle").click(); pg.wait_for_timeout(200)
    w3 = pg.locator(".rail").bounding_box()["width"]
    bad = [] if (w0 == 72 and 200 <= w1 <= 240 and w2 == w1 and w3 == 72 and len(labels) == 5 and all(labels)) else [f"widths {w0},{w1},{w2},{w3} labels {labels}"]
    return bad + [f"wrap: {x}" for x in wraps]


def a3(pg, base, lang):
    bad = []
    go(pg, base, "/sign-in")
    dd = pg.locator(".signin-row .dd-wrap").nth(1)
    dd.locator("button.select").click(); pg.wait_for_timeout(300)
    m = pg.locator(".pop.menu").first
    info = m.evaluate("e => ({up: e.classList.contains('up'), h: e.getBoundingClientRect().height, sh: e.scrollHeight, ch: e.clientHeight, "
                      "bottom: e.getBoundingClientRect().bottom, top: e.getBoundingClientRect().top})")
    page_scroll = pg.evaluate("[document.scrollingElement.scrollHeight - innerHeight, document.scrollingElement.scrollTop]")
    m.evaluate("e => e.scrollTop = 200"); pg.wait_for_timeout(100)
    after = pg.evaluate("document.scrollingElement.scrollTop")
    shot(pg, "A3", lang)
    if info["h"] > 321: bad.append(f"menu {info['h']}px high")
    if info["sh"] <= info["ch"]: bad.append("menu does not scroll inside (all items fit?)")
    if info["bottom"] > 900 or info["top"] < 0: bad.append(f"menu off screen {info}")
    if page_scroll[0] > 0 or after != 0: bad.append(f"page scrolls {page_scroll} {after}")
    pg.keyboard.press("Escape")
    for route in ("/", "/case/APP-03/letter", "/sign-in"):
        go(pg, base, route)
        bad += [f"{route} wraps: {x}" for x in pg.evaluate(WRAP_JS, ".dd-val, .select")]
    return bad


def a4(pg, base, lang):
    bad = []
    raw = re.compile(r"\b(officer\.[a-z0-9]+|human_review|return_for_rectification|not_automated|derived|pramaan-pipeline)\b|lane human")
    for route in ("/?file=APP-07", "/case/APP-07", "/case/APP-07/timeline", "/case/APP-07/notes", "/case/APP-17", "/letters", "/case/APP-07/checklist"):
        go(pg, base, route)
        txt = pg.locator("main").inner_text()
        for m in set(raw.findall(txt)):
            bad.append(f"{route}: raw '{m}'")
        if lang == "en":
            for el in pg.locator("main button, main .tabband a, main th, main .step-label, main td, main h1, main h2, main h3").all():
                tx = el.inner_text().strip().split("\n")[0]
                if el.evaluate("e => !!e.closest('.case-title, .pv-head h2') || (e.tagName === 'TD' && !!e.querySelector('button, a'))") \
                        or any(n in tx for n in INSTITUTES):
                    continue                                                      # institute names are proper names; buttons are checked on their own
                words = re.findall(r"[A-Za-z][A-Za-z-]*", tx.split(": ")[-1])
                caps = [w for w in words[1:] if w[0].isupper() and w not in PROPER and not re.match(r"^[A-Z]{2,}", w)]
                if caps and len(words) > 1 and not re.search(r"APP-|\d-\d{5}", tx):
                    bad.append(f"{route}: case '{tx[:50]}' ({', '.join(caps)})")
    go(pg, base, "/case/APP-07/timeline")
    shot(pg, "A4", lang)
    return sorted(set(bad))


def a5(pg, base, lang):
    bad = []
    for route, sel in (("/case/APP-07", ".casehead"), ("/case/APP-03/letter", ".letter-paper"), ("/letters", "main"), ("/?file=APP-07", "main")):
        go(pg, base, route)
        txt = pg.locator(sel).first.inner_text()
        if "2027-28" in txt: bad.append(f"{route}: 2027-28 on screen")
        if route != "/letters" and route != "/?file=APP-07" and "2026-27" not in txt: bad.append(f"{route}: 2026-27 missing")
    go(pg, base, "/case/APP-03/letter")
    shot(pg, "A5", lang)
    return bad


def a6(pg, base, lang):
    bad = []
    for route in ROUTES:
        go(pg, base, route, 300)
        bad += [f"{route}: {x}" for x in pg.evaluate(WRAP_JS, CONTROLS)]
        if pg.evaluate("document.scrollingElement.scrollWidth > innerWidth + 1"):
            bad.append(f"{route}: page scrolls sideways")
        tb = pg.locator(".tabband")
        if tb.count() and tb.evaluate("e => e.scrollWidth > e.clientWidth + 1"):
            bad.append(f"{route}: tab band overflows")
    go(pg, base, "/?file=APP-07")
    shot(pg, "A6", lang)
    return bad


def a6_layout(b, base):
    """Home in Hindi has the same layout as in English (key boxes within 2 px)."""
    sel = [".qpane", ".preview", ".filters", ".qrow", ".pv-head", ".pv-body", ".btn.brand", ".chain2"]
    boxes = {}
    for lang in ("en", "hi"):
        ctx = context(b, lang); pg = ctx.new_page()
        go(pg, base, "/?file=APP-07")
        boxes[lang] = {s: pg.locator(s).first.bounding_box() for s in sel}
        ctx.close()
    bad = []
    for s in sel:
        e, h = boxes["en"][s], boxes["hi"][s]
        if not e or not h: bad.append(f"{s} missing"); continue
        for k in ("x", "width"):
            if abs(e[k] - h[k]) > 2: bad.append(f"{s} {k} en {e[k]:.0f} hi {h[k]:.0f}")
    return bad


def a7(pg, base, lang):
    bad = []
    go(pg, base, "/case/APP-07")
    u = pg.locator(".seg .unavail").first
    u.hover(); pg.wait_for_timeout(250)
    tip = u.locator(".tipbox")
    if not tip.is_visible() or tr("Only for scanned pages. This is a text PDF: its file structure was checked instead.", lang) not in tip.inner_text():
        bad.append("heatmap reason not shown on hover")
    shot(pg, "A7", lang)
    pg.mouse.move(5, 5); u.focus(); pg.wait_for_timeout(150)
    if not tip.is_visible(): bad.append("heatmap reason not shown on focus")
    go(pg, base, "/case/APP-07/letter")
    s = pg.locator(".casehead .unavail")
    if not s.count(): bad.append("seal has no reason (nothing ticked on APP-07)")
    else:
        s.hover(); pg.wait_for_timeout(200)
        if tr("Tick at least one deficiency to seal.", lang) not in s.locator(".tipbox").inner_text(): bad.append("seal reason text")
    return bad


def b1(pg, base, lang, b=None):
    bad = []
    go(pg, base, "/sign-in", 200)
    if pg.locator(".bracket").count() != 4: bad.append("corner brackets")
    if pg.locator(".scan-line .beam-band").count() != 1: bad.append("beam band")
    pg.wait_for_timeout(3300)                                   # step 2: beam at 45%
    read, ticks, red = pg.locator(".sd-line.read").count(), pg.locator(".sd-tick.on").count(), pg.locator(".sd-box.red").count()
    unread = pg.locator(".sd-line:not(.read)").count()
    shot(pg, "B1", lang)
    if not (read >= 4 and ticks == read and red == 1 and unread >= 4): bad.append(f"mid-scan read={read} ticks={ticks} red={red} unread={unread}")
    if pg.locator(".sd-box.green").count(): bad.append("green box before the beam reaches the seal")
    pg.wait_for_timeout(1700)
    if pg.locator(".sd-box.green").count() != 1: bad.append("green box after the beam reached the seal")
    if b:
        ctx = context(b, lang, signed_in=False, reduced=True); p2 = ctx.new_page()
        go(p2, base, "/sign-in", 300)
        if p2.locator(".sd-line:not(.read)").count() or p2.locator(".sd-box").count() != 2 or not p2.locator(".scan-steps li.on").inner_text().endswith(tr("Ready for you", lang)):
            bad.append("reduced motion: should show the final frame")
        ctx.close()
    return bad


def c1(pg, base, lang):
    bad = []
    go(pg, base, "/")
    e = pg.locator(".pv-empty")
    if not e.count() or tr("Select a file from the queue to see it here.", lang) not in e.inner_text() or "j" not in e.inner_text():
        bad.append("empty state")
    if pg.locator(".pv").count(): bad.append("preview shown before a pick")
    shot(pg, "C1", lang)
    pg.locator(".qrow").nth(1).click(); ready(pg)
    m = re.search(r"file=(APP-\d+)", pg.url)
    if not m: bad.append(f"url not updated: {pg.url}")
    else:
        pg.reload(); ready(pg)
        if m.group(1) not in pg.locator(".pv").inner_text(): bad.append("reload lost the pick")
    pg.keyboard.press("j"); pg.wait_for_timeout(300)
    if m and m.group(1) in pg.url: bad.append("j did not move")
    return bad


def c2(pg, base, lang):
    go(pg, base, "/")
    t = pg.locator(".qhead").inner_text()
    shot(pg, "C2", lang)
    bad = [] if ("waiting in your region" not in t and "23" in t) else [f"head: {t[:120]!r}"]
    return bad


def c3(pg, base, lang):
    bad = []
    go(pg, base, "/?file=APP-03")
    main = pg.locator(".pv .btn.primary, .pv .btn.brand")
    if main.count() != 1: bad.append(f"{main.count()} filled buttons in the preview")
    o = pg.locator(".pv .btn.brand")
    if not o.count() or tr("Open full case", lang) not in o.inner_text(): bad.append("Open full case is not the brand button")
    else:
        bb, vb = o.bounding_box(), pg.locator(".pv .viewer").bounding_box()
        if abs(bb["width"] - vb["width"]) > 2 or not (0 <= bb["y"] - (vb["y"] + vb["height"]) <= 20): bad.append(f"position {bb} vs viewer {vb}")
        bg = o.evaluate("e => getComputedStyle(e).backgroundColor")
        if bg != "rgb(46, 93, 70)": bad.append(f"colour {bg}")
    draft = pg.locator(".pv-head .actions > .btn")                         # Assign is inside a wrapper; the role's action is the direct child
    if draft.count() != 1 or "primary" in (draft.first.get_attribute("class") or "") or "brand" in (draft.first.get_attribute("class") or ""):
        bad.append("Draft LoD should be an outline button")
    shot(pg, "C3", lang)
    go(pg, base, "/case/APP-03")
    if pg.locator(".casehead .btn.primary").count() != 1: bad.append("case page lost its gold main button")
    return bad


def c4(pg, base, lang):
    bad = []
    go(pg, base, "/?file=APP-07")
    ch = pg.locator(".pv .chain2")
    done, cur, nxt = ch.locator(".step.done").count(), ch.locator(".step.current").count(), ch.locator(".step.next").count()
    if not (done >= 2 and cur == 1 and nxt >= 1): bad.append(f"steps done={done} current={cur} next={nxt}")
    if ch.locator(".step.next .step-date, .step.current .step-date").count(): bad.append("dates on future steps")
    hashes = ch.locator(".step-hash").count()
    real = pg.evaluate("fetch(location.pathname + 'snapshot/en/cases/APP-07.json').then(r => r.json()).then(d => d.timeline.filter(e => e.real).length)")
    if hashes != real: bad.append(f"hashes {hashes} vs real blocks {real}")
    if ch.locator(".step.done .node svg").count() != done: bad.append("done steps without a check")
    if ch.locator(".chain2-line").count() != 1: bad.append("dotted line")
    if "dotted" not in ch.locator(".chain2-line").evaluate("e => getComputedStyle(e).borderTopStyle"): bad.append("line not dotted")
    shot(pg, "C4", lang)
    go(pg, base, "/case/APP-02/timeline")
    if pg.locator(".chain2 .step").count() < 4: bad.append("timeline tab")
    return bad


def d1(pg, base, lang):
    bad = []
    go(pg, base, "/case/APP-07")
    tab = pg.locator(".tabband a").first.inner_text()
    if not re.search(r"·\s*3\s+" + re.escape(tr("to check", lang)), tab): bad.append(f"evidence tab '{tab}'")
    ck = pg.locator(".tabband a").nth(1).inner_text()
    if "·" not in ck: bad.append(f"checklist tab '{ck}'")
    nl = pg.locator(".nextline").inner_text()
    if not nl.startswith(tr("Next", lang)) or "3" not in nl: bad.append(f"next line '{nl}'")
    if pg.locator(".crumbs a.back .ic").count() != 1: bad.append("back arrow")
    shot(pg, "D1", lang)
    return bad


def d2(pg, base, lang):
    bad = []
    go(pg, base, "/case/APP-07")
    cols = pg.locator(".ev2").evaluate("e => getComputedStyle(e).gridTemplateColumns.split(' ').length")
    if cols != 2: bad.append(f"{cols} columns")
    if pg.locator(".doclist, .note-add, .tamperbox").count(): bad.append("old doc list / notes / tamper box still on Evidence")
    if not re.search(r"\b\d+\s+" + re.escape(tr("of", lang)) + r"\s+\d+\b", pg.locator(".ev-docbar").inner_text()): bad.append("1 of n")
    secs = pg.locator(".isec-title").all_inner_texts()
    if tr("This document", lang) not in secs or not any(s.startswith(tr("Whole file (cross-checks, missing documents)", lang)[:8]) for s in secs): bad.append(f"sections {secs}")
    if pg.locator(".tamperline").count() != 1: bad.append("tamper line")
    if pg.locator(".evbox2 .evnum").count() < 1: bad.append("numbered box")
    pg.locator(".issue", has=pg.locator(".rule", has_text="X-NAME")).click(); pg.wait_for_timeout(700)
    if not pg.locator(".magnifier .lens").is_visible() or pg.locator(".maglines line").count() != 2: bad.append("magnifier")
    else:
        lens, page = pg.locator(".magnifier .lens").bounding_box(), pg.locator(".paper2").bounding_box()
        if lens["x"] < page["x"] + page["width"]: bad.append("callout not right of the page")
        if abs(lens["width"] - lens["height"]) > 1: bad.append("callout not round")
    shot(pg, "D2", lang)
    z = pg.locator(".zoomval")
    pg.get_by_role("button", name=tr("Zoom in", lang)).click(); pg.wait_for_timeout(150)
    z1 = z.inner_text()
    pg.locator(".ev-tools .btn", has_text=tr("Fit", lang)).click(); pg.wait_for_timeout(150)
    if z1 != "125%" or z.inner_text() != "100%": bad.append(f"zoom {z1} -> {z.inner_text()}")
    pg.locator(".docswitch button.select").click(); pg.locator(".docswitch .menu-item").first.click(); pg.wait_for_timeout(400)
    if not pg.locator(".cleanchip").is_visible() or "clean" not in (pg.locator(".paper2").get_attribute("class") or ""): bad.append("clean page")
    if pg.locator(".evbox2").count(): bad.append("boxes on a clean page")
    shot(pg, "D2c", lang)
    go(pg, base, "/case/APP-17")
    pg.locator(".docswitch button.select").click()
    photos = pg.locator(".docswitch .menu-item", has=pg.locator(".ic.t-rev"))
    if photos.count() < 1 or tr("Campus photo", lang) not in photos.first.inner_text(): bad.append("APP-17 photo item with orange icon")
    pg.keyboard.press("Escape")
    ph = pg.locator(".isec", has=pg.locator(".isec-title", has_text=tr("Photos and metadata", lang)))
    if ph.locator(".issue").count() != 4: bad.append(f"photo issues {ph.locator('.issue').count()}")
    ph.locator(".issue").first.click(); pg.wait_for_timeout(500)
    if "photos/APP-17" not in (pg.locator(".paper2 img").first.get_attribute("src") or ""): bad.append("photo issue did not open the photo")
    shot(pg, "D2b", lang)
    return bad


def d3(pg, base, lang):
    bad = []
    go(pg, base, "/case/APP-17")
    first = pg.locator(".isec .issue").first
    fid_title = first.locator(".finding-title").inner_text()
    first.get_by_role("button", name=tr("Correct", lang)).click(); pg.wait_for_timeout(200)
    go(pg, base, "/case/APP-17/letter")
    row = pg.locator(".incl", has_text=fid_title)
    if not row.locator("input").is_checked(): bad.append("Correct did not tick it")
    shot(pg, "D3", lang)
    go(pg, base, "/case/APP-17")
    pg.locator(".isec .issue").first.get_by_role("button", name=tr("False alarm", lang)).click(); pg.wait_for_timeout(200)
    go(pg, base, "/case/APP-17/letter")
    if pg.locator(".incl", has_text=fid_title).locator("input").is_checked(): bad.append("False alarm did not untick it")
    return bad


def d4(pg, base, lang):
    bad = []
    go(pg, base, "/case/APP-17")
    pg.locator(".isec .issue").first.get_by_role("button", name=tr("Correct", lang)).click(); pg.wait_for_timeout(200)
    go(pg, base, "/case/APP-17/letter")
    if pg.locator(".sidecol h3").first.inner_text() != tr("Deficiencies in this letter", lang): bad.append("title")
    if "Handbook quotes" in pg.locator("body").inner_text() or (lang == "hi" and HI.get("Handbook quotes", "@@") in pg.locator("body").inner_text()):
        bad.append("'Handbook quotes' still on screen")
    boxes = pg.locator(".incl input")
    if boxes.count() != 4 or any(boxes.nth(i).is_disabled() for i in range(boxes.count())): bad.append("every item tickable")
    if pg.locator(".letter-paper ol li").count() != 1: bad.append("ticked item not in the letter text")
    boxes.nth(1).check(); pg.wait_for_timeout(150)
    pg.reload(); ready(pg)
    if not pg.locator(".incl input").nth(1).is_checked(): bad.append("tick not remembered")
    seal = pg.get_by_role("button", name=tr("Seal and issue", lang))
    if seal.is_disabled(): bad.append("seal disabled with 2 ticked")
    shot(pg, "D4", lang)
    seal.click(); pg.wait_for_timeout(1500)
    if tr("Sealed and issued.", lang) not in pg.locator(".sealresult").inner_text(): bad.append("seal")
    return bad


def d5(pg, base, lang):
    bad = []
    go(pg, base, "/case/APP-07")
    with pg.expect_download() as dl:
        pg.locator(".casehead a.btn", has_text=tr("Case ZIP", lang)).click()
    p = dl.value.path()
    try:
        names = zipfile.ZipFile(p).namelist()
        if "result.json" not in names or not any(n.startswith("documents/") for n in names): bad.append(f"zip contents {names[:5]}")
    except zipfile.BadZipFile:
        bad.append("not a zip")
    if dl.value.suggested_filename != "APP-07_case.zip": bad.append(dl.value.suggested_filename)
    shot(pg, "D5", lang)
    return bad


def e1(pg, base, lang):
    bad = []
    go(pg, base, "/analytics")
    seg, csv = pg.locator(".page-head .seg.tall").bounding_box(), pg.locator(".page-head .btn", has_text=tr("Export CSV", lang)).bounding_box()
    if abs(seg["height"] - csv["height"]) > 1 or abs(seg["y"] - csv["y"]) > 1 or csv["x"] - (seg["x"] + seg["width"]) > 12: bad.append(f"seg {seg} csv {csv}")
    pg.locator(".seg.tall button").nth(1).click(); pg.wait_for_timeout(200)
    if pg.locator(".an-grid .box").first.locator("table").count() != 1: bad.append("table view")
    shot(pg, "E1", lang)
    return bad


def e2(pg, base, lang):
    go(pg, base, "/analytics")
    t = pg.locator(".kpis").inner_text()
    shot(pg, "E2", lang)
    return [] if tr("Not enough marks yet", lang) in t and "%" not in t.split(tr("Not enough marks yet", lang))[0][-6:] else [f"kpis: {t[:160]!r}"]


def g1(pg, base, lang):
    go(pg, base, "/case/APP-17")
    pg.locator(".isec", has=pg.locator(".isec-title", has_text=tr("Photos and metadata", lang))).locator(".issue").first.click(); pg.wait_for_timeout(400)
    sec = pg.locator(".isec").first.inner_text()
    shot(pg, "G1", lang)
    return [] if tr("This photo's issues are under Photos and metadata.", lang) in sec else [f"section text {sec[:100]!r}"]


def g2(pg, base, lang):
    go(pg, base, "/sign-in")
    vals = pg.locator(".signin-row .dd-val").all_inner_texts()
    shot(pg, "G2", lang)
    return [] if vals and not any(":" in v for v in vals) else [f"values {vals}"]


def g3(pg, base, lang):
    bad = []
    if lang != "hi":
        go(pg, base, "/case/APP-07/timeline"); shot(pg, "G3", lang)
        return bad
    for route, sel in (("/case/APP-07/timeline", ".rail-label, .tabband a, .step-label, .crumbs a, .case-title ~ .meta"),
                       ("/?file=APP-07", ".qhead h1, .filters .dd-val, .pv h3, .chip"), ("/analytics", ".page-head, .seg button, th"),
                       ("/case/APP-03/letter", ".sidecol h3, .sidecol p, .infobox b, .letter-paper > p")):
        go(pg, base, route)
        for el in pg.locator(sel).all():
            tx = re.sub(r"APP-\d+|AICTE|PDF|CSV|ZIP|Ctrl K|Enter|Pramaan AI|F\. No\.|[A-Z][\w-]*-\w+|\b[A-Z]{2,}\b|\d", "", el.inner_text())
            for n in sorted(INSTITUTES, key=len, reverse=True) + sorted(PLACES, key=len, reverse=True):   # whole names first
                tx = tx.replace(n, "")
            tx = re.sub(r"\b(Lane|Road|Street|Market|Ring|Nagar|Main)\b", "", tx)
            if re.search(r"[A-Za-z]{3,}", tx):
                bad.append(f"{route}: English left: {el.inner_text().strip()[:50]!r}")
    go(pg, base, "/case/APP-07/timeline")
    shot(pg, "G3", lang)
    return bad


def g4(pg, base, lang):
    bad = []
    for route in ("/?file=APP-07", "/case/APP-07", "/case/APP-12", "/case/APP-07/letter", "/case/APP-07/checklist"):
        go(pg, base, route)
        txt = pg.locator("main").evaluate("e => { const c = e.cloneNode(true); c.querySelectorAll('.rule, .mono').forEach(x => x.remove()); return c.innerText; }")
        for m in set(re.findall(r"\bMOCK\b|\b[a-z]+_[a-z_0-9]+\b|output/heatmaps", txt)):
            bad.append(f"{route}: '{m}'")
    go(pg, base, "/case/APP-07")
    shot(pg, "G4", lang)
    return bad


def g5(pg, base, lang):
    go(pg, base, "/case/APP-03/letter")
    pg.get_by_role("button", name=tr("Seal and issue", lang)).click(); pg.wait_for_timeout(1500)
    go(pg, base, "/letters")
    row = pg.locator("tr", has_text="APP-03").first
    row.get_by_role("button", name=tr("Verify", lang)).click(); pg.wait_for_timeout(400)
    txt = row.inner_text()
    shot(pg, "G5", lang)
    bad = [] if tr("VALID: matches the hash sealed in this browser (demo). The live app also checks the audit chain.", lang) in txt else [f"verify: {txt[-120:]!r}"]
    return bad + ([] if "Northfield" in txt else ["institute name missing"])


def g6(pg, base, lang):
    go(pg, base, "/case/APP-07/sources")
    pg.locator("tr", has_text="Fire").first.get_by_role("button", name=tr("Preview", lang)).click(); pg.wait_for_timeout(1200)
    pg.locator(".drawer .btn.primary").click(); pg.wait_for_timeout(200)
    shot(pg, "G6", lang)
    go(pg, base, "/case/APP-07/letter")
    return [] if pg.locator(".incl input:checked").count() >= 1 else ["drawer button did not tick the letter"]


def g7(pg, base, lang):
    go(pg, base, "/case/APP-07")
    pg.locator(".issue").first.get_by_role("button", name=tr("Correct", lang)).click(); pg.wait_for_timeout(200)
    f = pg.locator(".issue").first.locator(".finding")
    shot(pg, "G7", lang)
    ok = "confirmed" in (f.get_attribute("class") or "") and f.locator(".btn.on.ok .ic").count() == 1
    return [] if ok else ["confirmed look"]


def g8(pg, base, lang):
    go(pg, base, "/letters")
    n = pg.locator("td.mono, td .mono").evaluate_all("els => els.filter(e => /[\\u0900-\\u097F]/.test(e.innerText)).length")
    shot(pg, "G8", lang)
    return [] if n == 0 else [f"{n} Hindi texts in mono"]


def g9(pg, base, lang):
    go(pg, base, "/analytics")
    k = pg.locator(".kpis, .page-head").all_inner_texts()
    shot(pg, "G9", lang)
    if lang != "hi":
        return []
    bad = [w for w in ("days", "season", "false alarm", "Affidavit 2 stamp") if any(w in x for x in k) or w in pg.locator(".an-grid").inner_text()]
    return [f"English left: {bad}"] if bad else []


CHECKS = {"A1": a1, "A2": a2, "A3": a3, "A4": a4, "A5": a5, "A6": a6, "A7": a7, "B1": b1, "C1": c1, "C2": c2, "C3": c3, "C4": c4,
          "D1": d1, "D2": d2, "D3": d3, "D4": d4, "D5": d5, "E1": e1, "E2": e2, "G1": g1, "G2": g2, "G3": g3, "G4": g4, "G5": g5, "G6": g6,
          "G7": g7, "G8": g8, "G9": g9}


def run(base: str, only: set | None, langs: list[str]) -> dict:
    from playwright.sync_api import sync_playwright
    res = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        for fid, fn in CHECKS.items():
            if only and fid not in only:
                continue
            for lang in langs:
                ctx = context(b, lang, signed_in=fid not in ("B1", "A3", "G2"))
                pg = ctx.new_page()
                try:
                    bad = fn(pg, base, lang, b) if fid == "B1" else fn(pg, base, lang)
                    if fid == "A6" and lang == "hi":
                        bad += [f"layout: {x}" for x in a6_layout(b, base)]
                except Exception as e:
                    bad = [f"error: {type(e).__name__}: {str(e).splitlines()[0][:160]}"]
                    traceback.print_exc(limit=2)
                ctx.close()
                res[f"{fid} {lang}"] = bad
                print(("PASS " if not bad else "FAIL ") + f"{fid} {lang}" + ("" if not bad else ": " + " | ".join(bad[:12])), flush=True)
        b.close()
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5173"); ap.add_argument("--only", default=""); ap.add_argument("--langs", default="en,hi")
    ap.add_argument("--out", default=OUT, help="where the screenshots go (e.g. a scratch folder when checking the live site)")
    a = ap.parse_args()
    OUT = a.out
    r = run(a.base, set(a.only.split(",")) - {""} or None, a.langs.split(","))
    print(f"{sum(not v for v in r.values())} of {len(r)} passed")
