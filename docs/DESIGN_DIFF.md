# Built screens vs the approved frames (WK26 M7)
Compared each out/deck/wk26_<nn>_*.png with docs/design/<nn>_*.png by eye (1440 wide). Layout, tokens, type, chips, the tab band,
buttons and the three motions follow DESIGN_SYSTEM.md. The differences below are data, a missing drawing, or a rule that wins.

## Differences caused by the real (synthetic) data
- 02 / 03: frames show "Shivalik Institute of Engineering" and 14 documents per file; the demo files have 7-8 documents and
  synthetic institute names. All 23 cases fall due in the same few days (the demo's SLA dates), so "Due" words repeat.
- 04 Checklist: the frame lists 14 documents; the engine's checklist has 14 requirement rows (Annexure-2 2.1 i.-viii., NOC, area,
  previous EoA letter, photos, cross-document consistency, land). Same table, the engine's rows.
- 05 Verification sources: "Asked 6 outside sources"; the engine answers from 9-10 rows per file (AICTE records, signature check,
  university repository, fire department, municipal register, NBA, DigiLocker per document, serial register, map check, Registrar
  of Societies "Check by hand").
- 06 Changes since 2025: the frame has 12 fields (faculty, library volumes, bank account...); the MOCK prior-year record holds
  intake per programme, built-up area, institute name and address, so those rows are shown.
- 07 Resubmission: the frame says "3 of 4 issues fixed"; the only demo resubmission (APP-19 of APP-02) is "1 of 1 issues fixed"
  with one new issue.
- 08 Letter editor: the frame says "59 of 59 quotes in the rule pack match (measured)"; the build shows the measured figure for
  this rule pack (7 of 7 distinct Handbook quotes match word for word) and words it without "rule pack".
- 09 Letters: the frame shows Show Cause Notices and Letters of Approval; the engine drafts Letters of Deficiency (sealed) and
  Letters of Approval (batch approve, MOCK outbox); Show Cause Notices are not generated yet.
- 10 Calendar: events come from the engine (due dates, certificate expiries, appeal windows, spot check); no EVC visits or
  hearings are scheduled in the demo data.
- 11 Appeals: the frame shows four appeals with outcomes; the demo has the appeal window of the one sealed letter (APP-02).
- 12 Analytics: the frame's figures (1,284 files, 8 weeks) are placeholders; the build shows the 23 synthetic files over the
  weeks they were submitted, labelled synthetic.
- 14 Search: the frame shows 6 results for "fire expired" across a larger set; the demo has 1 (APP-03).

## Not in the design (built from the tokens and the closest drawn pattern)
- Profile pop-up: drawn on the Step 1 page (not exported); built from the written spec (heading, 6 roles, theme, sign out).
- Batch approve trigger on Home: "Approve clear files (N)" small button under the filters (frame 16 shows only the modal).
- The spot check inside the modal: an "Open" button shows the picked file inline, then "I opened it and agree".
- Letters and outbox: an "Outbox" sub-tab listing the MOCK messages.
- Letter editor: language dropdown values; Human review items can be added by the officer (live mode).
- Analytics: "Table view" toggle and hatched Human review bars (accessibility: the design's Return / Human review colours are too
  close for colour-blind readers, see STATUS).
- Case tabs Letters / Notes / Timeline: built as plain tables with the chain blocks (not drawn).
- Demo mode pill in the top bar; the "/states" review page showing the four states side by side (frame 18).

## Rules that override a frame
- Frame 15 shows a three-item rail (Visits, Calendar, Reports) for the Expert Visit Committee; the card says the rail has five
  items and the layout is the same for every role, so the EVC sees the same five-item rail.
- Token change for contrast: "Not automated" text #667085 -> #5E6779 and a darker tab text on the band (WCAG AA 4.5:1).
