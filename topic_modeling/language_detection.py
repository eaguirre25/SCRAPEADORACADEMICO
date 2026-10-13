from __future__ import annotations

from functools import lru_cache


LANGUAGE_MAP = {"SPANISH": "es", "ENGLISH": "en", "PORTUGUESE": "pt", "INDONESIAN": "id"}


@lru_cache(maxsize=1)
def _detector():
    try:
        from lingua import Language, LanguageDetectorBuilder
    except ImportError:
        return None
    # Unsupported languages must be able to win instead of being forced into
    # one of the four modeling languages. Lazy loading avoids preloading all.
    return LanguageDetectorBuilder.from_all_languages().with_minimum_relative_distance(0.15).build()


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
    code = language.iso_code_639_1.name.casefold()
    status = "ok" if code in LANGUAGE_MAP.values() else "unsupported_language"
    return code, float(confidence), status

