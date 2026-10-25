"""Small helpers shared by all modules. OWNER: Aryan."""
from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Optional

from .schemas import BBox

_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def parse_date(text: Optional[str]) -> Optional[date]:
    """Accepts 2026-03-16, 16-03-2026, 16/03/2026, 05-Apr-2025, 7 April 2025. Returns None if unreadable."""
    if not text:
        return None
    t = text.strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", t)
    if m:
        return _mk(int(m[1]), int(m[2]), int(m[3]))
    m = re.match(r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})$", t)
    if m:
        return _mk(int(m[3]), int(m[2]), int(m[1]))
    m = re.match(r"^(\d{1,2})[-/ .]+([A-Za-z]{3,9})[-/ .,]+(\d{4})$", t)
    if m and m[2][:3].lower() in _MONTHS:
        return _mk(int(m[3]), _MONTHS[m[2][:3].lower()], int(m[1]))
    return None


def _mk(y: int, mo: int, d: int) -> Optional[date]:
    try:
        return date(y, mo, d)
    except ValueError:
        return None


def iso(d: Optional[date]) -> Optional[str]:
    return d.isoformat() if d else None


def add_years(d: date, years: float) -> date:
    whole = int(years)
    try:
        out = d.replace(year=d.year + whole)
    except ValueError:                      # 29 Feb
        out = d.replace(year=d.year + whole, day=28)
    extra_days = int(round((years - whole) * 365))
    return date.fromordinal(out.toordinal() + extra_days)


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def norm_name(text: Optional[str]) -> str:
    """Normalise an institute/trust name for comparison."""
    t = (text or "").upper().replace("&", " AND ")
    t = re.sub(r"[^A-Z0-9 ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def similarity(a: Optional[str], b: Optional[str]) -> float:
    from difflib import SequenceMatcher
    return SequenceMatcher(None, norm_name(a), norm_name(b)).ratio()


def union_bbox(boxes: list) -> Optional[BBox]:
    if not boxes:
        return None
    return BBox(x0=min(b.x0 for b in boxes), y0=min(b.y0 for b in boxes),
                x1=max(b.x1 for b in boxes), y1=max(b.y1 for b in boxes))
