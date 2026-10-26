# Pramaan AI - AICTE Extension of Approval document validator (SIH 2026, PS SIH26261)

Advisory decision support for AICTE scrutiny officers: reads the documents of an Extension of Approval application, checks them
against the Approval Process Handbook rules, cross-checks them, looks for possible alterations, and sorts applications into
"return for rectification", "human review" or "clear". **The officer decides.** Offline; outside sources are MOCK in this version.

- Policies: [Privacy](docs/PRIVACY.md) - [Terms of use](docs/TERMS.md) - [Accessibility](docs/ACCESSIBILITY.md)
- What it can do: [docs/FEATURES.md](docs/FEATURES.md) - contracts: [docs/CONTRACTS.md](docs/CONTRACTS.md) - adapters: [docs/ADAPTERS.md](docs/ADAPTERS.md)
- Numbers: eval/results.csv (every number labelled measured / mocked / designed / assumption)

## Web app (WK26, the "Desk" design)
- **Live demo:** https://aryansingh4161-cmd.github.io/sih26261-aicte-validator/ (demo mode: the 23 synthetic files, no server;
  your actions stay in your browser). Built and deployed by `.github/workflows/pages.yml` on every push to `main` that touches `web/`.
- **Run it locally (live mode, real engine):**

      pip install -r requirements.txt
      python -m pramaan.synth.bundles                                   # the 23 synthetic files in data/demo/apps (once)
      python -m pramaan.pipeline data/demo/apps/*.json --today 2026-10-26   # results in output/
      uvicorn api.main:app --port 8600                                  # API, wraps pramaan/
      npm --prefix web install && npm --prefix web run dev              # http://127.0.0.1:5173 (proxies /api to 8600)

- Demo mode locally (no Python): `npm --prefix web run dev -- --mode demo`. Rebuild the snapshot: `python -m tools.export_snapshot`.
- Tests: `python -m tests.test_api`, `python -m tests.test_web_flows` (starts both servers), accessibility: `python -m tools.a11y_check`.
- The Streamlit dashboard in `dashboard/` stays as the backup.

---

# Pramaan starter v1 (Sun 25 Oct ~12:00). Unzip ON TOP of the repo (it does not overwrite anyone's module).

## What is new
- `pramaan/synth/bundles.py` 18 demo applications with KNOWN injected problems + MOCK AICTE records + mock issuer data. `python -m pramaan.synth.bundles`
- `pramaan/synth/demo_pki.py` a DEMO certificate authority so affidavits can be signed and validated (signing needs pyHanko).
- `pramaan/model/features.py, train_unet.py, eval_model.py, eval_common.py, eval_baseline.py` and `pramaan/tamper_model.py` our ONE trained model (Colab).
- `config/doc_specs/*.yaml` (7 document types), `config/rulepack_eoa_existing.yaml` (14 rules; clause_verified only for human-checked rows), `config/settings.yaml` (assumptions).
- `eval/run_eval.py` the numbers for the deck -> `eval/results.csv`. `eval/extraction_real.py` accuracy on REAL EoA letters vs the human answer key.
- `tests/test_contracts.py` the merge gate for ANY module version. `python -m tests.test_contracts <module>`
- `reference/` complete reference versions of every module + dashboard (the SAFETY NET). `python -m tools.use_reference <module>` copies one into `pramaan/` (keeps yours as `.mine.py`).

## Tested by the author (Python 3.13 sandbox): YES
synthetic docs, ingest, classify_extract (field accuracy 99%+ on synthetic, 7 types x 3 layouts), rules, crosscheck, triage, audit (tamper-evident chain), report HTML, issuer mocks, photo checks, pipeline (about 0.3 s per application), bundles, run_eval, eval_baseline.
## NOT tested by the author: you test these
pyHanko signing/validation (`demo_pki.sign_pdf`, `forensics.signature_check`), Streamlit dashboard, anything with torch (train_unet, eval_model, tamper_model).

## Five commands (repo root, venv active)
    pip install -r requirements.txt
    python -m tests.test_synth
    python -m pramaan.synth.bundles --today 2026-10-26
    python -m tests.test_contracts
    python -m pramaan.pipeline data/demo/apps/*.json --today 2026-10-26

## Reproduce in one command
Needs Python 3.11 or newer (tested on 3.11 and 3.14). All data is SYNTHETIC; issuer checks are MOCK (designed for integration).
The demo builds the 18 demo applications, runs the pipeline on all of them, runs the eval harness (writes `output/demo_eval.csv`;
`eval/results.csv` is not touched), prints the lanes and the key metrics, then opens the dashboard at http://localhost:8501.
Optional parts are reported and skipped: tamper model (needs torch + `data/models/tamper_unet.pt` from the team Drive), EasyOCR.

Mac / Linux:

    python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt && python -m pramaan.demo

Windows (PowerShell):

    py -3.11 -m venv .venv; .venv\Scripts\Activate.ps1; pip install -r requirements.txt; python -m pramaan.demo

Options: `--no-dashboard` (stop after the metrics), `--quick` (smaller extraction eval), `--today 2026-10-26` (default; the demo dates are built around it).
If PowerShell refuses to run Activate.ps1: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, or use `.venv\Scripts\activate.bat` in cmd.
