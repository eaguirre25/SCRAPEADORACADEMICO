#!/usr/bin/env python3
"""
Scraper acumulativo sobre dirección escolar / gestión escolar.

Qué hace
- Consulta OpenAlex con varios términos de búsqueda.
- Recupera trabajos publicados desde 2020-01-01.
- Mantiene una base maestra acumulativa en CSV.
- Mantiene un índice de IDs ya vistos en JSON.
- Envía por mail solo las novedades de cada corrida.
"""

from __future__ import annotations

import csv
import json
import os
import re
import smtplib
import time
from datetime import date
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests

SEARCH_TERMS: List[str] = [
    "gestión escolar",
    "dirección escolar",
    "gestión educativa",
    "school management",
    "educational leadership",
]

START_DATE = "2020-01-01"
MAX_PAGES_PER_TERM: Optional[int] = 3
EMAIL_ITEM_LIMIT = 50

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
MASTER_CSV = DATA_DIR / "master_records.csv"
SEEN_IDS_JSON = DATA_DIR / "seen_ids.json"

CSV_FIELDS = [
    "record_id",
    "first_seen_date",
    "search_term",
    "origin",
    "document_type",
    "authors",
    "title",
    "abstract",
    "keywords",
    "publication_year",
    "publication_date",
    "doi",
    "url",
    "openalex_id",
]


def as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    if not MASTER_CSV.exists():
        with MASTER_CSV.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

    if not SEEN_IDS_JSON.exists():
        SEEN_IDS_JSON.write_text("{}", encoding="utf-8")


def load_seen_ids() -> Set[str]:
    try:
        data = json.loads(SEEN_IDS_JSON.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return set(data.keys())
    except Exception:
        pass
    return set()


def save_seen_ids(seen_ids: Set[str]) -> None:
    payload = {item: True for item in sorted(seen_ids)}
    SEEN_IDS_JSON.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_existing_signatures() -> Set[str]:
    signatures: Set[str] = set()

    if not MASTER_CSV.exists():
        return signatures

    try:
        with MASTER_CSV.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get("title", "")
                year = row.get("publication_year", "")
                signatures.add(build_signature(title, year))
    except Exception:
        pass

    return signatures


def append_master_records(records: List[Dict[str, Any]]) -> None:
    if not records:
        return

    with MASTER_CSV.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        for record in records:
            writer.writerow(record)


def count_master_records() -> int:
    if not MASTER_CSV.exists():
        return 0

    try:
        with MASTER_CSV.open("r", encoding="utf-8", newline="") as f:
            reader = csv.DictReader(f)
            return sum(1 for _ in reader)
    except Exception:
        return 0


def build_headers() -> Dict[str, str]:
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    if gmail_user:
        return {"User-Agent": f"academic-scraper/2.0 (mailto:{gmail_user})"}
    return {"User-Agent": "academic-scraper/2.0"}


def normalize_doi(doi_value: Optional[str]) -> str:
    if not doi_value:
        return ""

    doi_value = doi_value.strip()
    if "doi.org/" in doi_value:
        doi_value = doi_value.split("doi.org/")[-1]

    return doi_value.lower().strip()


def normalize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = text.casefold().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def build_signature(title: Optional[str], year: Any) -> str:
    return f"{normalize_text(title)}::{str(year or '').strip()}"


def reconstruct_abstract(abstract_inverted_index: Any) -> str:
    if not isinstance(abstract_inverted_index, dict):
        return ""

    tokens: List[Tuple[int, str]] = []
    for word, positions in abstract_inverted_index.items():
        if not isinstance(positions, list):
            continue
        for pos in positions:
            if isinstance(pos, int):
                tokens.append((pos, word))

    if not tokens:
        return ""

    tokens.sort(key=lambda x: x[0])
    return " ".join(word for _, word in tokens)


def extract_authors(work: Dict[str, Any]) -> str:
    authorships = work.get("authorships", [])
    if not isinstance(authorships, list):
        return ""

    names: List[str] = []
    for authorship in authorships:
        if not isinstance(authorship, dict):
            continue

        author = as_dict(authorship.get("author"))
        raw_name = author.get("display_name", "") or authorship.get("raw_author_name", "") or ""
        raw_name = str(raw_name).strip()

        if raw_name:
            names.append(raw_name)

    return "; ".join(names)


def extract_keywords(work: Dict[str, Any]) -> str:
    keywords = work.get("keywords", [])
    values: List[str] = []

    if isinstance(keywords, list):
        for item in keywords:
            if isinstance(item, dict):
                name = item.get("display_name", "")
                if name:
                    values.append(str(name).strip())

    if not values:
        topics = work.get("topics", [])
        if isinstance(topics, list):
            for item in topics[:5]:
                if isinstance(item, dict):
                    name = item.get("display_name", "")
                    if name:
                        values.append(str(name).strip())

    cleaned: List[str] = []
    seen: Set[str] = set()
    for value in values:
        norm = normalize_text(value)
        if norm and norm not in seen:
            seen.add(norm)
            cleaned.append(value)

    return "; ".join(cleaned)


def query_openalex(search_term: str, from_date: str) -> List[Dict[str, Any]]:
    works: List[Dict[str, Any]] = []
    cursor = "*"
    page_count = 0
    headers = build_headers()

    while True:
        params = {
            "search": f"\"{search_term}\"",
            "filter": f"from_publication_date:{from_date}",
            "per-page": 200,
            "cursor": cursor,
        }

        try:
            response = requests.get(
                "https://api.openalex.org/works",
                params=params,
                headers=headers,
                timeout=30,
            )
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"Error consultando OpenAlex para '{search_term}': {e}")
            break

        data = response.json()
        batch = data.get("results", [])
        if not isinstance(batch, list):
            break

        works.extend(batch)

        meta = as_dict(data.get("meta"))
        next_cursor = meta.get("next_cursor")

        page_count += 1
        if not next_cursor:
            break

        if MAX_PAGES_PER_TERM is not None and page_count >= MAX_PAGES_PER_TERM:
            break

        cursor = next_cursor
        time.sleep(1)

    return works


def extract_record_info(work: Dict[str, Any], search_term: str) -> Dict[str, Any]:
    ids = as_dict(work.get("ids"))
    openalex_id = str(work.get("id", "")).strip()
    doi = normalize_doi(ids.get("doi"))

    primary_location = as_dict(work.get("primary_location"))
    source = as_dict(primary_location.get("source"))
    host_venue = as_dict(work.get("host_venue"))

    origin = (
        source.get("display_name")
        or host_venue.get("display_name")
        or ""
    )

    document_type = (
        primary_location.get("type")
        or work.get("type_crossref")
        or work.get("type")
        or ""
    )

    title = (work.get("title") or work.get("display_name") or "").strip()
    publication_year = work.get("publication_year") or ""
    publication_date = work.get("publication_date") or ""

    authors = extract_authors(work)
    abstract = reconstruct_abstract(work.get("abstract_inverted_index"))
    keywords = extract_keywords(work)

    url = (
        primary_location.get("landing_page_url")
        or primary_location.get("pdf_url")
        or (f"https://doi.org/{doi}" if doi else "")
        or openalex_id
    )

    record_id = doi or openalex_id

    return {
        "record_id": record_id,
        "first_seen_date": date.today().isoformat(),
        "search_term": search_term,
        "origin": origin,
        "document_type": document_type,
        "authors": authors,
        "title": title,
        "abstract": abstract,
        "keywords": keywords,
        "publication_year": publication_year,
        "publication_date": publication_date,
        "doi": doi,
        "url": url,
        "openalex_id": openalex_id,
    }


def collect_new_records() -> Tuple[List[Dict[str, Any]], int]:
    ensure_storage()

    seen_ids = load_seen_ids()
    title_year_signatures = load_existing_signatures()
    new_records: List[Dict[str, Any]] = []

    for term in SEARCH_TERMS:
        print(f"Searching for term: {term}")
        works = query_openalex(term, START_DATE)
        print(f"  Retrieved {len(works)} works for '{term}'")

        for work in works:
            if not isinstance(work, dict):
                continue

            record = extract_record_info(work, term)
            record_id = str(record.get("record_id", "")).strip()
            signature = build_signature(
                record.get("title", ""),
                record.get("publication_year", ""),
            )

            if not record_id:
                continue

            if record_id in seen_ids:
                continue

            if signature in title_year_signatures:
                seen_ids.add(record_id)
                continue

            new_records.append(record)
            seen_ids.add(record_id)
            title_year_signatures.add(signature)

    append_master_records(new_records)
    save_seen_ids(seen_ids)

    total_records = count_master_records()
    return new_records, total_records


def generate_email_body(new_records: List[Dict[str, Any]], total_records: int) -> str:
    lines: List[str] = []
    lines.append(
        f"Informe diario de novedades sobre dirección/gestión escolar - {date.today().isoformat()}"
    )
    lines.append("")
    lines.append(f"Base acumulada total: {total_records} registros")
    lines.append(f"Nuevos registros en esta corrida: {len(new_records)}")
    lines.append("")

    if not new_records:
        lines.append("No se detectaron novedades respecto de la base acumulada.")
        return "\n".join(lines)

    sorted_records = sorted(
        new_records,
        key=lambda x: (
            str(x.get("publication_date") or ""),
            int(x.get("publication_year") or 0),
            str(x.get("title") or "").casefold(),
        ),
        reverse=True,
    )

    lines.append(f"Se listan hasta {EMAIL_ITEM_LIMIT} novedades más recientes:")
    lines.append("")

    for i, rec in enumerate(sorted_records[:EMAIL_ITEM_LIMIT], start=1):
        authors = rec.get("authors") or "Autoría no disponible"
        title = rec.get("title") or "Sin título"
        origin = rec.get("origin") or "Origen no disponible"
        year = rec.get("publication_year") or "s/f"
        doi = rec.get("doi") or "Sin DOI"
        url = rec.get("url") or "Sin URL"

        lines.append(f"{i}. {title} ({year})")
        lines.append(f"   Autores: {authors}")
        lines.append(f"   Origen: {origin}")
        lines.append(f"   DOI: {doi}")
        lines.append(f"   URL: {url}")
        lines.append("")

    if len(sorted_records) > EMAIL_ITEM_LIMIT:
        lines.append(
            f"Hay {len(sorted_records) - EMAIL_ITEM_LIMIT} novedades adicionales guardadas en la base maestra."
        )

    return "\n".join(lines)


def send_email(subject: str, body: str, gmail_user: str, gmail_password: str, recipient: str) -> None:
    msg = MIMEText(body, _subtype="plain", _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, [recipient], msg.as_string())


def main() -> None:
    new_records, total_records = collect_new_records()

    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_password = (
        os.getenv("GMAIL_APP_PASSWORD", "").strip()
        or os.getenv("GMAIL_PASSWORD", "").strip()
    )
    recipient = os.getenv("RECIPIENT_EMAIL", "").strip()

    body = generate_email_body(new_records, total_records)
    subject = "Informe diario acumulativo de publicaciones sobre dirección/gestión escolar"

    if gmail_user and gmail_password and recipient:
        send_email(subject, body, gmail_user, gmail_password, recipient)
        print("Informe enviado por correo electrónico.")
    else:
        print("Faltan variables de entorno para correo. Informe en consola:")
        print(body)


if __name__ == "__main__":
    main()
