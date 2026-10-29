# Repository Privacy and Sensitive-Data Review

**Scope:** Read-only review of repository code, documentation, configuration, and data.  
**Status:** Findings below require owner review. This report is the only file created for the requested summary; no existing source or data files were changed.

## Findings

### Medium — Potentially identifying signature-test recording

- **Path:** `07_video/raw/J10_signature_test.mov` (untracked)
- The filename and media type indicate a signature-test recording. Its subject, consent status, and whether it is synthetic could not be established from the audit. Treat it as potentially identifying biometric/personal data and do not commit it unless cleared for release.
- It is not currently covered by `.gitignore`. If this raw capture is meant to remain local, add a targeted ignore rule for the raw video path or directory.
- **Confidence:** 8/10

### Medium — OCR report contains a personal attribution and internal-document excerpt

- **Path:** `docs/ocr_test_jasraj.md` (tracked; attribution near line 1, OCR excerpts near lines 37–43 and 57–63)
- The report is attributed to a named person and includes recognized text from a document described in the report as an internal project specification. The source document's publication approval was not established.
- Confirm the source and excerpts are approved for publication. Otherwise, remove the attribution and replace the excerpts with synthetic, non-confidential sample text. `.gitignore` will not remove a file that is already tracked.
- **Confidence:** 8/10

### Low — Environment report contains personal/workstation details

- **Path:** `docs/env_report_aryan.md` (tracked; lines 1 and 3–4)
- The report includes a personal attribution and workstation/operating-system details. These are limited-risk data points, but may be unnecessary in a public competition repository.
- Remove the attribution or generalize the environment description if those details are not needed. `.gitignore` will not remove a file that is already tracked.
- **Confidence:** 9/10

### Low — Untracked probe output derived from real-sample documents

- **Path:** `probe_results_all8.csv` (untracked)
- The CSV references files under `real_samples/` and contains document metadata. The scan found no personal names or extracted document text in this output, but it is a derivative of real-sample material and is not currently ignored.
- Keep it local unless approved for release; consider a targeted ignore rule such as `probe_results*.csv`.
- **Confidence:** 9/10

## Other observations

- The `real_samples/` directory is ignored.
- Demo users and `APP-*` snapshot examples appear to be synthetic.
- No clear credentials or secrets were identified in the material inspected. This is not a guarantee that every secret or personal-data instance has been found.

## Before public release

1. Confirm the signature-test recording is synthetic or approved; otherwise keep it out of Git and ignore its local path.
2. Review the OCR report's source document and replace potentially internal excerpts if not approved.
3. Decide whether personal attribution and workstation details belong in the environment report.
4. Keep unapproved probe output out of commits; add a targeted ignore rule if it should remain local.
