# Pramaan features (the deck is built from this file)
Status: built = code + test; mocked = works against a MOCK source; designed = specified, not built. Numbers are labelled measured / mocked / designed / assumption.

| # | Feature | Officer pain it removes | What it does (1 line) | Status | Evidence (test, demo app, numbers) | Dashboard page |
|---|---|---|---|---|---|---|
| 0 | Demo data + i18n hook | No realistic cases for the new tools | APP-19..23, region / assigned officer / DigiLocker consent per app, prior-year MOCK record; every string via t() | built | bundles: APP-01..18 documents byte-identical (affidavit signatures aside); 23 apps | all |
| 1 | Letter of Deficiency, auto-drafted | Typing each deficiency letter by hand | Numbers every return_for_rectification finding with the document, the Handbook clause verbatim and what to submit; review items go to an internal annex; HTML / text / .docx; edited final text in the audit log | built | test_officer lod: APP-02 letter = R-MISS-fire_cert with ANNEXURE-2 2.1 v.; APP-09 (review only) -> no letter items | Desk |
| 2 | Resubmission diff | Re-reading the whole file when an institute resubmits | Per earlier deficiency: resolved / still open / new; per document: unchanged / replaced / added / removed; one summary line | built | test_officer resubmit: APP-02 -> APP-19 "1 of 1 deficiencies resolved; 0 still open; 1 new" (APP-02 had one deficiency, so the still-open path is tested on a constructed pair) | Desk |
