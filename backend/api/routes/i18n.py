"""
Internationalisation endpoints (Issue 9).

GET /i18n/locales            -> available locale metadata for the language dropdown
GET /i18n/strings?lang=hi    -> the full translation map for a language (en-fallback merged)

Public: UI label strings are not sensitive. The SPA fetches the map once and
renders labels client-side.
"""
from __future__ import annotations

from fastapi import APIRouter, Query

from ... import i18n

router = APIRouter(prefix="/i18n", tags=["i18n"])


@router.get("/locales")
def get_locales():
    return {"default": i18n.DEFAULT_LANG, "locales": i18n.locales()}


@router.get("/strings")
def get_strings(lang: str = Query(default=i18n.DEFAULT_LANG)):
    code = lang if i18n.is_supported(lang) else i18n.DEFAULT_LANG
    return {"lang": code, "strings": i18n.load_strings(code)}
