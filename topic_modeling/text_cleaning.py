from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
DOI_RE = re.compile(r"(?:https?://doi\.org/)?10\.\d{4,9}/\S+", re.I)
ISSN_RE = re.compile(r"\b(?:ISSN[-\s:]*)?\d{4}-\d{3}[\dX]\b", re.I)
LICENSE_RE = re.compile(r"creative\s+commons|copyright|by-sa|atribuci[oó]n", re.I)
REPOSITORY_RE = re.compile(r"\b(?:oai-pmh|isni)\S*", re.I)
EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w.-]+\.[a-z]{2,}\b", re.I)
BIBLIOGRAPHIC_ID_RE = re.compile(r"\b(?:pmid|pmcid|orcid|scopus\s*id|handle|isbn)\s*[:#]?\s*[\w./-]+", re.I)
EDITORIAL_LINE_RE = re.compile(
    r"(?im)^.*(?:all rights reserved|todos los derechos reservados|received:|accepted:|published:|"
    r"cómo citar|how to cite|vol\.?\s*\d+.*(?:no\.?|n[úu]m\.?)\s*\d+|"
    r"creative commons|atribuci[oó]n[-\s]compartirigual).*$"
)
BROKEN_TOKEN_RE = re.compile(r"\b(?=\w{14,}\b)(?:[^aeiouáéíóúàâãêôõ]{10,}|\w*\d\w*[a-z]\w*)\b", re.I)
REFERENCE_HEADING_RE = re.compile(
    r"(?im)^\s*(referencias|bibliograf[ií]a|references|bibliography|refer[eê]ncias|daftar\s+pustaka)\s*[:.]?\s*$"
)


@dataclass(frozen=True)
class ReferenceRemoval:
    text: str
    detected: bool
    cut_position: int | None
    removed_fraction: float


def normalize_space(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\n{3,}", "\n\n", text)).strip()


def remove_references(text: str, minimum_fraction: float = 0.35) -> ReferenceRemoval:
    matches = list(REFERENCE_HEADING_RE.finditer(text or ""))
    if not matches:
        return ReferenceRemoval(text or "", False, None, 0.0)
    eligible = [m for m in matches if m.start() >= len(text) * minimum_fraction]
    if not eligible:
        return ReferenceRemoval(text, False, None, 0.0)
    match = eligible[-1]
    removed = (len(text) - match.start()) / max(len(text), 1)
    return ReferenceRemoval(text[: match.start()].rstrip(), True, match.start(), removed)


def _base_clean(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").replace("\x00", " ")
    text = URL_RE.sub(" ", text)
    text = DOI_RE.sub(" ", text)
    text = ISSN_RE.sub(" ", text)
    text = LICENSE_RE.sub(" ", text)
    text = REPOSITORY_RE.sub(" ", text)
    text = EMAIL_RE.sub(" ", text)
    text = BIBLIOGRAPHIC_ID_RE.sub(" ", text)
    text = EDITORIAL_LINE_RE.sub(" ", text)
    text = BROKEN_TOKEN_RE.sub(" ", text)
    return normalize_space(text)


def clean_for_bertopic(text: str, *, strip_references: bool = False) -> tuple[str, ReferenceRemoval]:
    cleaned = _base_clean(text)
    removal = remove_references(cleaned) if strip_references else ReferenceRemoval(cleaned, False, None, 0.0)
    return normalize_space(removal.text), removal


def clean_for_embeddings(text: str, *, strip_references: bool = False) -> tuple[str, ReferenceRemoval]:
    """Conservative cleaning that preserves syntax for contextual embeddings."""
    return clean_for_bertopic(text, strip_references=strip_references)


def clean_for_stm(text: str, *, strip_references: bool = False) -> tuple[str, ReferenceRemoval]:
    cleaned, removal = clean_for_bertopic(text, strip_references=strip_references)
    cleaned = re.sub(r"\b\d+\b", " ", cleaned)
    cleaned = re.sub(r"[^\w\sáéíóúüñçãõàâêô-]", " ", cleaned, flags=re.UNICODE)
    return normalize_space(cleaned.casefold()), removal


def clean_for_display(text: str) -> str:
    return normalize_space(unicodedata.normalize("NFKC", text or "").replace("\x00", " "))


SECTION_HEADINGS = {
    "abstract": ("abstract", "resumen", "resumo"),
    "introduction": ("introduction", "introducción", "introducao", "introdução", "pendahuluan"),
    "methods": ("methods", "methodology", "metodología", "metodologia", "métodos"),
    "results": ("results", "resultados", "hasil"),
    "discussion": ("discussion", "discusión", "discussão", "pembahasan"),
    "conclusions": ("conclusions", "conclusion", "conclusiones", "conclusão", "kesimpulan"),
    "references": ("references", "referencias", "bibliografía", "bibliography", "referências", "daftar pustaka"),
    "appendices": ("appendix", "appendices", "anexo", "anexos", "apêndice"),
}


def split_academic_sections(text: str) -> dict[str, str]:
    """Best-effort section split; unresolved text remains under ``body``."""
    source = clean_for_display(text)
    matches: list[tuple[int, int, str]] = []
    for section, headings in SECTION_HEADINGS.items():
        alternatives = "|".join(re.escape(item) for item in headings)
        for match in re.finditer(rf"(?im)^\s*(?:\d+(?:\.\d+)*\s+)?(?:{alternatives})\s*[:.]?\s*$", source):
            matches.append((match.start(), match.end(), section))
    matches.sort()
    if not matches:
        return {"body": source}
    result: dict[str, str] = {}
    if matches[0][0] > 0:
        result["front_matter"] = source[: matches[0][0]].strip()
    for index, (_, end, section) in enumerate(matches):
        next_start = matches[index + 1][0] if index + 1 < len(matches) else len(source)
        value = source[end:next_start].strip()
        if value:
            result[section] = (result.get(section, "") + "\n" + value).strip()
    return result


def artifact_counts(text: str) -> dict[str, int]:
    source = text or ""
    return {
        "urls": len(URL_RE.findall(source)), "dois": len(DOI_RE.findall(source)),
        "issn": len(ISSN_RE.findall(source)), "licenses": len(LICENSE_RE.findall(source)),
        "repository_ids": len(REPOSITORY_RE.findall(source)), "emails": len(EMAIL_RE.findall(source)),
        "bibliographic_ids": len(BIBLIOGRAPHIC_ID_RE.findall(source)),
        "editorial_lines": len(EDITORIAL_LINE_RE.findall(source)), "broken_tokens": len(BROKEN_TOKEN_RE.findall(source)),
    }
