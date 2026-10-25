# SAFEGUARDS.md - Pramaan AI (SIH 2026, PS SIH26261)

> **ASSUMPTION: the five headings below are our working names.** The exact wording of the problem statement's five
> Essential Safeguards is not in this repo. Paste the PS text over each heading; the mapping under it stays valid.
> Labels: **REAL** = implemented and tested in code (measured); **DESIGNED** = specified / stubbed, not running for real;
> **MOCK** = simulated stand-in for an external system.

## 1. Human in the loop: the AI advises, an officer decides
- REAL: no automated rejection anywhere. Only three lanes (`clear`, `return_for_rectification`, `human_review`), see `pramaan/schemas.py` (`Lane`) and `pramaan/triage.py` (`assign_lane`). Every `Finding` has `advisory=True`.
- REAL: the officer's decision is a separate, audited action with a required reason (`dashboard/app.py`, "Officer decision"); agreement between officer and AI lane is measured (`dashboard/pages/2_Analytics.py`).
- REAL: wording rules ("possible alteration, needs human review"; never "rejected"/"forged") in `pramaan/tamper_model.py`, `pramaan/report.py`.
- DESIGNED: inspection priority only orders the queue; weights are ASSUMPTIONS, not trained (`pramaan/priority.py`, `config/settings.yaml` `priority_weights`).

## 2. Explainability: every finding shows what, where and why
- REAL: each finding carries document, page, bounding box and the words it points at (`Evidence` in `pramaan/schemas.py`); the dashboard draws the red box (`dashboard/app.py`, `page_image`).
- REAL: rule findings cite the Handbook clause as printed and say UNVERIFIED until a human checked it (`aph_clause`, `clause_verified`; `config/rulepack_eoa_existing.yaml`, `config/area_norms.yaml`).
- REAL: tamper model outputs a heatmap file per page (`pramaan/tamper_model.py` -> `output/heatmaps/`).
- DESIGNED: area norms are PLACEHOLDERS until Saanvi's checked sheet is converted (`tools/norms_to_yaml.py`).

## 3. Privacy and data minimisation
- REAL: signatory / notary names and stamp numbers are masked (`K**** V****`) in every audit-log detail before hashing and in the HTML report; the full value stays only in the officer's result JSON (`pramaan/privacy.py`, `pramaan/audit.py`, `pramaan/report.py`; test `t_masking`).
- REAL: retention: output files, heatmaps and uploaded-document copies older than `retention_days` (30, ASSUMPTION) are deleted; dry run by default, every run audited; `audit.db` is never deleted (`tools/retention.py`; test `t_retention`).
- REAL: synthetic / public data only; `real_samples/` is git-ignored (`.gitignore`). No cloud AI at runtime; OCR runs locally (`tools/ocr_sidecar.py`).
- DESIGNED: per-row expiry inside `reuse.db` / `issuer_webhook.db`; `output/uploads/` is the designed location for uploaded copies (nothing writes there yet); encryption at rest is not implemented.

## 4. Access control and accountability
- REAL: role-based dashboard (scrutiny_officer: read + decide; viewer: read; admin: read + run pipeline) from `config/users.yaml`; sign-in, page views, pipeline runs and decisions are audited with actor and role (`dashboard/app.py`).
- REAL: tamper-evident audit log: SHA-256 hash chain, `verify_chain` (`pramaan/audit.py`; test `t_audit`); chain status shown in the dashboard and analytics page; access-log export to CSV by app / actor / date, itself audited (`tools/access_log_export.py`).
- DESIGNED: users are demo users with no passwords (labelled "designed for SSO" in the UI); no SSO / MFA integration.

## 5. Authenticity and integrity of documents and sources
- REAL: digital-signature validation with pyHanko against configured trust roots (`pramaan/forensics.py` `signature_check`; demo CA `pramaan/synth/demo_pki.py`; test `t_signature`); PDF structure checks (producer, fonts, incremental saves) (`pramaan/forensics.py`).
- REAL (trained on synthetic data): our tamper-localisation model (`pramaan/model/`, `pramaan/tamper_model.py`); numbers only from `eval/results.csv`.
- REAL: reuse of photos / certificate numbers across applications (`pramaan/reuse.py`); known false matches at scale are recorded (`eval/results.csv` `scale.reuse_not_injected.*`).
- MOCK (designed for integration): every issuer check - AICTE records, fire department, university repository, QR, API (`pramaan/issuer.py`, `mock=True`, source starts with "MOCK"); asynchronous signed webhook replies with HMAC (DEMO secret) and idempotency (`pramaan/issuer_async.py`, `tools/mock_issuer_sender.py`; test `t_issuer_webhook`).
