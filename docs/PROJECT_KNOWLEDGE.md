# PROJECT_KNOWLEDGE.md - Pramaan AI (SIH 2026, PS SIH26261)  [paste into your Claude/ChatGPT/Gemini Project]

## The problem in plain words
AICTE officers check Extension-of-Approval (EoA) applications by hand: dozens of documents per institute (affidavits, fire and structural certificates, university NOCs, the previous EoA letter...). They look for missing or expired papers, numbers that disagree between documents, and edited or forged files. Our tool does the first pass and shows the officer WHAT it found, WHERE (highlighted evidence) and WHY (the Handbook clause). **The tool only advises. A human decides. It never rejects:** it either sends an application back for rectification (something is missing or expired, the institute can fix it) or sends it to a human review queue (something looks wrong). Our team name is Pramaan AI.

## What we are building (the "spine" plus three extras)
SPINE (must run end to end): read a PDF -> work out its type -> pull out fields -> apply Handbook rules (each finding cites the clause) -> two lanes + alerts -> hash-chained audit log -> report -> dashboard for the officer.
EXTRAS in order: (B) cross-document contradiction finder, (A) PDF structure and digital-signature checks plus OUR ONE trained model that finds edited regions in document images, (C) photo checks (GPS vs declared location, blur, duplicate photos).
Everything that talks to an issuing authority (AICTE records, fire department, DigiLocker-style repository, QR, API) is a MOCK behind an "adapter". We say "mocked" and "designed for integration" everywhere. Digital-signature validation and PDF checks are REAL.

## Hard rules for every piece of code and every sentence
1. No paid APIs. No cloud AI at runtime. Python 3.11. All demo data is SYNTHETIC or public. Never name a real institute as suspicious. Never use real logos.
2. Every claim we make later needs a label: measured / mocked / designed / assumption. Do not invent numbers. If something is not tested, say "untested".
3. The system never says "rejected" or "forged". It says "possible alteration, needs human review".
4. Evidence-linked: every finding carries the document, page, box and the words it points at.
5. The contracts in `pramaan/schemas.py` and CONTRACTS.md are fixed. Do not rename fields. If you think a field is missing, tell Aryan; do not invent your own.

## Repo structure (GitHub repo aryansingh4161-cmd/sih26261-aicte-validator, private; Aryan merges)
```
pramaan/            schemas.py (Aryan) util.py  ingest.py classify_extract.py forensics.py (Jasraj)
                    rules.py crosscheck.py photo_check.py (Geetansh)  audit.py issuer.py (Nishchal)
                    triage.py report.py pipeline.py (Aryan)  tamper_model.py (Manviraj)
pramaan/synth/      fake documents, tampering, dataset, application bundles (Manviraj)
pramaan/model/      baseline.py metrics.py train_unet.py eval_model.py (Manviraj)
config/doc_specs/*.yaml   one file per document type (Jasraj)
config/rulepack_*.yaml    Handbook rules (Geetansh)    config/settings.yaml (Aryan)
data/               aicte_records.json (mock AICTE records, generated)   data/models/tamper_unet.pt (weights; NOT in git, in Drive)
dashboard/app.py    Streamlit officer dashboard (Aryan)
eval/run_eval.py    metrics harness -> results.csv (Aryan)
tests/              one test file per module
```
Upload rule: put files only in folders you own. One owner per file.

## How to write code for us (tell your AI this)
One file per message, under 150 lines, WHOLE file, exact file name, exact commands for my OS. Plain functions with type hints and short docstrings. Import shapes from `pramaan.schemas`; never redefine them. Each module gets a test file `tests/test_<module>.py` that runs with `python -m tests.test_<module>` and prints ALL TESTS PASSED. Never crash on a bad file: return a result with a note. No new dependencies beyond: pydantic, pyyaml, pdfplumber, pypdfium2, pillow, numpy, reportlab, pyhanko, streamlit, (optional) opencv-python-headless, torch + segmentation-models-pytorch on Colab only.

## What good output looks like
- A card's smoke test prints exactly what the card says.
- A finding reads like: "Fire Safety Certificate expired on 2025-09-16 (Annexure-2 2.1 v.)" with the date highlighted on page 1.
- A number we quote has a file and a row behind it in `results.csv`.
## What bad output looks like
- "Rejected." / "Forged." / a percentage with no source / a module that only works on one hand-picked file / renamed fields / code that needs a paid key.
