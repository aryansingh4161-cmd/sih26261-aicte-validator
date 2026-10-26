# Verification adapters (WK23-9)
Every outside source is reached through one adapter. In this repository all of them are **MOCK**: they read synthetic files in
`data/mock_issuers/` written by `python -m pramaan.synth.bundles`, and every row they produce says "MOCK".

| Source | Where | Reads | Status words |
|---|---|---|---|
| AICTE records | pramaan/issuer.py (pipeline) | data/aicte_records.json | verified / mismatch / unavailable |
| University NOC repository | pramaan/issuer.py (pipeline) | data/mock_issuers/university.json | verified / mismatch / pending |
| Fire department portal | pramaan/issuer.py + issuer_async.py (webhook) | data/mock_issuers/fire.json | verified / mismatch / pending / unavailable |
| Digital signature | pramaan/forensics.py (pyHanko, real check, not MOCK) | config/trust/*.pem | verified / mismatch |
| Municipal occupancy register | pramaan/verify_board.py `MunicipalRegister` | data/mock_issuers/occupancy.json | verified / mismatch / pending / unavailable |
| NBA accreditation | pramaan/verify_board.py `NBA` | data/mock_issuers/nba.json | verified / pending / unavailable (information only) |
| DigiLocker issued documents | pramaan/verify_board.py `DigiLocker` | data/mock_issuers/digilocker.json + manifest `declared.consent_digilocker` | verified / pending / consent not given |

## Interface
```python
class Adapter:
    name: str            # shown in the board
    mock: bool = True    # False only when an authorised real source answers
    def check(self, app: Application, result: ApplicationResult) -> list[dict]: ...
# row = {"document", "source", "status", "checked_at", "compared", "mock"}  (verify_board.row(...))
```
To drop in a real API: write a class with the same `check()` that calls the API, set `mock = False`, and replace the MOCK class
in `verify_board.ADAPTERS`. Rules: no personal data leaves the machine without the institute's consent (DigiLocker asks for it
explicitly); time-outs give "unavailable", never a guess; the compared fields are listed so the officer sees what was checked.
