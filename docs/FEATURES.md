# Pramaan features (the deck is built from this file)
Status: built = code + test; mocked = works against a MOCK source; designed = specified, not built. Numbers are labelled measured / mocked / designed / assumption.

| # | Feature | Officer pain it removes | What it does (1 line) | Status | Evidence (test, demo app, numbers) | Dashboard page |
|---|---|---|---|---|---|---|
| 0 | Demo data + i18n hook | No realistic cases for the new tools | APP-19..23, region / assigned officer / DigiLocker consent per app, prior-year MOCK record; every string via t() | built | bundles: APP-01..18 documents byte-identical (affidavit signatures aside); 23 apps | all |
| 1 | Letter of Deficiency, auto-drafted | Typing each deficiency letter by hand | Numbers every return_for_rectification finding with the document, the Handbook clause verbatim and what to submit; review items go to an internal annex; HTML / text / .docx; edited final text in the audit log | built | test_officer lod: APP-02 letter = R-MISS-fire_cert with ANNEXURE-2 2.1 v.; APP-09 (review only) -> no letter items | Desk |
