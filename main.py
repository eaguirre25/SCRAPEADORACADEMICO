#!/usr/bin/env python3
"""
Script to collect academic works related to school leadership and
management from OpenAlex and send daily email reports.

The script performs the following operations:

1. Queries the OpenAlex API for predefined search terms within a given date
   range (default from 2020-01-01 to today).
2. Stores retrieved works (identified by DOI or OpenAlex ID) in a JSON file to
   avoid duplicates across runs.
3. Generates a summary of new works and sends an email notification via Gmail
   SMTP if new items are found.  Email credentials and recipient address are
   supplied via environment variables.

The OpenAlex API is CC0 licensed and allows free access for academic
applications【280946531337324†L250-L346】.  This script abides by their usage guidelines by retrieving
results in batches and limiting the number of requests per run.
"""

from __future__ import annotations

import json
import os
import time
import smtplib
from email.mime.text import MIMEText
from typing import List, Dict, Any
from datetime import datetime, date

import requests
import pandas as pd

# Configure search parameters
SEARCH_TERMS: List[str] = [
    "gestión escolar",
    "dirección escolar",
    "gestión educativa",
    "school management",
    "educational leadership",
]

# Start date for the search (inclusive)
START_DATE: str = "2020-01-01"

# Maximum number of pages to retrieve per search term.  OpenAlex returns up to
# 200 items per page (configured via per_page parameter).  Adjust this limit
# to control the volume of data and API usage.  None means unlimited.
MAX_PAGES_PER_TERM: int | None = 3

# Directory to store data
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SCRAPED_RECORDS_FILE = os.path.join(DATA_DIR, "scraped_records.json")


def ensure_data_dir() -> None:
    """Ensure the data directory exists."""
    os.makedirs(DATA_DIR, exist_ok=True)


def load_scraped_records() -> Dict[str, Dict[str, Any]]:
    """Load previously scraped records from JSON file.

    Returns a dictionary keyed by DOI or OpenAlex ID.
    """
    if not os.path.exists(SCRAPED_RECORDS_FILE):
        return {}
    with open(SCRAPED_RECORDS_FILE, "r", encoding="utf-8") as f:
        try:
            data = json.load(f)
            return data
        except json.JSONDecodeError:
            return {}


def save_scraped_records(records: Dict[str, Dict[str, Any]]) -> None:
    """Save scraped records to JSON file."""
    with open(SCRAPED_RECORDS_FILE, "w", encoding="utf-8") as f:
        json.dump(records, f, ensure_ascii=False, indent=2)


def query_openalex(search_term: str, from_date: str) -> List[Dict[str, Any]]:
    """Query OpenAlex for works matching the search term since `from_date`.

    The function paginates through results using the `cursor` parameter and
    returns a list of works.  It stops when `meta["next_cursor"]` is None or
    when the maximum number of pages defined by `MAX_PAGES_PER_TERM` is
    reached.  A brief delay is introduced between requests to respect API
    etiquette.

    Args:
        search_term: The phrase to search for.  Quotes are added to enforce
            phrase matching, which improves relevance (e.g., "gestión escolar").
        from_date: An ISO-formatted date string (YYYY-MM-DD) indicating the
            earliest publication date to return.

    Returns:
        A list of work metadata dictionaries.
    """
    works: List[Dict[str, Any]] = []
    cursor = "*"  # initial cursor
    page_count = 0
    while True:
        params = {
            "search": f'"{search_term}"',
            "filter": f"from_publication_date:{from_date}",
            "per_page": 200,
            "cursor": cursor,
        }
        response = requests.get("https://api.openalex.org/works", params=params, timeout=30)
        if response.status_code != 200:
            print(f"Error querying OpenAlex for '{search_term}': {response.status_code}")
            break
        data = response.json()
        batch = data.get("results", [])
        works.extend(batch)

        next_cursor = data.get("meta", {}).get("next_cursor")
        page_count += 1
        # Stop if no more pages or max pages reached
        if not next_cursor or (MAX_PAGES_PER_TERM is not None and page_count >= MAX_PAGES_PER_TERM):
            break
        cursor = next_cursor
        # Respectful delay between requests (OpenAlex allows up to 1 request per second)
        time.sleep(1)

    return works


def extract_record_info(work: Dict[str, Any]) -> Dict[str, Any]:
    """Extract relevant fields from an OpenAlex work record.

    Args:
        work: The raw work dictionary returned by OpenAlex.

    Returns:
        A dictionary containing a unique identifier, title, year, date,
        DOI (if available), and a URL.
    """
    # Determine unique ID: prefer DOI if available, else use OpenAlex ID
    doi = None
    ids = work.get("ids", {})
    doi_url = ids.get("doi")
    if doi_url:
        # The DOI is the part after https://doi.org/
        doi = doi_url.split("doi.org/")[-1]
    unique_id = doi if doi else work.get("id")

    # Title and date
    title = work.get("title") or work.get("display_name")
    pub_year = work.get("publication_year")
    pub_date = work.get("publication_date")
    # Fallback: use date parts from issued if available
    if not pub_date:
        pub_date = work.get("biblio", {}).get("published_print") or work.get("biblio", {}).get("published_online")

    # URLs: use primary location (landing page or PDF)
    primary_loc = work.get("primary_location", {})
    url = None
    if primary_loc:
        url = primary_loc.get("landing_page_url") or primary_loc.get("pdf_url")
    if not url:
        # fallback to DOI link if available
        if doi:
            url = f"https://doi.org/{doi}"
        else:
            url = work.get("id")

    return {
        "id": unique_id,
        "title": title,
        "publication_year": pub_year,
        "publication_date": pub_date,
        "doi": doi,
        "url": url,
    }


def collect_new_records() -> List[Dict[str, Any]]:
    """Run searches for all terms and return a list of newly found records.

    This function compares results against the local database of previously
    scraped records and only returns those not seen before.  The local
    database is updated at the end of the function.

    Returns:
        A list of dictionaries with information about new works.
    """
    ensure_data_dir()
    existing_records = load_scraped_records()
    new_records: List[Dict[str, Any]] = []

    for term in SEARCH_TERMS:
        print(f"Searching for term: {term}")
        works = query_openalex(term, START_DATE)
        print(f"  Retrieved {len(works)} works for '{term}'")
        for work in works:
            record = extract_record_info(work)
            uid = record["id"]
            if uid not in existing_records:
                existing_records[uid] = record
                new_records.append(record)

    # Save updated records database
    save_scraped_records(existing_records)
    return new_records


def generate_email_body(new_records: List[Dict[str, Any]]) -> str:
    """Create a formatted email body summarizing new records."""
    lines = []
    header = f"Informe de nuevas publicaciones sobre dirección/gestión escolar - {date.today().isoformat()}"
    lines.append(header)
    lines.append("")
    if not new_records:
        lines.append("No se encontraron nuevas publicaciones en la última búsqueda.")
    else:
        lines.append(f"Se han encontrado {len(new_records)} nuevas publicaciones:")
        lines.append("")
        for i, rec in enumerate(sorted(new_records, key=lambda x: (x.get("publication_year", 0), x.get("title", "")), reverse=True), start=1):
            title = rec.get("title")
            year = rec.get("publication_year") or "s/f"
            url = rec.get("url")
            lines.append(f"{i}. {title} ({year})")
            lines.append(f"   URL: {url}")
            lines.append("")
    body = "\n".join(lines)
    return body


def send_email(subject: str, body: str, gmail_user: str, gmail_password: str, recipient: str) -> None:
    """Send an email via Gmail SMTP with the specified subject and body."""
    msg = MIMEText(body, _charset="utf-8")
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(gmail_user, gmail_password)
            server.sendmail(gmail_user, [recipient], msg.as_string())
            print("Informe enviado por correo electrónico.")
    except Exception as e:
        print(f"Error al enviar el correo: {e}")


def main() -> None:
    """Entry point of the script."""
    new_records = collect_new_records()
    gmail_user = os.getenv("GMAIL_USER")
    gmail_password = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("GMAIL_PASSWORD")
    recipient = os.getenv("RECIPIENT_EMAIL")
    # Generate email content
    body = generate_email_body(new_records)
    subject = "Informe diario de nuevas publicaciones sobre dirección/gestión escolar"
    # If email parameters are present, send email
    if gmail_user and gmail_password and recipient:
        send_email(subject, body, gmail_user, gmail_password, recipient)
    else:
        # If credentials are missing, output the report to stdout
        print("Variables de entorno para correo no definidas; mostrando informe en consola:")
        print(body)


if __name__ == "__main__":
    main()
