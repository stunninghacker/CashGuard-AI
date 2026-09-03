"""
Lightweight internationalisation helper (Issue 9).

Provides UI-label translations for the dashboard in 6 Indian languages:
    en (English), hi (Hindi), bn (Bengali), te (Telugu),
    mr (Marathi), ta (Tamil)

Usage:
    from .i18n import t, locales, load_strings
    t("app.title", lang="hi")          -> Hindi string (falls back to en, then key)
    locales()                           -> [{'code': 'hi', 'native': 'हिन्दी'}, ...]

Translations are served to the SPA via GET /i18n/strings?lang=; the frontend
renders labels through a tiny client-side mapper. Unknown keys always fall back
to English then to the key itself — a missing translation never breaks the UI.
"""
from __future__ import annotations

import json
from pathlib import Path

LOCALE_DIR = Path(__file__).resolve().parent / "locales"

# (code, native name, ISO name)
_SUPPORTED = [
    ("en", "English", "English"),
    ("hi", "हिन्दी", "Hindi"),
    ("bn", "বাংলা", "Bengali"),
    ("te", "తెలుగు", "Telugu"),
    ("mr", "मराठी", "Marathi"),
    ("ta", "தமிழ்", "Tamil"),
]

DEFAULT_LANG = "en"

_lang_cache: dict[str, dict] = {}


def locales() -> list[dict]:
    """Available locales (slim metadata for the language dropdown)."""
    return [{"code": c, "native": n, "name": iso} for c, n, iso in _SUPPORTED]


def load_strings(lang: str = DEFAULT_LANG) -> dict:
    """Load a language's translation map, with English fallback added."""
    if lang not in _lang_cache:
        data: dict = {}
        path = LOCALE_DIR / f"{lang}.json"
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
        else:  # unknown lang -> English only
            en_path = LOCALE_DIR / "en.json"
            if en_path.exists():
                data = json.loads(en_path.read_text(encoding="utf-8"))
        # always merge English as the ultimate fallback (so a half-translated
        # locale still covers every key)
        en_path = LOCALE_DIR / "en.json"
        if en_path.exists():
            en = json.loads(en_path.read_text(encoding="utf-8"))
            merged = dict(en)
            merged.update(data)
            data = merged
        _lang_cache[lang] = data
    return _lang_cache[lang]


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    """Translate a key for `lang`; fallback chain: lang -> en -> key."""
    strings = load_strings(lang)
    template = strings.get(key)
    if template is None:
        en = load_strings(DEFAULT_LANG)
        template = en.get(key, key)
    if kwargs and template:
        try:
            return template.format(**kwargs)
        except (KeyError, IndexError, ValueError):
            return template
    return template


def is_supported(lang: str) -> bool:
    return any(c == lang for c, _, _ in _SUPPORTED)
