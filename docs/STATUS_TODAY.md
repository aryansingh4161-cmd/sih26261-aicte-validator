# STATUS_TODAY - Sun 25 Oct (Opus 5.5 worker, cloud session)

## A0 + WK1 (~12:50)
- Changed: starter zip v1 committed to main (434281c). requirements.txt = starter list; old pinned freeze moved to docs/requirements_freeze_aryan.txt. .gitignore adds real_samples/, output/, data/demo/, *.pt.
- Tests (measured, system Python 3.13, NOT 3.11): test_synth ALL PASSED; test_contracts ALL PASSED with owner modules SKIPPED (not in pramaan/ yet); bundles wrote 12 apps, signed affidavits: False.
- Numbers: none new.
- BLOCKED (all 3 WK1 checks): this cloud session cannot reach PyPI (proxy 403 on pypi.org), so torch, pyHanko, Streamlit cannot be installed. Torch / signatures / dashboard remain UNTESTED.
- Teammates: pull main for the starter files. Manviraj: model scripts NOT yet verified, do not wait on this; run the WK1 check 1 commands yourself on Colab, or wait until pypi.org is allowed here.

## WK1 rerun (~14:40) - partial, PyPI still blocked (proxy 403) in this session
- Changed: pramaan/forensics.py (copied from reference), dashboard/app.py (copied from reference), tests/test_contracts.py gains t_signature (4 cases, runs under module forensics, SKIPs if pyhanko missing).
- Tests (measured, Python 3.13): test_synth ALL PASSED; test_contracts ALL PASSED (signature SKIP: no pyhanko). Tiny dataset (56 images) + ai_inpaint --method classical OK. All model scripts byte-compile. Dashboard compiles; no removed Streamlit APIs found by static scan.
- Numbers (measured, reference modules, unsigned affidavits): demo pipeline 12/12 apps ran, 0.27-0.39 s each. APP-01 and APP-11 = return_for_rectification with ONE finding R-SIG-affidavit_2 (unsigned because no pyHanko); expected "clear" once signed = ASSUMPTION, untested.
- UNTESTED: torch train/eval/tamper_model, pyHanko signing + the 4 signature cases, Streamlit serving.
- Teammates: pull main (forensics.py is the reference copy; Jasraj's own version can replace it if it passes python -m tests.test_contracts signature).

## WK0b verify (local Mac session, .venv Python 3.14.6)
- Changed: nothing in code. Steps 1-3 were already done in a38f3bb (TEST_SETS has test_ai_inpaint + test_classical_inpaint; ai_inpaint.py present; config/trust/ gitignored, demo_root.pem untracked; use_reference all-missing = no-op; reference/pramaan and reference/dashboard identical to live copies).
- Tests (measured, Python 3.14.6): test_synth ALL PASSED; test_contracts 9/9 PASS, 0 SKIP (ingest, classify_extract, rules, crosscheck, triage, audit, report, pipeline, signature). Signature's 4 cases now run for real (pyHanko 0.38.0); the PathBuildingError traceback in the output is pyHanko logging the "unknown trust root" case, as expected.
- Numbers: none new. pip works here: pyHanko 0.38.0, streamlit 1.66.1, torch 2.14.1 (MPS available), segmentation_models_pytorch 0.5.0, opencv-python-headless 5.0.0.93 installed in .venv.
- UNTESTED: test_contracts has no cases for issuer, photo_check, tamper_model or forensics.pdf_structure_checks (they pass test_synth / pipeline only); torch train/eval/tamper_model; Streamlit serving; APP-01/APP-11 "clear" once signed (still an assumption).
- Teammates: nothing new to pull for code; pip install -r requirements.txt now works on Mac with Python 3.14.

## WK1 check 1 - torch smoke (local Mac, Python 3.14.6, torch 2.14.1 CPU)
- Changed: no code; train_unet / eval_model / features / tamper_model / ai_inpaint --method classical all ran unmodified.
- Measured (/tmp/tiny, 16/8/8, seed 1, 1 epoch bs 2): train 62 s on CPU, wrote /tmp/t.pt; eval wrote /tmp/r.csv incl. test_classical_inpaint (n=8). AUCs (0.0-0.87) are noise on n=8 after 1 epoch - smoke only, NOT results.
- tamper_check: loads weights, runs on a scanned image (threshold 0 -> 1 F-TAMPER finding, lane human_review, heatmap saved); [] for text-layer PDFs and for missing weights, as designed.
- Note: train_unet downloads ImageNet encoder weights from the HF Hub on first run (needs internet on Colab). --method ai not tried (not asked).

## WK1 check 2 - signatures (pyHanko 0.38.0)
- Changed: tests/test_contracts.py t_signature now also asserts the unsigned case note contains "no digital signature found" (CONTRACTS 6). demo_pki.py / forensics.py unchanged (no bug found).
- Tests (measured): bundles --today 2026-10-26 -> "signed affidavits: True"; t_signature 4/4 cases PASS (verified / mismatch_detected / manual_review_required x2); test_synth + test_contracts 9/9 PASS.
- Numbers (measured, output/*.result.json): pipeline 12/12 apps; APP-01 clear (0 findings), APP-11 clear (0 findings, 1 pending_verification alert from the injected fire_not_in_issuer_db = as designed), APP-12 clear; 0.14-0.24 s/app (APP-01 2.13 s incl. first-run warm-up).
- The earlier ASSUMPTION "APP-01/APP-11 clear once signed" is now MEASURED. Teammates: pull main.

## WK1 check 3 - dashboard (streamlit 1.66.1)
- Changed: nothing; dashboard/app.py = reference copy, no deprecation ERRORS on 1.66.1.
- Tests (measured): headless server on :8599 -> / 200, /_stcore/health ok, log clean; streamlit AppTest ran app.py and selected all 12 demo apps: 0 exceptions, 0 st.error.
- Warnings only: use_container_width deprecated (use width='stretch'); sqlite ResourceWarning (unclosed audit.db connections). Not fixed (warnings, not errors).
- UNTESTED: real browser clicks (Decision selectbox submit, file upload), MPS training.

## WK2 F10 priority + F8 reuse (local Mac, Python 3.14.6)
- Changed: schemas.ApplicationResult +priority/+priority_reasons; NEW pramaan/priority.py (score(result, record, settings, today=None)), pramaan/reuse.py (check_reuse, SQLite index next to audit.db = output/reuse.db; compares only with apps FIRST indexed earlier, so re-runs are stable and never self-match); pipeline calls reuse after crosscheck and priority before the final audit row; report header shows priority + reasons; dashboard queue has a priority column, sorted desc; settings.yaml priority_weights (designed weights, ASSUMPTION, not trained); bundles APP-13 (APP-09 campus_1 photo, own GPS) and APP-14 (APP-03 fire certificate no, not in mock fire db).
- Tests (measured): test_synth ALL PASSED; test_contracts 11/11 PASS (new t_priority, t_reuse); pipeline re-run twice gives identical lanes/priorities; dashboard AppTest 0 exceptions, queue sorted by priority.
- Numbers (measured, eval/results.csv, synthetic): extract.field_acc.all 0.9972 (n=1800); extract.type_acc.all 1.0 (n=300); demo.recall 1.0 (n=18); demo.unexpected_findings 0 (n=14 apps); demo.lane_agreement 0.9286 (n=14; APP-12 clear because no tamper weights here); demo.seconds_per_app 0.34. Priority (designed): top APP-07 0.55; APP-01/APP-11 0.00.
- UNTESTED / notes: reuse only flags the LATER application (APP-03, APP-09 not flagged back); ahash tolerance 6 bits untested on real photos; priority weights not validated against any officer ranking; reference/pramaan/pipeline.py is now OLDER than pramaan/pipeline.py - do not run use_reference pipeline.
- Teammates: pull main, then python -m pramaan.synth.bundles --today 2026-10-26 (now 14 apps) and delete output/reuse.db before a clean demo run.
