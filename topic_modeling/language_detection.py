from __future__ import annotations

from functools import lru_cache


LANGUAGE_MAP = {"SPANISH": "es", "ENGLISH": "en", "PORTUGUESE": "pt", "INDONESIAN": "id"}


@lru_cache(maxsize=1)
def _detector():
    try:
        from lingua import Language, LanguageDetectorBuilder
    except ImportError:
        return None
    return LanguageDetectorBuilder.from_languages(
        Language.SPANISH, Language.ENGLISH, Language.PORTUGUESE, Language.INDONESIAN
    ).with_preloaded_language_models().build()


def detect_language(text: str) -> tuple[str, float | None, str]:
    sample = (text or "").strip()[:10000]
    if len(sample) < 30:
        return "und", None, "insufficient_text"
    detector = _detector()
    if detector is None:
        return "und", None, "dependency_unavailable"
    language = detector.detect_language_of(sample)
    if language is None:
        return "und", None, "undetected"
    confidence = detector.compute_language_confidence(sample, language)
    return LANGUAGE_MAP.get(language.name, language.name.casefold()), float(confidence), "ok"

