"""User-visible text goes through t(text, lang). English is the source language; until the offline translation engine is
plugged in (WK23 feature 17) every language returns the English text unchanged. OWNER: Aryan."""
from __future__ import annotations

LANGUAGES = {"en": "English", "hi": "हिन्दी Hindi", "bn": "বাংলা Bengali", "mr": "मराठी Marathi", "te": "తెలుగు Telugu",
             "ta": "தமிழ் Tamil", "gu": "ગુજરાતી Gujarati", "kn": "ಕನ್ನಡ Kannada", "ml": "മലയാളം Malayalam", "or": "ଓଡ଼ିଆ Odia",
             "pa": "ਪੰਜਾਬੀ Punjabi", "as": "অসমীয়া Assamese", "ur": "اردو Urdu"}
BANNER = "Machine-translated (IndicTrans2, offline). The English version is authoritative."


def t(text: str, lang: str = "en") -> str:
    return text


def banner(lang: str = "en") -> str:
    return "" if lang == "en" else BANNER
