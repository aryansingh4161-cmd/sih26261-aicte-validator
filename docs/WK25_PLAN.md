# WK25 Plan: product back-end (no UI)

> For agentic workers: item by item. Each item = module + CLI + a test function in tests/test_product.py, then
> `python -m tests.test_contracts`, `python -m tests.test_officer`, `python -m tests.test_product`, commit "WK25-<n>: ...", push,
> a docs/FEATURES.md row (numbering from 21; Dashboard page = "not yet (UI pending approval)") and a STATUS_TODAY.md line.

**Goal:** the case, search, notes and rule-administration back-end the future UI will call; plain-language policy docs; the
real-letter scorer fix.
**Architecture:** new modules in pramaan/, each with `if __name__ == "__main__"` CLI; state in the same SQLite file as the audit
log (new tables); every user-visible string through pramaan.i18n.t().
**Spec:** the WK25 card.

## Global constraints
- NO change in dashboard/, reference/dashboard/; no web/ or api/ folder.
- No existing schema field or contract signature changes; new things in CONTRACTS.md section 8.
- Never reject / forged / fraud. Offline. MOCK labelled. Synthetic data only; real_samples/ and real_photos/ never committed.
- Demo stays: 23 apps, recall 1.0, 0 unexpected, all lanes agree.
- The held-out letters (real_samples/eoa_test/) are not opened or looked at before the single WK24-C2 run.

## Review focus
1. Timeline of an app with no letter / no decision: no invented events, state "open".
2. Search with an empty query + only filters; a query that matches nothing returns [] (not an error).
3. A note mentioning an officer id that does not exist: stored, no mention created, warning returned.
4. rule_admin apply after a failed propose: refused, rule pack byte-identical.
5. check_clause when the Handbook PDF is missing: "Handbook text not available" (never "found").

## Items
| n | Module / file | Produces |
|---|---|---|
| 21 | pramaan/case_timeline.py | `build_timeline(app_id, out_dir, audit_db, manifests_dir) -> list[dict{ts, actor, type, hash, refs}]`, `case_summary(app_id, ...) -> dict`; CLI `python -m pramaan.case_timeline APP-02` |
| 22 | pramaan/search.py | `search(query, filters, ...) -> list[dict{app_id, field, value, reason, score}]`; saved filters table `saved_filters` (save/list/run/delete); CLI `python -m pramaan.search "fire expired" --region North-West` |
| 23 | pramaan/notes.py (+ export_case `institute_copy`) | `add_note(app_id, author, text, finding_id=None, db) -> dict`, `list_notes(app_id, db)`, `mentions_for(officer, db)`; table `notes`; audit row per note |
| 24 | pramaan/rule_admin.py | `check_clause(text) -> {found, page}` against the Handbook PDF (settings `handbook_pdf`, local, git-ignored; text cached in output/); `propose_edit(rule, fields) -> {ok, diff, errors}` on a temp copy; `apply_edit(...)` (version bump, audit row, clause_verified only if found); `coverage()` from config/rule_coverage.yaml |
| 25 | docs/PRIVACY.md, TERMS.md, ACCESSIBILITY.md + README links | plain language, DPDP Act 2023 by name only ("designed with ... principles in mind") |
| 26 | eval/extraction_real.py | whitespace normalised on both sides; dev EOA1-6 once (dev) + held-out EOA7+ once, both only when the answer key is on this Mac (else "waiting") |

Note: README.md currently holds two shell lines (bee1b8e); item 25 restores a real README (from README_V1.md + links).
