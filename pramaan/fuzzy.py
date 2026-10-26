"""WK22 OCR tolerance for spec-driven extraction (generic: only the spec's own labels, no document or institute strings).
- label_matches(text, label): a line that IS a label still matches with a few character errors ("Perod of" ~ "Period of").
- repair_line(text, labels): a label inside an OCR line is rewritten to its exact spelling, and misread separators after a
  word ("No::", "No.=", "No;") become ":", so the spec's regex patterns apply unchanged.
- fix_date_chars(v): O/o -> 0 and l/I/| -> 1, only inside a token made of digits, those letters and date separators.
Allowed errors grow with label length: 0 below 4 characters, 1 below 8, else 2 (short labels would match random words).
OWNER: Aryan."""
from __future__ import annotations

import re


def max_errors(label: str) -> int:
    n = len(label.strip())
    return 0 if n < 4 else 1 if n < 8 else 2


def lev(a: str, b: str, limit: int) -> int:
    """Levenshtein distance, stops early once every cell exceeds limit (returns limit + 1)."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def _core(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[\s:;.,=]+$", "", s.strip())).lower()


def label_matches(text: str, label: str) -> bool:
    t, l = _core(text), _core(label)
    return bool(t) and lev(t, l, max_errors(l)) <= max_errors(l)


def _separators(text: str) -> str:
    text = re.sub(r"[:;=]{2,}", ":", text)                        # "No::" / ":;" -> ":"
    return re.sub(r"(?<=[\w.])\s*[;=](?=\s)", ":", text)         # "No.= 12" / "Date; 1-2" -> "No.: 12"


def repair_line(text: str, labels) -> str:
    text = _separators(text)
    low, labels = text.lower(), {l for l in labels if l}
    if any(l.lower() in low for l in labels):                 # a label is already spelled right: leave the line alone
        return text
    best = None                                               # the single closest label wins (alternatives are often near)
    for lab in labels:
        k, L = max_errors(lab), len(lab)
        for st in ([0] + [m.end() for m in re.finditer(r"\s+", text)]) if k else []:   # labels start at a word start
            for n in range(L - k, L + k + 1):
                d = lev(low[st:st + n], lab.lower(), k)
                cut = st + n < len(text) and text[st + n].isalnum()           # window would split a word
                if d <= k and (best is None or (d, cut, -L) < best[0]):
                    best = ((d, cut, -L), st, n, lab)
    if best:
        _, st, n, lab = best
        text = text[:st] + lab + text[st + n:]
    return text


def fix_date_chars(v: str) -> str:
    def tok(m):
        s = m.group(0)
        return s.translate(str.maketrans("OoIl|", "00111")) if re.search(r"\d", s) else s
    return re.sub(r"[0-9OoIl|]+(?:[-/.][0-9OoIl|]+){2}", tok, v)
