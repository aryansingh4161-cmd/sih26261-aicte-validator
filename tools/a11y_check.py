"""WK26 accessibility check: axe-core (WCAG 2 A + AA rules) on every route of the web app, light and dark.
Needs the app running (demo: npm --prefix web run dev -- --mode demo; or live). Writes docs/A11Y_REPORT.md.
  python -m tools.a11y_check [--base http://127.0.0.1:5173] [--out docs/A11Y_REPORT.md]"""
from __future__ import annotations

import argparse
import json
from collections import Counter

ROUTES = ["/sign-in", "/", "/case/APP-07", "/case/APP-07/checklist", "/case/APP-07/sources", "/case/APP-20/changes",
          "/case/APP-19/resubmission", "/case/APP-07/letters", "/case/APP-07/notes", "/case/APP-07/timeline", "/case/APP-03/letter",
          "/letters", "/calendar", "/appeals", "/analytics", "/search?q=fire", "/visit/APP-15", "/privacy", "/terms", "/accessibility", "/states"]


def run(base: str) -> dict:
    from playwright.sync_api import sync_playwright
    axe = open("web/node_modules/axe-core/axe.min.js").read()
    out = {}
    with sync_playwright() as p:
        b = p.chromium.launch(channel="chrome", headless=True)
        for theme in ("light", "dark"):
            for r in ROUTES:
                ctx = b.new_context(viewport={"width": 1440, "height": 900})
                signed = "" if r == "/sign-in" else "yes"
                ctx.add_init_script(f"try{{localStorage.setItem('pramaan.signedIn','{signed}');localStorage.setItem('pramaan.theme','{theme}');}}catch(e){{}}")
                pg = ctx.new_page()
                pg.goto(f"{base}/#{r}", wait_until="networkidle")
                for _ in range(40):
                    if pg.locator(".skel").count() == 0 or r == "/states":
                        break
                    pg.wait_for_timeout(250)
                pg.wait_for_timeout(500)
                pg.add_script_tag(content=axe)
                res = pg.evaluate("async () => (await axe.run(document, {runOnly: {type: 'tag', values: ['wcag2a','wcag2aa','wcag21a','wcag21aa']}})).violations"
                                  ".map(v => ({id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length, target: v.nodes.slice(0,2).map(n => n.target.join(' '))}))")
                out[f"{theme} {r}"] = res
                ctx.close()
        b.close()
    return out


def report(res: dict, path: str) -> Counter:
    tally = Counter(v["impact"] for vs in res.values() for v in vs)
    lines = ["# Accessibility report (axe-core, WCAG 2.0 / 2.1 A + AA rules)", "",
             f"Routes checked: {len(res)} ({len(res) // 2} routes x light and dark). Tool: tools/a11y_check.py (measured).", "",
             "| Impact | Count |", "|---|---|"] + [f"| {k} | {tally.get(k, 0)} |" for k in ("critical", "serious", "moderate", "minor")] + ["",
             "## Per route", "", "| Route | Violations |", "|---|---|"]
    for r, vs in res.items():
        lines.append(f"| {r} | " + ("none" if not vs else "; ".join(f"{v['impact']}: {v['id']} ({v['nodes']})" for v in vs)) + " |")
    details = {v["id"]: v for vs in res.values() for v in vs}
    if details:
        lines += ["", "## Rules that fired", ""] + [f"- **{k}** ({v['impact']}): {v['help']}. Example: `{v['target'][0] if v['target'] else ''}`" for k, v in details.items()]
    open(path, "w").write("\n".join(lines) + "\n")
    return tally


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:5173"); ap.add_argument("--out", default="docs/A11Y_REPORT.md")
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    res = run(a.base)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    t = report(res, a.out)
    print(dict(t))
    for r, vs in res.items():
        for v in vs:
            if v["impact"] in ("serious", "critical"):
                print(r, v["impact"], v["id"], v["nodes"], v["target"][:1])
