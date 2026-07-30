from __future__ import annotations

import hashlib
import re
import unicodedata
from typing import Any, Mapping


NULL_VALUES = {"", "nan", "none", "null", "na", "n/a"}


def clean_value(value: Any) -> str:
    text = str(value or "").strip()
    return "" if text.casefold() in NULL_VALUES else text


def normalize_doi(value: Any) -> str:
    text = clean_value(value).casefold()
    text = re.sub(r"^https?://(?:dx\.)?doi\.org/", "", text)
    text = re.sub(r"^doi:\s*", "", text)
    return text.strip().rstrip(".,;)")


def normalize_text(value: Any) -> str:
    text = unicodedata.normalize("NFKD", clean_value(value)).encode("ascii", "ignore").decode()
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", text.casefold())).strip()


def first_author(value: Any) -> str:
    return normalize_text(re.split(r"[;|]", clean_value(value), maxsplit=1)[0])


def stable_document_id(record: Mapping[str, Any]) -> str:
    doi = normalize_doi(record.get("doi"))
    if doi:
        return f"doi:{doi}"
    persistent = clean_value(record.get("record_id") or record.get("openalex_id"))
    if persistent:
        digest = hashlib.sha256(persistent.casefold().encode()).hexdigest()[:24]
        return f"record:{digest}"
    title = normalize_text(record.get("title") or record.get("titulo"))
    year = clean_value(record.get("publication_year") or record.get("anio"))
    author = first_author(record.get("authors") or record.get("autores"))
    filename = normalize_text(record.get("filename"))
    basis = "|".join([title, year, author]) if title else "|".join([filename, year, author])
    if not basis.strip("|"):
        raise ValueError("Cannot construct document_id without DOI, persistent id, title, or filename")
    return "hash:" + hashlib.sha256(basis.encode()).hexdigest()[:24]

