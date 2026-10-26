# CONTRACTS.md - exact formats and function signatures  [paste into your Project; paste schemas.py too]
The file `pramaan/schemas.py` IS the contract (pydantic models, extra fields are rejected). This page explains it and fixes every function signature. Dates are ISO strings YYYY-MM-DD. Bounding boxes are fractions of the page (0..1), origin top-left. Page numbers start at 1.

## 1. Fixed vocabularies (exact strings)
- Verification statuses (the six in the problem statement): `verified`, `mismatch_detected`, `expired`, `verification_pending`, `source_unavailable`, `manual_review_required`.
- Verification methods (the six in the problem statement): `issuer_portal`, `api`, `digital_repository`, `reference_number`, `qr_code`, `digital_signature`.
- Severity: `info` < `low` < `medium` < `high`.
- Finding lane: `return_for_rectification` (missing/expired/incomplete: the institute can fix) | `human_review` (looks wrong: a person looks) | `info`.
- Application lane (overall): `human_review` if any finding has lane human_review; else `return_for_rectification` if any finding has that lane; else `clear`. There is no "reject" anywhere.
- Finding source: `rule`, `crosscheck`, `pdf_forensics`, `tamper_model`, `photo`, `verification`.
- Document types: `eoa_letter`, `affidavit_2`, `noc_format2`, `fire_cert`, `structural_cert`, `unclassified`. Application categories: `eoa_existing_regular`, `intake_increase`.

## 2. Canonical field names per document type (value strings; dates ISO)
- eoa_letter: `file_no`, `approval_date`, `permanent_id`, `application_id`, `institute_name`, `academic_year`, `printed_on`; table `programs` rows `{course, intake_prev, intake_curr}`
- affidavit_2: `stamp_value` ("100"), `stamp_no`, `signatory_name`, `signatory_designation`, `institute_name`, `application_id`, `sworn_date`, `notary_name`
- noc_format2: `university_name`, `institute_name`, `ref_no`, `issue_date`, `academic_year`; table `programs` rows `{course, intake_curr}`
- fire_cert: `certificate_no`, `issuing_authority`, `institute_name`, `issue_date`, `valid_until`
- structural_cert: `certificate_no`, `issue_date`, `validity_years`, `issuing_authority`, `institute_name`
The generator (`pramaan/synth`) writes the true value of each of these in `truth`, so extraction accuracy can be measured.

## 3. Function signatures (one function per job; modules import shapes from pramaan.schemas)
```
# pramaan/ingest.py  (Jasraj)
def ingest(path: str, doc_id: str, slot: str | None = None) -> DocumentRecord
#  PDF: text layer via pdfplumber -> line-level TextBlocks (normalised bbox); pages; is_scanned (almost no text);
#  metadata keys: producer, creator, creation_date, mod_date, eof_markers (count of b"%%EOF"), has_signature_field, fonts (sorted list), error (only if broken)
#  Image file (jpg/png): is_scanned=True. If a sidecar file <path>.ocr.json exists it is loaded as OCR blocks (source="ocr").
#  Never raises on a broken file.
# pramaan/classify_extract.py  (Jasraj)
def classify_and_extract(doc: DocumentRecord, specs_dir: str = "config/doc_specs") -> DocumentRecord   # sets doc_type, doc_type_confidence, fields, tables
# pramaan/forensics.py  (Jasraj)
def pdf_structure_checks(app_id: str, doc: DocumentRecord, spec: dict) -> list[Finding]            # source="pdf_forensics"
def signature_check(doc: DocumentRecord, trust_roots: list[str]) -> VerificationResult              # method="digital_signature"
# pramaan/tamper_model.py  (Manviraj)
def tamper_check(app_id: str, doc: DocumentRecord, weights_path: str = "data/models/tamper_unet.pt") -> list[Finding]   # source="tamper_model"; [] if weights missing
# pramaan/rules.py  (Geetansh)
def run_rules(app: Application, docs: list[DocumentRecord], verifications: list[VerificationResult],
              record: dict | None, rulepack_path: str, today: date) -> list[Finding]           # source="rule"
# pramaan/crosscheck.py  (Geetansh)
def run_crosscheck(app: Application, docs: list[DocumentRecord], record: dict | None, today: date) -> list[Finding]   # source="crosscheck"
# pramaan/photo_check.py  (Geetansh, extra C)
def check_photos(app: Application, today: date) -> list[Finding]                                    # source="photo"
# pramaan/issuer.py  (Nishchal)
def verify_document(doc: DocumentRecord, app: Application, records: dict) -> list[VerificationResult]   # MOCK adapters, mock=True
# pramaan/audit.py  (Nishchal)
class AuditLog:
    def __init__(self, db_path: str): ...
    def append(self, actor: str, role: str, action: str, app_id: str | None, detail: dict) -> str   # returns the new row hash
    def verify_chain(self) -> tuple[bool, int | None]      # (ok, first_bad_row_id)
    def rows(self, app_id: str | None = None) -> list[dict]
# pramaan/triage.py  (Aryan)
def assign_lane(findings: list[Finding]) -> Lane
def make_alerts(app: Application, findings: list[Finding], verifications: list[VerificationResult], today: date) -> list[Alert]
# pramaan/report.py  (Aryan)
def build_report(result: ApplicationResult, out_dir: str) -> dict[str, str]        # {"json": path, "html": path}
# pramaan/pipeline.py  (Aryan)
def run_application(manifest_path: str, out_dir: str = "output", today: date | None = None,
                    audit_db: str = "output/audit.db", records_path: str = "data/aicte_records.json") -> ApplicationResult
```
Pipeline order: ingest -> classify_and_extract -> (pdf_structure_checks, signature_check, tamper_check, verify_document) -> run_rules -> run_crosscheck -> check_photos -> assign_lane/make_alerts -> AuditLog entries for every step -> build_report. Every step appends to the audit log ("rules applied", "record checked", "source response", "alert", "observation").

## 4. Input files
Application manifest `*.json` = `Application` (see schemas.py): app_id, category, academic_year, permanent_id, submitted_on, declared{institute_name, latitude, longitude}, documents[{slot, path}], photos[paths].
Mock AICTE records `data/aicte_records.json`: `{ "<permanent_id>": {"institute_name", "trust_name", "address", "building_completion_date", "latitude", "longitude", "ter_paid": true/false, "last_eoa_year": "2025-26", "approved_programs": [{"course", "intake_prev"}]} }` (generated together with the demo applications, SYNTHETIC).
Document spec `config/doc_specs/<doc_type>.yaml`:
```
doc_type: fire_cert
match_any: ["FIRE SAFETY CERTIFICATE"]     # case-insensitive text found on any line
fields:
  certificate_no: {patterns: ['Certificate No[:\s]+(\S+)'], type: text}
  valid_until:    {patterns: ['Valid Until[:\s]+(\S+)'],   type: date}
expected_producers: []        # strings that may appear in PDF Producer (empty = no check)
expected_fonts: []            # font-name prefixes expected (empty = no check)
```
Field options: `patterns` (regex, group 1 = value, tried line by line), `labels` (a line that is exactly the label takes the NEXT line as value), `join: true` (search the whole text joined with spaces, for values that wrap onto the next line), `first_line: true`, `type` text|date|int (dates are normalised to ISO). First match wins. Optional `tables:` block maps table columns by header keywords (see config/doc_specs/eoa_letter.yaml); borderless tables fall back to "lines ending in numbers".
Rule pack `config/rulepack_<category>.yaml`:
```
rules:
  - id: R-DOC-FIRE
    type: required_doc        # required_doc | field_present | not_expired | age_validity | conditional_required | value_equals | signature_required | year_match | record_flag
    applies_to: [eoa_existing_regular, intake_increase]
    params: {doc_type: fire_cert}
    severity: high
    lane: return_for_rectification
    title: Fire Safety Certificate missing
    message: A valid Fire Safety Certificate is required.
    aph_clause: "ANNEXURE-2 2.1 v."
    clause_verified: false      # becomes true only after a human checked the clause in the Handbook PDF
```
Settings `config/settings.yaml`: `sla_days: {high: 2, medium: 5, low: 7, info: 10}` (ASSUMPTION, configurable), `tamper_threshold`, `expiry_warning_days: 60`.

## 5. Output files
`output/<app_id>.result.json` = `ApplicationResult`. `output/<app_id>.report.html`. `output/audit.db` (SQLite, hash chain: each row stores prev_hash and hash = sha256(prev_hash + canonical json of the row)).
Metrics `results.csv`: `metric_id,metric,value,unit,n,set,label,source_file,notes` where label is one of measured/mocked/designed/assumption.

## 6. Semantics everyone must follow
- Missing or expired document -> finding lane `return_for_rectification`. Mismatch, anomaly, suspected edit -> lane `human_review`. Never both for one finding.
- A rule that cites a Handbook clause copies the clause text exactly as printed and keeps `clause_verified=false` until Saanvi marks the row ok.
- Mock verifications always set `mock=True` and `source` starting with "MOCK ". Real checks (signature validation, PDF structure) set `mock=False`.
- Status mapping for `digital_signature`: valid and trusted -> verified; broken or modified after signing -> mismatch_detected; certificate expired -> expired; signed but trust root unknown -> manual_review_required; no signature found -> manual_review_required with note "no digital signature found".
- Evidence text is at most 200 characters.

## 7. Naming conventions that other modules rely on (do not invent new prefixes)
- `rule_id` prefixes: `R-MISS-<doc>` missing document; `R-EXP-<doc>` expired / out of validity; `R-FLD-<doc>-<field>` missing or wrong field; `R-SIG-<doc>` signature rule; `R-REC-<key>` mismatch against AICTE records; `X-<NAME>` cross-document check (crosscheck.py); `F-PDF-<NAME>` PDF structure; `F-TAMPER` tamper model; `F-PHOTO-<NAME>` photo check; `V-<method>` from a verification result.
- `finding_id` = `<app_id>-<rule_id>-<doc_id or APP>`; `alert_id` = `<app_id>-AL<n>`; `doc_id` = `<app_id>-<slot>`.
- Alert kind from the finding: `R-MISS-*` and `R-SIG-*` -> missing_document; `R-EXP-*` -> expired_document; `X-*`, `R-REC-*` and `R-FLD-*` -> mismatch; `F-*` -> suspected_anomaly; verification status verification_pending -> pending_verification; source_unavailable -> source_unavailable. One alert per (app, kind); `finding_ids` lists all findings in it; `due_by` = today + the SHORTEST SLA among its findings' severities (SLA days come from `config/settings.yaml`, default high 2, medium 5, low 7, info 10 = ASSUMPTION).
- `conditional_required` params (only these two forms): `{doc_type: X, when_record_older_than: {key: building_completion_date, years: 30}}` or `{doc_type: X, when_record_equals: {key: ter_paid, value: false}}`.

## 8. Changes announced Sun 25 Oct 13:00 (made by the Opus 5.5 worker; everyone else just pulls)
- `DOC_TYPES` gains `area_statement` (F9). Fields: `institute_name`, `total_built_up_area_sqm`, and table `areas` rows `{room_type, count, area_sqm}`.
- `ApplicationResult` gains `priority: float = 0.0` and `priority_reasons: list[str] = []` (F10 inspection-priority score, transparent weights in `config/settings.yaml`, label "designed weights").
- New rule type `area_min` (F9): params `{doc_type: area_statement, norms_file: config/area_norms.yaml}`; norms typed from the Handbook by Saanvi (human-read table).
- New module `pramaan/reuse.py` (F8): `check_reuse(app, docs, index_db) -> list[Finding]`, rule ids `X-REUSE-PHOTO`, `X-REUSE-CERT`; lane human_review.
- New split names for the model test: `test_ai_inpaint`, `test_classical_inpaint` (F16).
- WK21: `DOC_TYPES` gains `occupancy_cert` (Occupancy / Completion Certificate, Building License, Form D; spec `config/doc_specs/occupancy_cert.yaml`). Fields: `certificate_no`, `issuing_authority`, `institute_name`, `issue_date`, `certificate_kind` (the word printed: `Full` / `Partial` / `Provisional`).
- WK21 rules: `R-MISS-occupancy_cert` (required_doc, high, return_for_rectification; Handbook ANNEXURE-2 2.1 iii., clause_verified) and `R-PROV-occupancy_cert` (new rule type `provisional_age`, medium, human_review; ANNEXURE-3 3.1 c., clause_verified). `provisional_age` params `{doc_type, kind_field, kinds: [partial, provisional], issue_field, max_academic_years: 2, ay_start_month: 7}`: the academic year of issue counts as year 1 (academic year starts in July = ASSUMPTION); a finding is raised when the year applied for is beyond year `max_academic_years`; no finding if the date or kind is not read. New prefix `R-PROV-<doc>` -> alert kind expired_document.
- WK23 (no existing field or signature changed): manifests `declared` gain `address`, `region`, `assigned_officer`, `consent_digilocker`; MOCK AICTE records gain `last_built_up_area_sqm`, `last_approval_date`, `region` (and `approved_programs` now = LAST year's approved intake, identical for APP-01..18). New MOCK file data/mock_issuers/geocoder.json. config/users.yaml: regional officers + role `institute`. reuse.py: an application is never matched with another application of the SAME Permanent Id (a resubmission may reuse its own documents; new SQLite table app_pid). New modules, each with its own models: letters, resubmit, checklist, queue, trust, seal, yoy, serial, verify_board, expiry, feedback, assign, export_case, evc_pack, geo, appeal, outbox, i18n. New rule ids (all human_review): X-YOY-*, X-SERIAL, X-GEO.
- WK23-6: after writing a report the pipeline (and the issuer webhook) appends one audit row "report sealed" {sha256, kind}; `audit_head_hash` in the result still = the observation row (unchanged meaning), the seal row follows it.
- WK25: new tables in the audit DB file: saved_filters (search.py), notes (notes.py); export_case gains optional institute_copy=False; assign.record_assignment writes audit action "case assigned"; audit action "internal note" holds note id + SHA-256 only.
