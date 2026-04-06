#!/usr/bin/env python3
"""
Scraper académico sobre dirección escolar / gestión escolar.

Qué hace
- Consulta OpenAlex con varios términos de búsqueda.
- Recupera trabajos publicados desde 2020-01-01.
- Guarda los registros ya vistos en un JSON local para no repetirlos.
- Envía un informe por Gmail con las novedades detectadas.

Variables de entorno esperadas
- GMAIL_USER
- GMAIL_APP_PASSWORD   (o GMAIL_PASSWORD)
- RECIPIENT_EMAIL
"""

from __future__ import annotations

import json
import os
import smtplib
import time
from datetime import date
from email.mime.text import MIMEText
from typing import Any, Dict, List, Optional

import requests

SEARCH_TERMS: List[str] = [
    "gestión escolar",
    "dirección escolar",
    "gestión educativa",
    "school management",
    "educational leadership",
]

START_DATE = "2020-01-01"

# Para la primera corrida conviene no dejarlo en None, así no explota por volumen.
# Si luego quieres ampliar, puedes subirlo o dejarlo en None.
MAX_PAGES_PER_TERM: Optional[int] = 3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SCRAPED_RECORDS_FILE = os.path.join(DATA_DIR, "scraped_records.json")


def ensure_data_dir() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)


def load_scraped_records() -> Dict[str, Dict[str, Any]]:
    if not os.path.exists(SCRAPED_RECORDS_FILE):
        return {}

    try:
        with open(SCRAPED_RECORDS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_scraped_records(records: Dict[str, Dict[str, Any]]) -> None:
    with open(SCRAPED_RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def build_headers() -> Dict[str, str]:
    gmail_user = os.getenv("GMAIL_USER", "").strip()
    if gmail_user:
        return {
            "User-Agent": f"academic-scraper/1.0 (mailto:{gmail_user})"
        }
    return {
        "User-Agent": "academic-scraper/1.0"
    }


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

        meta = data.get("meta", {})
        next_cursor = meta.get("next_cursor")

        page_count += 1

        if not next_cursor:
            break

        if MAX_PAGES_PER_TERM is not None and page_count >= MAX_PAGES_PER_TERM:
            break

        cursor = next_cursor
        time.sleep(1)

    return works


def normalize_doi(doi_value: Optional[str]) -> Optional[str]:
    if not doi_value:
        return None

    doi_value = doi_value.strip()

    if "doi.org/" in doi_value:
        doi_value = doi_value.split("doi.org/")[-1]

    return doi_value.lower() or None


def extract_record_info(work: Dict[str, Any]) -> Dict[str, Any]:
    ids = work.get("ids", {}) if isinstance(work.get("ids"), dict) else {}
    doi = normalize_doi(ids.get("doi"))

    openalex_id = work.get("id")
    unique_id = doi or openalex_id

    title = work.get("title") or work.get("display_name") or "Sin título"
    publication_year = work.get("publication_year")
    publication_date = work.get("publication_date")

    primary_location = work.get("primary_location", {})
    if not isinstance(primary_location, dict):
        primary_location = {}

    url = (
        primary_location.get("landing_page_url")
        or primary_location.get("pdf_url")
        or (f"https://doi.org/{doi}" if doi else None)
        or openalex_id
        or ""
    )

    return {
        "id": unique_id,
        "title": title,
        "publication_year": publication_year,
        "publication_date": publication_date,
        "doi": doi,
        "url": url,
    }


def collect_new_records() -> List[Dict[str, Any]]:
    ensure_data_dir()
    existing_records = load_scraped_records()
    new_records: List[Dict[str, Any]] = []

    for term in SEARCH_TERMS:
        print(f"Searching for term: {term}")
        works = query_openalex(term, START_DATE)
        print(f"  Retrieved {len(works)} works for '{term}'")

        for work in works:
            record = extract_record_info(work)
            uid = record.get("id")

            if not uid:
                continue

            if uid not in existing_records:
                existing_records[uid] = record
                new_records.append(record)

    save_scraped_records(existing_records)
    return new_records


def generate_email_body(new_records: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    header = (
        f"Informe de nuevas publicaciones sobre dirección/gestión escolar - "
        f"{date.today().isoformat()}"
    )
    lines.append(header)
    lines.append("")

    if not new_records:
        lines.append("No se encontraron nuevas publicaciones en la última búsqueda.")
        return "\n".join(lines)

    lines.append(f"Se han encontrado {len(new_records)} nuevas publicaciones:")
    lines.append("")

    sorted_records = sorted(
        new_records,
        key=lambda x: (
            int(x.get("publication_year") or 0),
            str(x.get("title") or "").casefold(),
        ),
        reverse=True,
    )

    for i, rec in enumerate(sorted_records, start=1):
        title = rec.get("title") or "Sin título"
        year = rec.get("publication_year") or "s/f"
        url = rec.get("url") or "Sin URL"

        lines.append(f"{i}. {title} ({year})")
        lines.append(f"   URL: {url}")
        lines.append("")

    return "\n".join(lines)


def send_email(
    subject: str,
    body: str,
    gmail_user: str,
    gmail_password: str,
    recipient: str,
) -> None:
    msg = MIMEText(body, _subtype="plain", _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient

    try:
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, [recipient], msg.as_string())
        print("Informe enviado por correo electrónico.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")
        raise


def main() -> None:
    new_records = collect_new_records()

    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_password = (
        os.getenv("GMAIL_APP_PASSWORD", "").strip()
        or os.getenv("GMAIL_PASSWORD", "").strip()
    )
    recipient = os.getenv("RECIPIENT_EMAIL", "").strip()

    body = generate_email_body(new_records)
    subject = "Informe diario de nuevas publicaciones sobre dirección/gestión escolar"

    if gmail_user and gmail_password and recipient:
        send_email(subject, body, gmail_user, gmail_password, recipient)
    else:
        print("Faltan variables de entorno para correo. Informe en consola:")
        print(body)


if __name__ == "__main__":
    main()
