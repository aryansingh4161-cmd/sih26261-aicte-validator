"""Data minimisation for logs and reports. Personal values (signatory / notary names, stamp numbers) are masked as
"I*** K*****" (first character of each word kept) everywhere EXCEPT the result JSON the officer works from.
Used by pramaan/audit.py (every detail is masked before it is hashed and stored) and pramaan/report.py. OWNER: Aryan."""
from __future__ import annotations

import re
from typing import Any, Iterable

PERSONAL_FIELDS = ("signatory_name", "notary_name", "stamp_no")


def mask(value: Any) -> Any:
    """'Kavya Verma' -> 'K**** V****'; 'IN-DL5788' -> 'I********'. Non-strings and empty values pass through."""
    if not isinstance(value, str) or not value.strip():
        return value
    return re.sub(r"\S+", lambda m: m.group(0)[0] + "*" * (len(m.group(0)) - 1), value.strip())


def mask_detail(obj: Any, keys: Iterable[str] = PERSONAL_FIELDS) -> Any:
    """Recursively mask the values of personal keys in dicts / lists (audit-log details)."""
    keys = tuple(keys)
    if isinstance(obj, dict):
        return {k: (mask(v) if k in keys else mask_detail(v, keys)) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [mask_detail(v, keys) for v in obj]
    return obj


def personal_values(documents, keys: Iterable[str] = PERSONAL_FIELDS) -> list[str]:
    """Personal values extracted in these DocumentRecords (longest first, so longer values are replaced first)."""
    vals = {d.fields[k].value.strip() for d in documents for k in keys if k in d.fields and d.fields[k].value and d.fields[k].value.strip()}
    return sorted(vals, key=len, reverse=True)


def mask_text(text: str, values: Iterable[str]) -> str:
    """Replace every occurrence of a known personal value inside free text (finding reasons, evidence, notes)."""
    for v in values:
        if v and v in text:
            text = text.replace(v, mask(v))
    return text
