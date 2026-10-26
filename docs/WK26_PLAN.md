# WK26 Plan: Pramaan web app on the approved "Desk" design

> For agentic workers: milestone by milestone (M1..M8). After each: commit "WK26-M<n>: ...", push, Playwright screenshots
> out/deck/wk26_<nn>_<screen>.png at 1440x900, docs/FEATURES.md (Dashboard page = the new route) + STATUS_TODAY.md.

**Goal:** the officer web app exactly as the approved Figma frames (docs/design/*.png, frozen 27 Oct), on the unchanged engine.
**Architecture:** `api/` = FastAPI routers that only call pramaan/ modules (no new business logic). `web/` = React 18 + TS + Vite +
react-router + TanStack Query, plain CSS variables (web/src/styles/tokens.css, light + dark from DESIGN_SYSTEM.md §3), Framer
Motion only for motions A/B/C. One data layer `web/src/data/` with two back ends: live (fetch /api) and demo (static JSON snapshot
from tools/export_snapshot.py + localStorage for actions). The Streamlit dashboard/ is not touched.
**Spec:** the WK26 v2 card + docs/DESIGN_SYSTEM.md + docs/DESIGN_DECISIONS.md + docs/design/*.png.

## Global constraints (copied from the card / design system)
- Engine contracts unchanged; API wraps pramaan/ modules only; no business logic in JS.
- Never "reject", "forged", "fraud", "Rule pack", "11 of 59", em dash. Lanes: Return for rectification, Human review, Clear, Not automated.
- Handbook names only (Regulation Bureau ... Standing Appellate Committee; LoD, LoA, Show Cause Notice, Speaking Order).
- Rail: 5 items. No rule-pack screen, no automation counts, no institute screens.
- Tokens §3; corners 4 px (pop-ups/drawers 6); shadow only on popover/modal/drawer; Material Symbols filled, self-hosted SVG;
  Montserrat 600/700, Roboto 400/500, Roboto Mono 400/500, Noto Sans per script, Noto Nastaliq Urdu; all self-hosted.
- Skeleton loaders on every async view; empty/error states (frame 18); reduced-motion turns motion off.
- Synthetic data only. Demo stays: run_eval 23 apps, recall 1.0, 0 unexpected, 23/23. All Python tests pass.

## Review focus
1. A case whose document has no page image (scan missing) -> "Not automated" state, never an empty viewer.
2. Language with no static table (e.g. Telugu) in demo mode -> English dynamic text + a small note, UI still usable.
3. Urdu: whole layout mirrors (rail on the right), ids/hashes stay LTR.
4. Batch approve when the queue has 0 clear files -> empty state, no modal.
5. Live API down -> source/queue error state with Retry (frame 18), not a blank page.

## Milestones
| M | Deliverable | Verification |
|---|---|---|
| 1 | api/main.py + routers (queue, cases, documents, verification, letters, outbox, calendar, appeals, analytics?role=, search, notes, feedback, assign, evc, docs); tools/export_snapshot.py -> web/public/snapshot/ | tests/test_api.py: every endpoint for APP-02 + APP-07; seal-and-issue verifies with tools/verify_report; notes never in letters |
| 2 | web shell: tokens, fonts, rail, top bar, search (Ctrl K), profile pop-up (6 roles), theme, language (hi, ur RTL), skeletons, demo/live | Playwright: shell renders light/dark/hi/ur |
| 3 | 02 Home, 16 batch approve, 18 states | screenshots vs design |
| 4 | 03-07 + 05b | screenshots vs design |
| 5 | 08, 09, motion B + C | seal round trip in the browser |
| 6 | 01 + motion A, 10, 11, 12 (role scope), 14, 15, 17 | screenshots |
| 7 | Playwright flows, axe-core, banned-things grep, design diff list (docs/A11Y_REPORT.md) | reports |
| 8 | GitHub Action -> GitHub Pages (demo build), README run instructions | workflow file + build passes locally |
