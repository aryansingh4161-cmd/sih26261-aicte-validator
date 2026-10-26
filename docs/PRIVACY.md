# Privacy - Pramaan (plain language)

Pramaan helps AICTE scrutiny officers check Extension of Approval applications. This page says what it does with data.
It was **designed with DPDP Act 2023 principles in mind** (designed); it makes no other legal claim.

## What data is processed
- The documents an institute uploads for its application (letters, certificates, affidavits, statements, campus photos) and the
  text, dates, numbers and names read from them.
- The application details the institute declares (name, address, Permanent Id, campus location) and, where the officer's office
  has them, AICTE records for the same Permanent Id.
- What officers do in the tool: sign-ins, pages opened, decisions, letters issued, feedback on findings, internal notes.

## Where it runs
- **On the office's own machines (on-premise), offline.** No cloud AI is used at any point. The translation model (IndicTrans2)
  and the document checks run locally after a one-time download.
- Outside sources (fire department, municipal register, university, NBA, DigiLocker) are **MOCK adapters** in this version:
  nothing is sent to them (docs/ADAPTERS.md).

## DigiLocker (MOCK)
DigiLocker checks need the institute's consent (`consent_digilocker` in the application). Without it the tool shows
"consent not given" and checks nothing there.

## Keeping data small
- **Masking:** signatory names, notary names and e-stamp numbers are masked (for example "K**** V****") in the audit log and in
  reports (`pramaan/privacy.py`).
- **Internal notes** between officers are stored only inside the office database; the audit log keeps only a fingerprint of each
  note, and notes are never part of letters, the institute's self-check or the institute's copy of a case file.
- **Retention:** generated files older than 30 days (`retention_days`, an ASSUMPTION until AICTE sets a period) are deleted with
  `python -m tools.retention --apply` (dry run by default). The audit log is never deleted, so past decisions stay provable;
  it holds masked values only.

## Who can see what (roles, config/users.yaml)
- scrutiny officer: reads applications, records decisions, issues letters; viewer: reads only; admin: runs the checks;
  institute: sees only its own applications (self-check) - never officers' notes.
- Every access is logged; `python -m tools.access_log_export` exports who opened what and when (the export itself is logged).

## The AI is advisory
The tool marks things for a person to look at ("possible alteration, needs human review"). **The officer decides.** It never
issues a decision by itself.

## Your right to correct
- Officers can mark any finding "correct" or "false alarm" (with a note); these corrections are kept and reviewed.
- An institute can respond to a Letter of Deficiency within 7 days (APH 1.11 a.) and resubmit; the tool shows what changed.

## Contact
Data protection contact: **[name, designation, e-mail of the AICTE office - to be filled in]**
