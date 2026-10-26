# WK24 Plan: WK23 officer platform, then WK22 robustness

> For agentic workers: implement task by task, in order. Each feature ends with a test in tests/test_officer.py, `python -m tests.test_contracts` + `python -m tests.test_officer`, commit "WK23-<n>: <feature>", push, then a docs/FEATURES.md row.

**Goal:** add the officer tools around the unchanged engine (extract -> rules -> crosscheck -> forensics -> lanes -> report -> audit), then finish WK22.
**Architecture:** one new module per feature in `pramaan/`, reading `ApplicationResult` JSON from `output/` (no schema field changes; new models live in the new modules). Dashboard: one Streamlit page per group in `dashboard/pages/`. Every visible string goes through `pramaan.i18n.t()`.
**Tech:** Python 3.14 venv, pydantic, Streamlit, SQLite (same `output/audit.db`, new tables), Playwright (system Chrome) for screenshots, IndicTrans2 (offline, gated on Hugging Face) for Part 3.
**Spec:** the WK24 card (HOW TO WORK, Section 1 = WK23, Section 2 = WK22).

## Global constraints
- Do not change existing schema fields or signatures in docs/CONTRACTS.md; new things go in section 8.
- Never the words reject / forged / fraud in output. Lanes: return_for_rectification / human_review / clear / info.
- Offline only. Outside systems = MOCK adapters labelled "MOCK" in output and UI.
- Synthetic data only in git. Never commit real_samples/, real_photos/, IndicTrans2/ (clone) or model weights.
- APP-01..18 keep findings and lanes; run_eval: recall 1.0, 0 unexpected, all lanes agree, field acc ~0.997.
- Labels on every number: measured / mocked / designed / assumption. Thresholds and weights live in config/settings.yaml (ASSUMPTION).
- Commit as aryansingh4161-cmd@users.noreply.github.com, after every feature.

## Review focus (inputs no feature test hits by default; each gets one assertion in its feature test)
1. An application with NO return_for_rectification findings: LoD says "no deficiencies" rather than an empty numbered list.
2. Resubmission where the previous result is missing (first submission): compare() handles prev=None.
3. Clear queue with 1 application: spot check is max(1, 10%) = 1, button disabled until it is opened.
4. Report seal on a file with no matching audit entry: verify_report says ALTERED / not found, never VALID.
5. t() on text that is only placeholders (an id, a date): returned unchanged without calling the model.

## Feature numbering (docs/FEATURES.md; screenshots out/deck/wk23_<n>.png for 1, 2, 3, 6, 8, 9, 10, 11, 12, 13)
| # | Module | Interface (produces) |
|---|---|---|
| 0 | pramaan/i18n.py | `t(text: str, lang: str = "en") -> str` (English passthrough until #17) |
| 0 | synth/bundles.py | APP-19..23, `declared.region`, `declared.assigned_officer`, `declared.consent_digilocker`, prev-year MOCK record (`last_intake`, `last_built_up_area_sqm`, `last_approval_date`) |
| 1 | pramaan/letters.py | `build_lod(result: ApplicationResult, officer_text: str | None = None) -> dict{html, text, deficiencies, notes}`; `export_docx(lod, path)`; `save_final(log, officer, app_id, text)` |
| 2 | pramaan/resubmit.py | `compare(prev: ApplicationResult | None, new: ApplicationResult) -> dict{deficiencies:[{rule_id,status}], documents:[{slot,status}], summary}` |
| 3 | config/checklists/eoa_existing.yaml + pramaan/checklist.py | `tick(result) -> list[{row, status, evidence}]`, `counts(rows) -> str` |
| 4 | pramaan/queue.py | `clear_queue(results) -> list`, `spot_sample(app_ids, seed) -> list`, `approve_batch(log, officer, app_ids, opened) -> list[hash]` |
| 5 | pramaan/trust.py | `doc_score(result, doc_id) -> (int, [reasons])`, `app_score(result) -> (int, [reasons])` |
| 6 | pramaan/seal.py + tools/verify_report.py | `seal_html(html, app_id, audit_head) -> html`; `verify(path, audit_db) -> str` ("VALID: matches audit entry #n" / "ALTERED") |
| 7 | pramaan/yoy.py | `yoy_check(app, result, record, settings) -> list[Finding]` rule X-YOY-* (human_review) |
| 8 | pramaan/serial.py | `serial_check(result, all_results) -> list[Finding]` rule X-SERIAL (human_review) |
| 9 | pramaan/verify_board.py + docs/ADAPTERS.md | `board(result, app) -> list[row]`, MOCK adapters incl. DigiLocker consent |
| 10 | pramaan/expiry.py (not calendar.py: shadows stdlib) | `expiries(results) -> list`, `reminders(..., today) -> outbox`, `to_ics(...) -> str` |
| 11 | pramaan/feedback.py | `record(db, finding_id, verdict, officer, note)`, `export_csv(db, path)`, `false_alarm_rate(db) -> dict` |
| 12 | pramaan/assign.py | `assign(results, users, settings) -> dict app_id -> officer`, `due_date(...)` |
| 13 | pramaan/export_case.py | `export_case(app_id, out_dir, audit_db, zip_path) -> path` |
| 14 | dashboard/pages/5_Institute_SelfCheck.py | precheck mode, to-do list, role institute |
| 15 | pramaan/evc_pack.py | `evc_pack(result, record) -> html` (sealed) |
| 16 | dashboard/pages/2_Analytics.py | top-10, by region, lanes, auto-cleared share, median time (synthetic), false alarms, SLA breaches |
| 17 | pramaan/i18n.py engine + tools/build_translations.py + config/i18n/<lang>.json | IndicTrans2 dist-200M, SQLite cache, placeholders, RTL Urdu, banner |
| 18 | pramaan/geo.py | `geo_check(app, docs, settings) -> list[Finding]` X-GEO (MOCK geocoder), APP-23 15 km |
| 19 | pramaan/appeal.py | `appeal_status(lod_issued_on, today, decided) -> dict` (APH 1.11 a., 7 days) |
| 20 | pramaan/outbox.py | `send(kind, to, template, data) -> path` (MOCK, data/outbox/*.json) |

Engine hooks: yoy, serial and geo are added to pipeline.run_application as extra checks (new rule ids only fire on APP-20..23; verified by run_eval 0 unexpected).

## Order
Infra (#0) -> Part 1 (#1-6, Desk page) -> Part 2 (#7-13, pages Checks, Calendar & Exports) -> Part 3 (#14-20) -> Section 2 (WK22 A done; B blocked on model 2; C step 1 done, held-out waits for EOA7+).
