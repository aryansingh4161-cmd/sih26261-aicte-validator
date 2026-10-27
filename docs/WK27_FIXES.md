# WK27 fixes: one row per fix, worked top to bottom
Result (measured, 27 Oct): tools/wk27_check.py 56 of 56 checks PASS (28 rows x English and Hindi) on the demo build;
tests/test_web_flows.py 4 of 4 PASS on the live stack. The same 56 checks PASS on the deployed site
(https://aryansingh4161-cmd.github.io/sih26261-aicte-validator/). Walkthrough screenshots: out/review/wk27/walk_<lang>_<nn>_<step>.png.

A row is **verified** only when a Playwright screenshot in English and Hindi (out/review/wk27/<ID>_en.png, <ID>_hi.png) shows the
acceptance check passing, or a Playwright test asserts it (tests/test_web_flows.py live, tools/wk27_check.py demo build).

| ID | What | Where | Acceptance check | Status | Evidence |
|---|---|---|---|---|---|
| A1 | Logo (rail) and wordmark (top bar) go to Home | Shell.tsx | From /calendar, clicking the logo and the wordmark lands on #/ (my queue) | verified | out/review/wk27/A1_en.png, A1_hi.png; tools/wk27_check.py A1 PASS en + hi |
| A2 | Rail expand / collapse toggle at the bottom, remembered | Shell.tsx, components.css | Toggle widens the rail to about 220 px with icon + full name; a reload keeps the choice | verified | out/review/wk27/A2_en.png, A2_hi.png; tools/wk27_check.py A2 PASS en + hi |
| A3 | Dropdowns: menu max 320 px scrolling inside, flips up, value never wraps | Dropdown (components/ui.tsx), Shell LanguageMenu, AssignMenu, Evidence DocSwitcher | Sign-in language menu opens upward with its own scroll, page scrollTop stays 0; dropdown value is one line with a tooltip | verified | out/review/wk27/A3_en.png, A3_hi.png; tools/wk27_check.py A3 PASS en + hi |
| A4 | Sentence case; no raw internal names; no "derived" hash | case.tsx, More.tsx, api/views_case.py | No "lane human_review", "officer.se" or "derived" on screen; timeline steps and table cells start with a capital, rest lower case (Handbook names excepted) | verified | out/review/wk27/A4_en.png, A4_hi.png; tools/wk27_check.py A4 PASS en + hi |
| A5 | Application year as filed: "Extension of Approval 2027-28" (reverted from the 2026-27 display on request) | config/settings.yaml academic_year_shown = {} | Case header, letter subject and F. No. show 2027-28, matching the documents; the previous Extension of Approval letter (supporting document) shows 2026-27 | verified | out/review/wk27/A5_en.png, A5_hi.png, A5b_en.png, A5b_hi.png (previous letter preview); tools/wk27_check.py A5 PASS en + hi; tests/test_api.py |
| A6 | Hindi first-class: no label wraps; layout same as English | components.css, base.css | Script check: no button, chip, tab, dropdown, table header or rail label renders on 2 lines in Hindi on any route; Home in Hindi matches the English layout | verified | out/review/wk27/A6_en.png, A6_hi.png; tools/wk27_check.py A6 PASS en + hi; layout en vs hi compared box by box |
| A7 | One tooltip for unavailable controls | ui.tsx (Unavailable) | Hover or focus on an unavailable control shows the reason (heatmap on a text PDF, Seal with nothing ticked) | verified | out/review/wk27/A7_en.png, A7_hi.png; tools/wk27_check.py A7 PASS en + hi |
| B1 | Sign-in animation reads as scanning | SignIn.tsx, components.css | Corner brackets, beam with a trailing band, lines turn to read ink behind the beam, margin ticks, boxes appear when the beam reaches them; 4 steps and timings kept; off under reduced motion | verified | out/review/wk27/B1_en.png, B1_hi.png; tools/wk27_check.py B1 PASS en + hi; reduced motion checked |
| C1 | Home preview empty until a file is picked; URL updates | Home.tsx | Fresh Home shows the gear mark + "Select a file from the queue to see it here." + hint; clicking a file sets #/?file=APP-07 and a reload keeps it | verified | out/review/wk27/C1_en.png, C1_hi.png; tools/wk27_check.py C1 PASS en + hi |
| C2 | No "23 files waiting in your region" line | Home.tsx | Line gone; "Your queue. / 23 waiting." stays | verified | out/review/wk27/C2_en.png, C2_hi.png; tools/wk27_check.py C2 PASS en + hi |
| C3 | "Open full case" is the one main button of the preview | Home.tsx, components.css | Filled forest-green full-width button under the document; Draft Letter of Deficiency is an outline button; exactly one filled button in the preview | verified | out/review/wk27/C3_en.png, C3_hi.png; tools/wk27_check.py C3 PASS en + hi |
| C4 | Audit chain as nodes on a dotted line | case.tsx ChainTimeline (Home + Timeline tab) | Done = brand circle + check + date; current = gold ring; next steps hollow dashed, no date; hash only on real audit blocks; line draws in once (off under reduced motion) | verified | out/review/wk27/C4_en.png, C4_hi.png; tools/wk27_check.py C4 PASS en + hi |
| D1 | Quiet guidance on case pages | Case.tsx | Tabs show "Evidence · n to check", "Checklist · n to check"; one muted "Next: ..." line under the strip; back arrow on "My queue" | verified | out/review/wk27/D1_en.png, D1_hi.png; tools/wk27_check.py D1 PASS en + hi |
| D2 | Evidence tab: viewer + one issues panel | Evidence.tsx, case.tsx, api/views_case.py | Two columns; document switcher with 1 of n and prev/next; sections This document / Photos and metadata / Whole file; numbered issues jump to their box; toolbar switch, zoom, pan, page; heatmap inactive on text PDFs with tooltip; numbered boxes; magnifier callout; clean page green outline + chip; APP-17 photo findings under a listed photo item with an orange icon | verified | out/review/wk27/D2_en.png, D2_hi.png; tools/wk27_check.py D2 PASS en + hi; also D2b (APP-17 photo), D2c (clean page) |
| D3 | Correct carries into the letter | actions.ts, LetterEditor.tsx | Correct ticks the item in the Letter of Deficiency; False alarm unticks it; demo (localStorage) and live (feedback API) | verified | out/review/wk27/D3_en.png, D3_hi.png; tools/wk27_check.py D3 PASS en + hi; live: tests/test_web_flows.py photo_correct_letter |
| D4 | Letter editor: "Deficiencies in this letter", all tickable, no Handbook quotes box, seal rule | LetterEditor.tsx, api/views_case2.py | Title + subline; every item tickable and remembered; no "Handbook quotes" text; Seal enabled with 1+ ticked, tooltip otherwise; Playwright APP-17: Correct -> ticked -> sealed | verified | out/review/wk27/D4_en.png, D4_hi.png; tools/wk27_check.py D4 PASS en + hi; live: tests/test_web_flows.py photo_correct_letter |
| D5 | Case ZIP works on the demo site | tools/export_snapshot.py, Case.tsx | Demo Case ZIP button downloads snapshot/zips/<APP>.zip (officer copy); total size reported | verified | out/review/wk27/D5_en.png, D5_hi.png; tools/wk27_check.py D5 PASS en + hi; 23 ZIPs = 1.6 MB, snapshot 20 MB in all (was 18 MB), no image compression needed |
| E1 | Analytics "Chart / Table" segmented switch next to Export CSV, same height | Analytics.tsx | Switch height = Export CSV height; table view toggles | verified | out/review/wk27/E1_en.png, E1_hi.png; tools/wk27_check.py E1 PASS en + hi |
| E2 | Hide "marked false alarm" % under 20 marks | api/views_global.py | With fewer than 20 officer marks the KPI reads "Not enough marks yet" | verified | out/review/wk27/E2_en.png, E2_hi.png; tools/wk27_check.py E2 PASS en + hi |
| F1 | Demo rebuilt and live | GitHub Pages | Live URL serves the new build (C1 empty state visible) | verified | Pages run 40487804102 (7f9d041) success; tools/wk27_check.py --base https://aryansingh4161-cmd.github.io/sih26261-aicte-validator 56 of 56 PASS; out/review/wk27/F1_en.png, F1_hi.png (live Home) |

## Walkthrough rows (G)
| ID | What | Where | Acceptance check | Status | Evidence |
|---|---|---|---|---|---|
| G1 | Viewing a campus photo, "This document" said "No problems found" while the photo had 4 issues in the section below | Evidence.tsx | On a photo, the section points to "Photos and metadata (n)" | verified | out/review/wk27/G1_en.png, G1_hi.png; tools/wk27_check.py G1 PASS en + hi |
| G2 | Sign-in dropdowns repeated their field label ("Signing in as" / "Role: Regulation Bureau") | SignIn.tsx | Dropdowns show the value only; the field label stays above | verified | out/review/wk27/G2_en.png, G2_hi.png; tools/wk27_check.py G2 PASS en + hi |
| G3 | Hindi: machine translations that read wrong for an officer ("Why this lane" as "why this street", "Trust" as "keep faith", "Clear" as "clean up", "Letters" as alphabet letters, "Assign" as "appoint"); tab, rail and timeline labels missing from the table (kept in arrays the scanner did not see); strings with escaped quotes never matched | config/i18n/hi_reviewed.json, tools/build_translations.py | Reviewed Hindi wins over the machine translation; the scanner reads label arrays, ternaries and unescapes quotes; every rail item, tab and timeline step shows in Hindi | verified | out/review/wk27/G3_en.png, G3_hi.png; tools/wk27_check.py G3 PASS en + hi |
| G4 | Raw engine text on screen: "(MOCK Fire department portal)", "institute_name: ...", "differs on fire_cert", heatmap file paths | api/ctx.py plain(), clean_reason() | Display text reads "(Fire department portal, demo adapter)", "Institute name:", "fire safety certificate"; rule ids untouched | verified | out/review/wk27/G4_en.png, G4_hi.png; tools/wk27_check.py G4 PASS en + hi |
| G5 | Demo: a letter sealed in this browser said "Not sealed yet" on Verify in Letters, and showed no institute | Letters.tsx, actions.ts | Verify recomputes the hash of the sealed text in the browser and says VALID (demo); the row shows the institute; PDF explains why it is unavailable | verified | out/review/wk27/G5_en.png, G5_hi.png; tools/wk27_check.py G5 PASS en + hi |
| G6 | 05b drawer "Add to Letter of Deficiency" only changed its own label | Sources.tsx | The button ticks the findings behind that source in the letter (same tick as the editor); with nothing behind it, it explains why | verified | out/review/wk27/G6_en.png, G6_hi.png; tools/wk27_check.py G6 PASS en + hi |
| G7 | After pressing Correct it was hard to see which findings were confirmed | case.tsx, components.css | A confirmed finding has a green Correct button with a check and a green edge; a false alarm is greyed | verified | out/review/wk27/G7_en.png, G7_hi.png; tools/wk27_check.py G7 PASS en + hi |
| G8 | Hindi "not sealed" in the Letters hash column used the mono font (letters spread apart) | Letters.tsx | Mono only on the hash itself | verified | out/review/wk27/G8_en.png, G8_hi.png; tools/wk27_check.py G8 PASS en + hi |
| G9 | Analytics in Hindi: "14 days", "season" as weather season, the false-alarm label and a return reason stayed English | api/views_global.py, hi_reviewed.json | KPI value and headline built from translated words; reviewed Hindi | verified | out/review/wk27/G9_en.png, G9_hi.png; tools/wk27_check.py G9 PASS en + hi |

## Decisions written down
- A4: Handbook document names keep their capitals where the engine writes them in rule titles and letters (Fire Safety Certificate,
  Structural Stability Certificate, Occupancy / Completion Certificate, University NOC Format 2), like the other Handbook names; the
  engine's tests pin that wording. UI labels of the same documents (document switcher, tabs) are in sentence case. Table headers and
  calendar weekday labels are now sentence case too (they were upper case by CSS); the gold eyebrows stay upper case by design.
- A5 (revised 27 Oct): the screens show the application year as filed, 2027-28, so the case header, letter subject and F. No. match
  the documents. The previous Extension of Approval letter stays 2026-27: it is a supporting document from the year before.
  `academic_year_shown` in config/settings.yaml is empty; a {"filed": "shown"} mapping there would change the display only.
- C4: "current" is the first step not done yet (the open appeal window when there is one, else the letter, else the decision).
- D2: issues are numbered once for the whole file (documents in order, then photos, then whole-file items), so the number on a box
  never changes when the officer switches documents. Cross-check findings sit under "Whole file" even when they point at one page;
  clicking them still opens that page and box.
- D3: a tick the officer sets by hand is kept (browser storage, both modes); a later Correct / False alarm mark on that finding resets
  the tick so the letter follows the mark. In live mode the mark goes to the feedback API and is also kept in the browser, so the
  letter follows it at once (before the case view is fetched again).

## Not fixed here (bigger items)
- Demo mode seals with a hash kept in the browser; the QR seal, outbox, audit block and appeal window need the live server (said on
  screen).
- Hindi: UI words are reviewed; engine text inside findings and letters (reasons, deficiency wording) is IndicTrans2 output, read on
  the walkthrough screens but not reviewed line by line by a Hindi-speaking officer. Bengali, Tamil and Marathi got the new strings by
  machine translation only (not reviewed; not worse than before).
- Two engine titles still carry document names in Handbook capitals ("Fire Safety Certificate expired"); see the A4 decision.

