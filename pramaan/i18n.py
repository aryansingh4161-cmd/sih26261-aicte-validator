"""Every user-visible string goes through t(text, lang). English is the source and the authoritative version.
Engine (WK23-17): IndicTrans2 distilled en->Indic (ai4bharat/indictrans2-en-indic-dist-200M), offline on CPU after a one-time
download (gated on Hugging Face), pre/post-processing with IndicTransToolkit. If the model cannot be loaded, t() returns the
English text and banner() says translation is unavailable.
Order of lookup: English -> static table config/i18n/<lang>.json (pre-built by python -m tools.build_translations) -> SQLite
cache output/i18n_cache.db keyed (lang, sha1(text)) -> the model (result cached).
Never translated (protected by <IDn> placeholders, restored after): numbers, dates, ids (APP-02, 1-1234567), rule ids
(R-MISS-fire_cert), file names and paths, quoted text (Handbook clauses, names, values), "MOCK", Handbook references.
If a placeholder does not survive translation, the English text is kept. OWNER: Aryan."""
from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from contextlib import closing

LANGUAGES = {"en": "English", "hi": "हिन्दी Hindi", "bn": "বাংলা Bengali", "mr": "मराठी Marathi", "te": "తెలుగు Telugu",
             "ta": "தமிழ் Tamil", "gu": "ગુજરાતી Gujarati", "kn": "ಕನ್ನಡ Kannada", "ml": "മലയാളം Malayalam", "or": "ଓଡ଼ିଆ Odia",
             "pa": "ਪੰਜਾਬੀ Punjabi", "as": "অসমীয়া Assamese", "ur": "اردو Urdu"}
CODES = {"hi": "hin_Deva", "bn": "ben_Beng", "mr": "mar_Deva", "te": "tel_Telu", "ta": "tam_Taml", "gu": "guj_Gujr", "kn": "kan_Knda",
         "ml": "mal_Mlym", "or": "ory_Orya", "pa": "pan_Guru", "as": "asm_Beng", "ur": "urd_Arab"}
RTL = {"ur"}
MODEL = "ai4bharat/indictrans2-en-indic-dist-200M"
BEAMS, BATCH = 1, 32       # greedy decoding, 32 strings per batch (speed on CPU)
STATIC_LANGS = ("hi", "bn", "ta", "mr")   # pre-built tables; the other 8 languages translate on first view (cached)
BANNER = "Machine-translated (IndicTrans2, offline). The English version is authoritative."
UNAVAILABLE = "Translation unavailable on this machine: showing English."
STATIC_DIR = os.environ.get("PRAMAAN_I18N_STATIC", os.path.join("config", "i18n"))
CACHE = os.environ.get("PRAMAAN_I18N_CACHE", os.path.join("output", "i18n_cache.db"))
PROTECT = re.compile("|".join([
    r"\"[^\"]+\"", r"'[^']{2,}'",                                       # quoted: clauses, names, values
    r"https?://\S+", r"\S+@\S+\.\w+",
    r"\b(?:ANNEXURE|Annexure)-\d+(?:\s+[\d.]+)?(?:\s+[ivx]+\.)?", r"\bAPH\s+[\d.]+\s*[a-z]?\.?", r"\bR0\d\b",
    r"\b[A-Z]{1,4}-\d[\w-]*", r"\b[A-Z](?:-[A-Za-z0-9_]+)+",          # APP-02 / SELF-x / R-MISS-fire_cert
    r"\b\d+-\d{4,}\b",                                                  # Permanent Id / Application Id
    r"\b\d{4}-\d{2}-\d{2}(?:T[\d:.]+)?\b", r"\b\d{1,2}[-/]\d{1,2}[-/]\d{2,4}\b", r"\b\d{4}-\d{2}\b",
    r"[\w./-]+\.(?:pdf|jpe?g|png|docx|html|json|csv|ya?ml|ics|zip|txt|db|py)\b", r"\b[\w-]+/[\w./-]+",
    r"\b[a-z]+_[a-z0-9_]+\b", r"\b[0-9a-f]{12,}\b", r"\bMOCK\b", r"\bSELF-CHECK\b", r"\bpyHanko\b",
    r"\b\d+(?:[.,]\d+)*%?",
]))

_engine = None             # callable(list[str], lang) -> list[str]; None = not loaded yet, False = unavailable
_static: dict = {}
CALLS = {"model": 0}       # how many strings went to the model (tests check that the cache works)


def set_engine(fn) -> None:
    """Tests (and other engines) plug in here: fn(texts, lang) -> texts."""
    global _engine
    _engine = fn


def _load_engine():
    global _engine
    if _engine is not None:
        return _engine
    try:
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        try:
            from IndicTransToolkit.processor import IndicProcessor
        except ImportError:
            from IndicTransToolkit import IndicProcessor
        tok = AutoTokenizer.from_pretrained(MODEL, trust_remote_code=True, local_files_only=True)
        model = AutoModelForSeq2SeqLM.from_pretrained(MODEL, trust_remote_code=True, local_files_only=True).eval()
        ip = IndicProcessor(inference=True)

        def run(texts: list[str], lang: str) -> list[str]:
            out = []
            for i in range(0, len(texts), BATCH):
                b = ip.preprocess_batch(texts[i:i + BATCH], src_lang="eng_Latn", tgt_lang=CODES[lang])
                x = tok(b, truncation=True, padding="longest", return_tensors="pt", max_length=256)
                with torch.no_grad():
                    o = model.generate(**x, use_cache=True, min_length=0, max_length=256, num_beams=BEAMS)
                out += ip.postprocess_batch(tok.batch_decode(o, skip_special_tokens=True, clean_up_tokenization_spaces=True), lang=CODES[lang])
            return out
        _engine = run
    except Exception:
        _engine = False
    return _engine


def available() -> bool:
    return bool(_load_engine())


def protect(text: str) -> tuple[str, list[str]]:
    keep: list[str] = []

    def sub(m):
        keep.append(m.group(0))
        return f"<ID{len(keep)}>"
    return PROTECT.sub(sub, text), keep


def restore(text: str, keep: list[str]) -> str | None:
    for i, v in enumerate(keep, 1):
        if f"<ID{i}>" not in text:
            return None
        text = text.replace(f"<ID{i}>", v, 1)
    return text


def _static_table(lang: str) -> dict:
    if lang not in _static:
        p = os.path.join(STATIC_DIR, f"{lang}.json")
        _static[lang] = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    return _static[lang]


def _db():
    os.makedirs(os.path.dirname(CACHE) or ".", exist_ok=True)
    c = sqlite3.connect(CACHE)
    c.execute("CREATE TABLE IF NOT EXISTS cache (lang TEXT, sha1 TEXT, src TEXT, out TEXT, PRIMARY KEY (lang, sha1))")
    return closing(c)


def _key(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def translate_many(texts: list[str], lang: str) -> dict:
    """Model translation of the texts not yet cached; returns {text: translation}, caching every result."""
    if lang == "en" or lang not in CODES:
        return {x: x for x in texts}
    out, todo = {}, []
    with _db() as c:
        for x in dict.fromkeys(texts):
            row = c.execute("SELECT out FROM cache WHERE lang=? AND sha1=?", (lang, _key(x))).fetchone()
            if row:
                out[x] = row[0]
            else:
                todo.append(x)
        eng = _load_engine() if todo else None
        if todo and eng:
            prot = [protect(x) for x in todo]
            need = [(x, p) for x, p in zip(todo, prot) if re.search(r"[A-Za-z]", re.sub(r"<ID\d+>", "", p[0]))]
            res = eng([p[0] for _, p in need], lang) if need else []
            CALLS["model"] += len(need)
            done = {x: (restore(r, p[1]) or x) for (x, p), r in zip(need, res)}
            for x in todo:
                y = done.get(x, x)                       # placeholder-only text (ids, dates) stays as it is
                out[x] = y
                c.execute("INSERT OR REPLACE INTO cache VALUES (?,?,?,?)", (lang, _key(x), x, y))
            c.commit()
        else:
            out.update({x: x for x in todo})
    return out


def t(text: str, lang: str = "en") -> str:
    if lang == "en" or not text or lang not in CODES or not re.search(r"[A-Za-z]", text):
        return text
    hit = _static_table(lang).get(text)
    if hit is not None:
        return hit
    return translate_many([text], lang)[text]


def model_cached() -> bool:
    """Cheap check (no model load): are the model files in the local Hugging Face cache?"""
    if _engine is not None:
        return bool(_engine)
    try:
        from huggingface_hub import try_to_load_from_cache
        return isinstance(try_to_load_from_cache(MODEL, "config.json"), str)
    except Exception:
        return False


def banner(lang: str = "en") -> str:
    if lang == "en":
        return ""
    return t(BANNER, lang) + " / " + BANNER if model_cached() else UNAVAILABLE
