# Accessibility report (axe-core, WCAG 2.0 / 2.1 A + AA rules)

Result (measured, demo build, 27 Oct, after WK27): 0 critical, 0 moderate, 0 minor. The only "serious" finding is the gold "AI" in the
Pramaan wordmark (#D4A247 on paper, 2.1:1), once per route. It is the brand logotype, which WCAG 1.4.3 exempts ("text that is part
of a logo or brand name has no contrast requirement"); it carries the accessible name "Pramaan AI". Fixed in WK26: tab text on the case
band and the "Not automated" text (token --na #667085 -> #5E6779), the scrollable viewer (focusable, labelled), the map box
(role="img"), the dark-mode letter highlights. Fixed in WK27: muted text on the letter paper in dark mode (the paper stays light).
New in WK27 and checked here: the expanded rail, the Evidence viewer (focusable page region, numbered boxes as buttons with names,
zoom and page buttons with names), the segmented switches, the tooltips of unavailable controls (role="tooltip", reachable by
keyboard focus), the audit-chain nodes (state also as text for screen readers).
Routes checked: 42 (21 routes x light and dark). Tool: tools/a11y_check.py (measured).

| Impact | Count |
|---|---|
| critical | 0 |
| serious | 21 |
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
| dark /case/APP-03/letter | none |
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

- **color-contrast** (serious): Elements must meet minimum color contrast ratio thresholds. Example: `b`
