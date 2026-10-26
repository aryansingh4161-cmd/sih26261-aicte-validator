"""User-visible text goes through t(text, lang). English is the source language; until the offline translation engine is
plugged in (WK23 feature 17) every language returns the English text unchanged. OWNER: Aryan."""
from __future__ import annotations


def t(text: str, lang: str = "en") -> str:
    return text
