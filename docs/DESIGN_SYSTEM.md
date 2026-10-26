# Pramaan AI: design system and page spec (front end)
The single source for the front-end build. Read with DESIGN_DECISIONS.md (the decision log).
Status: Step 2 drawn and revised on 27 Oct. Waiting for final approval, then FROZEN.
Figma: https://www.figma.com/design/098H6dN6COyGiJHCyN8xbb?node-id=24-2 (page "Step 2: All pages (Desk)"; Nishchal's student plan).
Labels: everything here is designed, not built. All names and figures on screens are synthetic demo data.

## 1. Principles
- Apple-like: simple, functional, cohesive, modern with a little retro. Function over form, with a little flash.
- For AICTE officials only (verification part of the AICTE portal). No institute screens. Desktop only (1440 x 960 design size).
- The AI is advisory: every screen says or shows that the officer decides.
- Status is never colour alone: colour + icon + text, always.
- Calm work screens. Motion only where it explains something, plays once, and is off when the computer asks for reduced motion.

## 2. Layout: "Desk" (approved Option 3)
- Icon rail, 72 px, left: logo mark (36 px) on top, then My queue, Calendar, Letters, Appeals, Analytics (no Rule pack item; removed 27 Oct). Icon 22 px + label 10 px. Active item: surface2 tile, brand icon, Medium label.
- Top bar, 60 px, bottom border: wordmark "Pramaan AI" ("AI" in gold), search (480 px, "Search Permanent Id, institute, rule or document", Ctrl K hint), then on the right: theme toggle (36 px square), language dropdown (translate icon + language name), round avatar (36 px, brand fill, 2 px gold ring, initials).
- Home: queue list pane (420 px) on the left + the selected file's preview on the right.
- Case pages: case header (breadcrumb, institute name 26 px, meta line, actions) + summary strip (lane chip, trust score bar, checklist counts, assignee, due), then the TAB BAND.
- Tab band (rev. 27 Oct): its own full-width band below the header. Light #E8E4D8 with a #D9D4C5 bottom line; dark #1C2621 with a #2B3832 line. Active tab: text colour + Medium + 2 px gold underline. Tabs: Evidence, Checklist, Verification sources, Changes since 2025, Resubmission, Letters, Notes, Timeline.
- Site footer (17 Privacy page, rev. 27 Oct): band surface2, top border. Row 1: wordmark + "Document verification for the AICTE portal" | Privacy and data use · Terms of use · Accessibility statement · Help. One row only (rev. 2, 27 Oct): no second line.

## 3. Colour tokens (light / dark)
| Token | Light | Dark | Use |
|---|---|---|---|
| bg | #F8F7F1 (Paper) | #111915 | page background (never pure white) |
| surface | #FCFBF7 | #17211C | panels, tables, rail |
| surface2 | #F0EEE5 | #1E2A24 | header rows, selected rows, active rail item |
| band | #E8E4D8 | #1C2621 | case tab band |
| border | #E3E0D4 | #2B3832 | all 1 px lines |
| text | #1B2A22 | #ECEBE3 | body text |
| muted | #5D6A63 | #9BA7A0 | secondary text |
| brand | #2E5D46 (Forest Green) | #8CC2A4 | wordmark, links, icons |
| brandSolid | #2E5D46 | #1F3A2D | avatar, solid green areas |
| gold | #D4A247 (Antique Gold) | #D9AE5C | primary buttons, active underline, logo gear |
| goldText | #8A6418 | #E3BC6E | eyebrows, gold text on paper |
| onGold | #1B2A22 | #1B2A22 | text on gold buttons |
| return (ret) | #B42318, bg #FDF0EE | #F97066, bg #3A1916 | Return for rectification |
| review (rev) | #B54708, bg #FEF6E7 | #FDB022, bg #3A2A10 | Human review |
| clear (clr) | #067647, bg #EAF7EF | #47CD89, bg #10301F | Clear |
| not automated (na) | #667085, bg #F0F1F3 | #98A2B3, bg #262B30 | Not automated |
| page | #FFFEFA | #E9E7DE | document paper inside viewers (stays light in dark mode) |
| sign-in panel | #2A5641 | (same) | right half of the sign-in page |

## 4. Type
- Montserrat SemiBold: page titles 26-36 px (two-line headings: line 1 text colour, line 2 muted), brand. Montserrat Bold for the wordmark.
- Roboto Regular 13-16 px: body and tables. Roboto Medium 11-15 px: labels, buttons, chips.
- Roboto Mono Medium/Regular: ids (APP-07), rule ids, hashes (#a3f9c1), scores.
- Eyebrow: Roboto Medium 11-12 px, letter-spacing 8%, goldText, upper case (e.g. "REGULATION BUREAU · NORTHERN").
- Indian scripts: Noto Sans per script (Noto Sans Devanagari etc.).
- Copy: plain sentences. No em dashes, no slogans, no exclamation marks.

## 5. Shape, icons, effects
- Corners 4 px (pop-ups and drawers 6 px; chips 4 px). 1 px borders.
- No shadows, except pop-ups, modals and drawers: one soft shadow (y 8, blur 28, 10-12% black).
- Icons: Material style, filled, 14/16/18/20/22/24 px. Never Lucide, never sparkles, no emojis.
- Lane chips: icon + label on the tinted bg. Return = undo arrow, Human review = eye, Clear = check circle, Not automated = minus circle.
- Buttons: primary = gold fill + onGold Medium 14; secondary = 1 px border, text colour; small = 11 px pill with border (Correct / False alarm, Preview).
- "demo adapter" tag: 10 px goldText on a 1 px goldText outline, next to any source that is MOCK.

## 6. Motion (designed)
- A · Scan (sign-in page, rev. 27 Oct): a 4-keyframe Smart Animate loop on the right 60% of the sign-in page.
  1. Read: the scan line starts at the top. 0.6 s, then 1.0 s ease-in-out.
  2. Check: the line is at 45%. The red box and the "Expiry date has passed" tag fade in. 0.8 s, then 1.0 s.
  3. Cross-check: the line is at 93%. The green box and the "Seal matches" tag fade in. 0.8 s, then 0.6 s ease-out.
  4. Ready for you: the lane chip "Return for rectification" and the checklist card (11 passed · 1 to check · 2 to return) appear. Hold 2.4 s, then dissolve back to 1.

  A step row (Read, Check, Cross-check, Ready for you) and a one-line caption follow along.
- B · Seal: the gear turns 36° once (900 ms, ease-out) and the badge fills in. Used as the loading mark and after "Seal and issue".
- C · Chain: a new audit block slides 8 px into place and its hash appears (300 ms).
- No hover animations, no animated arrows. Skeleton rows while loading.

## 7. Pages (Step 2 inventory)
- 01 Sign in (rev. 2). Designed at 1440 x 820 so it fits a laptop screen; in the build it is exactly one screen high (100vh, no scroll) and the sign-in block is centred vertically. Left 40% (576 px), the sign-in panel:
  - logo and wordmark (inside the centred block, not pinned to the top);
  - "Welcome back. / Sign in to start checking.";
  - two lines on what Pramaan does;
  - gold "Continue with AICTE portal sign-in";
  - "Signing in as" (role) and "Language" dropdowns;
  - footer links.

  Right 60% (864 px): the scan animation (keyframes 1-4) on #2A5641, with texture inside the 30-item rules: two faded pages stacked behind the document ("14 documents in this file"), and two large gear outlines in Paper at 4-5% opacity, partly off the edge. No gradients, orbs or dot grids.
- 02 Home: my queue (Option 3).
- 03 Case view: Evidence. Document list | viewer with evidence boxes, tamper heatmap toggle | findings (Correct / False alarm), tamper check, internal notes.
- 04 Checklist: 14 required documents, status, what Pramaan found, source, officer action.
- 05 Verification sources (rev.). Six sources, each with what was asked, the answer, when and the result, plus a **Preview** button per row ("Nothing to show" when the source isn't connected).
- 05b Preview open (new). A right-side drawer (560 px) shows exactly what the source sent back (DigiLocker shown):
  - the returned document, with an evidence box;
  - a key-value list (document id, issued to, academic year, issued by, received, answer hash);
  - buttons: Add to Letter of Deficiency, Open full size, Download.
- 06 Changes since 2025 (year over year).
- 07 Resubmission: "3 of 4 issues fixed", before/after.
- 08 Letter editor: Letter of Deficiency, Handbook quotes, Seal and issue (+ dark).
- 09 Letters and outbox · 10 Calendar · 11 Appeals tracker (Standing Appellate Committee, 7-day window) · 12 Analytics. One layout for every role; only the scope and the figures change (no extra design): officer = "my numbers" for own region (files done, time per file, false alarms marked, due soon); committees = files at their stage; leadership = all regions (the frame shown).
- 13 Rule pack admin: REMOVED on 27 Oct (team decision). Do not show automation counts anywhere.
- 14 Search + saved filters · 15 Expert Visit Committee visit pack · 16 Batch-approve with random spot check.
- 17 Privacy / Terms / Accessibility (+ site footer, rev.) · 18 States (empty, unreadable scan, source down, loading).
- Dark: 03 Case view, 08 Letter editor.
- Shared (Step 1 page): profile pop-up "Who is checking the documents right now?" with the six Handbook roles; motion storyboard; tokens.

## 8. Never (the 30-item list)
- No gradients, glass, radial orbs, dot grids or neon.
- No purple-and-black, no pastels, no pure white backgrounds.
- No Lucide or sparkle icons, no emojis.
- No Inter, Geist or Space Grotesk.
- No checkmark bullets, three-card rows, bento grids, coloured left stripes, terminal mockups, big corner radius or pricing tiers.
- No em dashes, no "it's not X, it's Y", no fake testimonials.
- No animated arrows, no hover animations.
- Must have: skeleton loaders, real-looking (labelled) data, and Privacy, Terms and Accessibility.

## 9. Content rules
- Never "reject", "forged" or "fraud". The lanes are: Return for rectification, Human review, Clear, Not automated.
- Use the Handbook's names: Regulation Bureau, Scrutiny / Re-Scrutiny Committee, Expert Visit Committee, Standing Hearing Committee, Executive Committee, Standing Appellate Committee; Letter of Deficiency, Letter of Approval, Show Cause Notice, Speaking Order.
- Mocked integrations are always tagged "demo adapter".
- Do not show weak measured numbers as headlines. Rule automation counts are never shown.
