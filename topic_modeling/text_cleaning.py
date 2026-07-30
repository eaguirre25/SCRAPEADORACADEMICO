from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass


URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
DOI_RE = re.compile(r"(?:https?://doi\.org/)?10\.\d{4,9}/\S+", re.I)
ISSN_RE = re.compile(r"\b(?:ISSN[-\s:]*)?\d{4}-\d{3}[\dX]\b", re.I)
LICENSE_RE = re.compile(r"creative\s+commons|copyright|by-sa|atribuci[oó]n", re.I)
REPOSITORY_RE = re.compile(r"\b(?:oai-pmh|isni)\S*", re.I)
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
    return normalize_space(text)


def clean_for_bertopic(text: str, *, strip_references: bool = False) -> tuple[str, ReferenceRemoval]:
    cleaned = _base_clean(text)
    removal = remove_references(cleaned) if strip_references else ReferenceRemoval(cleaned, False, None, 0.0)
    return normalize_space(removal.text), removal


def clean_for_stm(text: str, *, strip_references: bool = False) -> tuple[str, ReferenceRemoval]:
    cleaned, removal = clean_for_bertopic(text, strip_references=strip_references)
    cleaned = re.sub(r"\b\d+\b", " ", cleaned)
    cleaned = re.sub(r"[^\w\sáéíóúüñçãõàâêô-]", " ", cleaned, flags=re.UNICODE)
    return normalize_space(cleaned.casefold()), removal


def clean_for_display(text: str) -> str:
    return normalize_space(unicodedata.normalize("NFKC", text or "").replace("\x00", " "))

