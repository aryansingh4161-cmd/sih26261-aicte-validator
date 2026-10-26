# DESIGN_DECISIONS: the front end (living file; read before ANY design or front-end step)
Owner: Nishchal. Approvers: Nishchal + Jasraj + Aryan. Last update 27 Oct 03:20.

## Gate (binding)
- Nothing on the dashboard or front end is built, and no worker prompt is written, without explicit approval.
- Two-step approval:
  1. Pick one of 3 home-page options (Figma).
  2. Approve ALL pages in that style (Figma).
  Only then is the worker card written.
- WK26 draft withdrawn. The Streamlit dashboard stays as a backup and is not to be touched.

## Scope
- AICTE officials only. A module "integrated with / designed for integration with the AICTE portal" (PS wording). No institute-facing screens. The institute self-check stays a back-end service with no UI.
- "End-to-end" = the full document-verification part of the portal, not the whole AICTE website.
- Desktop web only. No mobile for now.
- Live link: nice to have, free hosting only.

## Official roles and terms (from the Handbook, APH 2024-27, cl. 1.8, 1.9, 2.23, 2.24, 2.25, Table 2.3)
- **Regulation Bureau**: processes applications, informs schedules, places Standing Hearing Committee recommendations and approved intake before the Executive Committee (cl. 1.8 b, 2.24 d, 2.25).
- **Scrutiny Committee / Re-Scrutiny Committee**: verify the authenticity of documents; deficiencies are communicated through the AICTE Web-Portal (cl. 1.8).
- **Expert Visit Committee (EVC)**: after Scrutiny/Re-Scrutiny (cl. 1.9, 2.23.2).
- **Standing Hearing Committee (SHC)**: institutes submit compliance for shortcomings; recommendations go to the Executive Committee (cl. 2.23.3).
- **Executive Committee (EC)**: decides; the decision is uploaded to the Web-Portal with a detailed Speaking Order (cl. 2.23.3); ratified by the Council.
- **Standing Appellate Committee (SAC)**: appeals to the Council within 7 days of uploading the decision (cl. 2.24).
- Letters: Letter of Deficiency (LoD), Letter of Approval (LoA), Speaking Order, Show Cause Notice.
- NOTE (Table 2.3): "Extension of Approval based on Self-Disclosure" goes through Self-Disclosure only, with NO Scrutiny step. Increase in intake, new programme, change of site and similar go through Scrutiny/Re-Scrutiny -> EVC -> SHC/SAC as applicable.
  So for plain EoA the Regulation Bureau desk is where Pramaan's first pass matters most.
- Profiles in the pop-up (use these exact names): Regulation Bureau; Scrutiny / Re-Scrutiny Committee; Expert Visit Committee; Standing Hearing Committee; Executive Committee; Standing Appellate Committee. (Admin = rules, inside Regulation Bureau, unless told otherwise.)
- Pop-up heading: "Who is checking the documents right now?" (subline: "Choose your role to see your view.")
- Per-profile differences are SMALL: the summary line on top ("Forwarded to you by the Standing Hearing Committee: 12 cases"), the default queue filter and the primary action. Same layout for everyone. No separate dashboards.

## Home page (for every officer)
- The home page = the officer's PENDING WORK queue. Not a "today/deadlines" overview.
- It must look good and intuitive; feature-rich but not cluttered.

## Look and feel
- Apple design philosophy: simple yet functional, cohesive, modern with a little retro, everything works.
- Density: a middle ground between calm (Mail-like) and editorial (more air): breathable, legible, function over form, with a little flash.
- Light AND dark mode, with a toggle the officer can reach.
- Language: a visible dropdown in the top bar, left of the circular profile icon (top right). Shown as a feature, not hidden.
- Profile: a circular avatar at top right -> the pop-up with the profiles above.
- Cool factor (very subtle, government-appropriate; judge each one, drop anything over the top):
  - A: the scan. A document page with a light line revealing evidence boxes / heatmap; entry/profile screen only.
  - B: the seal. The logo gear turns once and settles; reused as the loading mark.
  - C: the chain. Audit blocks clicking into place on the case timeline.
  - Lando Norris site reference: big two-line headings, hover image swaps, smooth vector animation (no 3D on that site).
- The work screens stay calm; motion only where it explains something.

## Brand (from the brand sheet + deck)
- Colours:
  - Forest Green #2E5D46: headings, primary text, icons, sidebar, key elements.
  - Antique Gold #D4A247: gear, accents, highlights, buttons, active states.
  - Paper #F8F7F1: backgrounds, cards, surfaces.
- Status colours (planning proposal, to approve): return #B42318, review #B54708, clear #067647, not automated #667085; always paired with a text label + icon.
- Type (deck spec):
  - Cover title: Montserrat Bold 34-40.
  - Headings: Montserrat SemiBold 28-32.
  - Subheadings: Roboto Medium 20-24.
  - Body: Roboto Regular 18-22 (deck; the web will scale down).
  - Labels: Roboto Medium 14-18.
  - Footnotes: Roboto Regular 11-13.
  - Brand name: Montserrat SemiBold; tagline "DOCUMENT VERIFICATION": Roboto Medium, letter-spaced.
  - Indian scripts: the Noto Sans family per script.
- Logo:
  - A gold gear, a green magnifier ring, a document with lines, a gold check badge, a green handle.
  - Variants: full colour, horizontal, monochrome, reversed on green.
  - Deliverable: a clean vector redraw (SVG + PDF + PNG 1024/2048/4096) shared with the team for the deck.

## Never (the "looks AI-generated" reel, 30 items)
- Visual effects: harsh gradients; drop shadows; liquid glass; radial orbs; dot grids; neon colours.
- Colour: rainbow colouring; purple and black; basic pastel colours; pure white backgrounds.
- Icons and type: Lucide icons; sparkle icons; emojis; Inter, Geist or Space Grotesk fonts; checkmark bullets.
- Layout patterns: 3 feature cards in a row; bento grids; a coloured left stripe; terminal windows; soft (big) corner radius; 3 pricing tiers.
- Copy: em dashes; "it's not X, it's Y"; fake testimonials.
- Motion: animated arrows; hover animations.
- Missing pieces to avoid: no skeleton loaders; no real product demos; no Terms; no privacy policy.
- So we must HAVE: skeleton loaders, real demos/data, Terms + Privacy.
- (Deck note: the current slide cards use a coloured left stripe; review at deck time.)

## Process log
- 26 Oct 23:10: answers received (home = officer queue; real AICTE terms; all 3 cool ideas, subtle; middle-ground density; logo redraw; approvers).
- 26 Oct 23:46: logo APPROVED (centred version). Pack: Pramaan_logo_pack.zip (SVG, PDF, PNG 1024/2048/4096; full colour, on paper, monochrome, reversed).
- 27 Oct: step 1 drawn in Figma: https://www.figma.com/design/098H6dN6COyGiJHCyN8xbb (Aryan's account, drafts).
  - Option 1 Ledger: green sidebar + calm queue table + lane tabs.
  - Option 2 Editorial: top nav, big two-line heading, lane counts, Next up card with the scan, list grouped by lane.
  - Option 3 Desk: icon rail + queue list + case preview (document with evidence boxes, findings with Correct / False alarm, audit-chain timeline).
  - Shared: profile pop-up (6 Handbook roles, theme, language, sign out); motion storyboard A scan / B seal (gear 36°, 900 ms) / C chain (300 ms); skeleton loading; tokens + type + 30-item check.
  - Dark-mode neutrals (designed): bg #111915, surface #17211C, border #2B3832, text #ECEBE3, muted #9BA7A0. Status in dark: #F97066 / #FDB022 / #47CD89 / #98A2B3.
  - Waiting for the pick (1, 2, 3 or a mix). Status: DESIGNED, not approved.
- 27 Oct: BLOCKER for step 2: Figma Starter plan with a View seat = 20 MCP tool calls per month, now used up. Variables are limited to 1 mode on Starter (dark mode drawn as separate frames).
- 27 Oct 01:29: HOME PICKED = Option 3 (Desk). Figma now runs on Nishchal's student plan (Full seat); file moved to his Education team.
- 27 Oct: step 2 drawn, page "Step 2: All pages (Desk)" in the same file. Frames: 01 Sign in + role (scan) · 02 Home (Option 3) · 03 Case view: evidence · 04 Checklist · 05 Verification sources (demo adapters labelled) · 06 Changes since 2025 · 07 Resubmission (3 of 4 fixed) · 08 Letter editor (LoD, Seal and issue) · 09 Letters and outbox · 10 Calendar · 11 Appeals tracker (SAC 7-day window) · 12 Analytics (leadership) · 14 Search + saved filters · 15 EVC visit pack (Hindi language shown) · 16 Batch-approve with random spot check · 17 Privacy/Terms/Accessibility · 18 States (empty, unreadable scan, source down, loading) · Dark: case view, letter editor.
  - Status: DESIGNED, waiting for approval of ALL pages by Nishchal, Jasraj, Aryan. Only then: write the front-end worker card.
  - Numbers on screens are synthetic, except one measured one: 59 of 59 Handbook quotes match.
- 27 Oct 02:19: review round 1 (Aryan/Nishchal). Changes made, other pages untouched:
  - 01 Sign in redone: sign-in on the LEFT (40%), animated document check on the RIGHT (60%), make.com as inspiration, little text. 4 keyframes with Smart Animate; press Play on frame 01.
  - 05 Verification sources: a Preview button on every source row + new 05b (preview drawer, DigiLocker).
  - Case tab bar now sits on its own darker band (03, 04, 05, 06, 07, dark 03).
  - 13 Rule pack page REMOVED. Rule: never show rule-automation counts anywhere.
  - 17 Privacy: site footer added.
  - Full spec now in DESIGN_SYSTEM.md. Next: final approval, then Step 2 is FROZEN and the worker card can be written.
- 27 Oct 02:40: review round 2. Sign-in redrawn at 1440x820, centred, no scroll; logo moved into the centred block; right panel textured (faded page stack + faint gear outlines). 17 footer: second line removed. "Rule pack" removed from the rail on every Step 2 page. Analytics: same layout for every role, scope and figures change by role; no extra design (build it).
