# Accessibility report (axe-core, WCAG 2.0 / 2.1 A + AA rules)

Result after fixes (measured, demo build, 27 Oct): 0 critical; the only remaining "serious" finding on each route is the gold "AI"
in the Pramaan wordmark (#D4A247 on paper, 2.1:1). It is the brand logotype, which WCAG 1.4.3 exempts ("text that is part of a logo
or brand name has no contrast requirement"); it is marked up as role="img" with the label "Pramaan AI". Fixed in this round: tab
text on the case band and the "Not automated" text (token --na #667085 -> #5E6779, both now >= 4.5:1), the scrollable document
viewer (now focusable and labelled), the map box (role="img"), the letter highlights in dark mode (light-paper colours).

Routes checked: 42 (21 routes x light and dark). Tool: tools/a11y_check.py (measured).

| Impact | Count |
|---|---|
| critical | 0 |
| serious | 22 |
| moderate | 0 |
| minor | 0 |

## Per route

| Route | Violations |
|---|---|
| light /sign-in | serious: color-contrast (1) |
| light / | serious: color-contrast (1) |
| light /case/APP-07 | serious: color-contrast (1) |
| light /case/APP-07/checklist | serious: color-contrast (1) |
| light /case/APP-07/sources | serious: color-contrast (1) |
| light /case/APP-20/changes | serious: color-contrast (1) |
| light /case/APP-19/resubmission | serious: color-contrast (1) |
| light /case/APP-07/letters | serious: color-contrast (1) |
| light /case/APP-07/notes | serious: color-contrast (1) |
| light /case/APP-07/timeline | serious: color-contrast (1) |
| light /case/APP-03/letter | serious: color-contrast (1) |
| light /letters | serious: color-contrast (1) |
| light /calendar | serious: color-contrast (1) |
| light /appeals | serious: color-contrast (1) |
| light /analytics | serious: color-contrast (1) |
| light /search?q=fire | serious: color-contrast (1) |
| light /visit/APP-15 | serious: color-contrast (1) |
| light /privacy | serious: color-contrast (2) |
| light /terms | serious: color-contrast (2) |
| light /accessibility | serious: color-contrast (2) |
| light /states | serious: color-contrast (1) |
| dark /sign-in | none |
| dark / | none |
| dark /case/APP-07 | none |
| dark /case/APP-07/checklist | none |
| dark /case/APP-07/sources | none |
| dark /case/APP-20/changes | none |
| dark /case/APP-19/resubmission | none |
| dark /case/APP-07/letters | none |
| dark /case/APP-07/notes | none |
| dark /case/APP-07/timeline | none |
| dark /case/APP-03/letter | serious: color-contrast (1) |
| dark /letters | none |
| dark /calendar | none |
| dark /appeals | none |
| dark /analytics | none |
| dark /search?q=fire | none |
| dark /visit/APP-15 | none |
| dark /privacy | none |
| dark /terms | none |
| dark /accessibility | none |
| dark /states | none |

## Rules that fired

- **color-contrast** (serious): Elements must meet minimum color contrast ratio thresholds. Example: `.letter-paper > .muted`
