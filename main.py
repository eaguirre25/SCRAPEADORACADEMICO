#!/usr/bin/env python3
"""
Scraper acumulativo sobre dirección escolar / gestión escolar.

Qué hace
- Consulta OpenAlex con varios términos de búsqueda.
- Recupera trabajos publicados desde 2020-01-01.
- Mantiene una base maestra acumulativa en CSV.
- Mantiene un índice de IDs ya vistos en JSON.
- Genera y actualiza un Excel acumulativo (publicaciones.xlsx).
- Adjunta el Excel al correo diario.
- Descarga PDFs en acceso abierto y los sube a Google Drive (opcional).
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
from email import encoders
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import requests
import openpyxl
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

# Drive uploader: se activa solo si existe drive_uploader.py y DRIVE_FOLDER_ID
try:
    from drive_uploader import DriveUploader
    DRIVE_AVAILABLE = True
except ImportError:
    DRIVE_AVAILABLE = False

# ── Configuración ─────────────────────────────────────────────────────────────

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
EXCEL_FILE = DATA_DIR / "publicaciones.xlsx"
PDFS_DIR = DATA_DIR / "pdfs"

# Campos del CSV — compatibles con registros viejos (is_oa y pdf_url pueden estar vacíos)
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
    "is_oa",
    "pdf_url",
]

# ── Helpers generales ─────────────────────────────────────────────────────────

def as_dict(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ensure_storage() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PDFS_DIR.mkdir(parents=True, exist_ok=True)

    if not MASTER_CSV.exists():
        with MASTER_CSV.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            writer.writeheader()

    if not SEEN_IDS_JSON.exists():
        SEEN_IDS_JSON.write_text("{}", encoding="utf-8")


# ── Persistencia CSV / JSON ───────────────────────────────────────────────────

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
        with MASTER_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get("title", "")
                year = row.get("publication_year", "")
                signatures.add(build_signature(title, year))
    except Exception as e:
        print(f"Error leyendo signatures: {e}")
    return signatures


def append_master_records(records: List[Dict[str, Any]]) -> None:
    if not records:
        return
    with MASTER_CSV.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        for record in records:
            writer.writerow({k: record.get(k, "") for k in CSV_FIELDS})


def count_master_records() -> int:
    if not MASTER_CSV.exists():
        return 0
    try:
        with MASTER_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            return sum(1 for _ in csv.DictReader(f))
    except Exception:
        return 0


def read_all_records() -> List[Dict[str, str]]:
    """Lee todos los registros del CSV maestro.
    Compatible con CSVs viejos que no tienen is_oa ni pdf_url."""
    if not MASTER_CSV.exists():
        print("CSV maestro no encontrado.")
        return []
    try:
        with MASTER_CSV.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            print(f"CSV leído: {len(rows)} registros, campos: {reader.fieldnames}")
            return rows
    except Exception as e:
        print(f"Error leyendo CSV maestro: {e}")
        return []


# ── Normalización ─────────────────────────────────────────────────────────────

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
        raw_name = (
            author.get("display_name", "")
            or authorship.get("raw_author_name", "")
            or ""
        )
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


# ── OpenAlex ──────────────────────────────────────────────────────────────────

def query_openalex(search_term: str, from_date: str) -> List[Dict[str, Any]]:
    works: List[Dict[str, Any]] = []
    cursor = "*"
    page_count = 0
    headers = build_headers()

    while True:
        params = {
            "search": f'"{search_term}"',
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


def fetch_oa_info_by_doi(doi: str) -> Tuple[bool, str]:
    """Consulta OpenAlex por DOI para obtener is_oa y pdf_url de un registro viejo."""
    if not doi:
        return False, ""
    try:
        url = f"https://api.openalex.org/works/https://doi.org/{doi}"
        resp = requests.get(url, headers=build_headers(), timeout=15)
        if resp.status_code != 200:
            return False, ""
        data = resp.json()
        oa = as_dict(data.get("open_access"))
        is_oa = bool(oa.get("is_oa", False))
        primary = as_dict(data.get("primary_location"))
        pdf_url = primary.get("pdf_url") or oa.get("oa_url") or ""
        return is_oa, str(pdf_url)
    except Exception:
        return False, ""


def extract_record_info(work: Dict[str, Any], search_term: str) -> Dict[str, Any]:
    ids = as_dict(work.get("ids"))
    openalex_id = str(work.get("id", "")).strip()
    doi = normalize_doi(ids.get("doi"))

    primary_location = as_dict(work.get("primary_location"))
    source = as_dict(primary_location.get("source"))
    host_venue = as_dict(work.get("host_venue"))

    origin = source.get("display_name") or host_venue.get("display_name") or ""
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

    oa_info = as_dict(work.get("open_access"))
    is_oa = bool(oa_info.get("is_oa", False))
    pdf_url = primary_location.get("pdf_url") or oa_info.get("oa_url") or ""

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
        "is_oa": is_oa,
        "pdf_url": pdf_url,
    }


# ── Recolección principal ─────────────────────────────────────────────────────

def collect_new_records() -> Tuple[List[Dict[str, Any]], int]:
    ensure_storage()

    seen_ids = load_seen_ids()
    title_year_signatures = load_existing_signatures()
    new_records: List[Dict[str, Any]] = []

    for term in SEARCH_TERMS:
        print(f"Buscando: {term}")
        works = query_openalex(term, START_DATE)
        print(f"  {len(works)} resultados para '{term}'")

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


# ── Excel acumulativo ─────────────────────────────────────────────────────────

EXCEL_HEADERS = [
    "Título", "Año", "Fecha publicación", "Autores", "Revista/Fuente",
    "Tipo", "Término búsqueda", "DOI", "URL", "Acceso abierto",
    "PDF URL", "Abstract", "Palabras clave", "Fecha registro",
]
EXCEL_KEYS = [
    "title", "publication_year", "publication_date", "authors", "origin",
    "document_type", "search_term", "doi", "url", "is_oa",
    "pdf_url", "abstract", "keywords", "first_seen_date",
]


def update_excel(new_record_ids: Set[str]) -> None:
    """Reconstruye el Excel completo desde el CSV maestro."""
    all_records = read_all_records()

    if not all_records:
        print("ADVERTENCIA: No se encontraron registros para generar el Excel.")
        return

    print(f"Generando Excel con {len(all_records)} registros...")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Publicaciones"

    # Cabecera
    header_fill = PatternFill("solid", fgColor="1F4E79")
    header_font = Font(bold=True, color="FFFFFF", size=10)
    for col, header in enumerate(EXCEL_HEADERS, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)

    ws.row_dimensions[1].height = 28
    ws.freeze_panes = "A2"

    new_fill = PatternFill("solid", fgColor="FFF2CC")

    for row_idx, record in enumerate(all_records, 2):
        is_new = record.get("record_id", "") in new_record_ids
        for col_idx, key in enumerate(EXCEL_KEYS, 1):
            val = record.get(key, "") or ""
            if key == "is_oa":
                val = "Sí" if str(val).lower() in ("true", "1", "yes", "sí") else "No"
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.alignment = Alignment(
                vertical="top",
                wrap_text=(key in ("title", "abstract", "keywords")),
            )
            if is_new:
                cell.fill = new_fill

    # Anchos de columna
    col_widths = [55, 6, 14, 40, 30, 12, 18, 38, 38, 12, 38, 60, 40, 14]
    for i, w in enumerate(col_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    try:
        wb.save(EXCEL_FILE)
        print(f"Excel guardado: {EXCEL_FILE} ({len(all_records)} registros)")
    except Exception as e:
        print(f"Error al guardar Excel: {e}")


# ── Descarga de PDFs ──────────────────────────────────────────────────────────

def download_pdf(record: Dict[str, Any]) -> Optional[Path]:
    pdf_url = str(record.get("pdf_url", "")).strip()
    if not pdf_url:
        return None

    raw_name = (
        str(record.get("doi") or record.get("record_id") or record.get("openalex_id") or "unknown")
        .replace("/", "_")
        .replace(":", "_")
        .replace(" ", "_")
    )
    dest = PDFS_DIR / f"{raw_name}.pdf"

    if dest.exists():
        return dest

    try:
        resp = requests.get(pdf_url, timeout=30, stream=True)
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")
        if "pdf" not in content_type and not pdf_url.lower().endswith(".pdf"):
            return None
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        print(f"  PDF descargado: {dest.name}")
        return dest
    except Exception as exc:
        print(f"  No se pudo descargar PDF ({pdf_url}): {exc}")
        return None


def bulk_download_and_upload(uploader: Optional[Any]) -> None:
    """
    Procesa TODOS los registros del CSV:
    - Si tienen pdf_url: descarga y sube.
    - Si tienen DOI pero no pdf_url: consulta OpenAlex para obtenerlo.
    Usa una pausa entre consultas para no saturar la API.
    """
    all_records = read_all_records()
    print(f"\nDescarga masiva de PDFs: procesando {len(all_records)} registros...")

    ok = 0
    skipped = 0

    for i, record in enumerate(all_records):
        pdf_url = str(record.get("pdf_url", "")).strip()
        is_oa_raw = str(record.get("is_oa", "")).lower()
        is_oa = is_oa_raw in ("true", "1", "yes", "sí")

        # Si el registro es viejo y no tiene pdf_url, intentamos obtenerlo por DOI
        if not pdf_url and not is_oa:
            doi = str(record.get("doi", "")).strip()
            if doi:
                is_oa, pdf_url = fetch_oa_info_by_doi(doi)
                time.sleep(0.3)  # pausa cortesía con la API

        if not pdf_url:
            skipped += 1
            continue

        pdf_path = download_pdf({**record, "pdf_url": pdf_url})
        if pdf_path:
            ok += 1
            if uploader:
                try:
                    uploader.upload(pdf_path)
                except Exception as exc:
                    print(f"  Error subiendo a Drive: {exc}")

        # Progreso cada 100 registros
        if (i + 1) % 100 == 0:
            print(f"  Procesados {i + 1}/{len(all_records)} — PDFs descargados: {ok}")

    print(f"Descarga masiva completada: {ok} PDFs descargados, {skipped} sin PDF disponible.")


# ── Correo electrónico ────────────────────────────────────────────────────────

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
        lines.append("Se adjunta el Excel actualizado con todos los registros.")
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
    lines.append("(Ver Excel adjunto para el listado completo.)")
    lines.append("")

    for i, rec in enumerate(sorted_records[:EMAIL_ITEM_LIMIT], start=1):
        authors = rec.get("authors") or "Autoría no disponible"
        title = rec.get("title") or "Sin título"
        origin = rec.get("origin") or "Origen no disponible"
        year = rec.get("publication_year") or "s/f"
        doi = rec.get("doi") or "Sin DOI"
        url = rec.get("url") or "Sin URL"
        is_oa = "Sí" if rec.get("is_oa") else "No"

        lines.append(f"{i}. {title} ({year})")
        lines.append(f"   Autores: {authors}")
        lines.append(f"   Fuente: {origin}")
        lines.append(f"   DOI: {doi}")
        lines.append(f"   URL: {url}")
        lines.append(f"   Acceso abierto: {is_oa}")
        lines.append("")

    if len(sorted_records) > EMAIL_ITEM_LIMIT:
        lines.append(
            f"Hay {len(sorted_records) - EMAIL_ITEM_LIMIT} novedades adicionales en el Excel adjunto."
        )

    return "\n".join(lines)


def send_email(
    subject: str,
    body: str,
    gmail_user: str,
    gmail_password: str,
    recipient: str,
) -> None:
    msg = MIMEMultipart()
    msg["Subject"] = subject
    msg["From"] = gmail_user
    msg["To"] = recipient
    msg.attach(MIMEText(body, _subtype="plain", _charset="utf-8"))

    if EXCEL_FILE.exists():
        with open(EXCEL_FILE, "rb") as f:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(f.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename={EXCEL_FILE.name}",
        )
        msg.attach(part)
        print(f"Excel adjuntado ({EXCEL_FILE.stat().st_size / 1024:.1f} KB)")
    else:
        print("ADVERTENCIA: Excel no encontrado, se envía sin adjunto.")

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as server:
        server.ehlo()
        server.starttls()
        server.ehlo()
        server.login(gmail_user, gmail_password)
        server.sendmail(gmail_user, [recipient], msg.as_string())


# ── Flujo principal ───────────────────────────────────────────────────────────

def main() -> None:
    # 1. Buscar novedades en OpenAlex
    new_records, total_records = collect_new_records()
    new_record_ids = {str(r.get("record_id", "")) for r in new_records}

    # 2. Generar Excel con todos los registros
    update_excel(new_record_ids)

    # 3. Inicializar uploader de Drive (si está configurado)
    drive_folder_id = os.getenv("DRIVE_FOLDER_ID", "").strip()
    uploader = None
    if DRIVE_AVAILABLE and drive_folder_id:
        try:
            uploader = DriveUploader(drive_folder_id)
            print("Google Drive conectado.")
        except Exception as exc:
            print(f"Drive no disponible: {exc}")

    # 4. Descarga masiva: procesa TODOS los registros del CSV
    #    (para registros viejos sin pdf_url, consulta OpenAlex por DOI)
    #    En corridas siguientes solo descargará los que no existan todavía en data/pdfs/
    bulk_download_and_upload(uploader)

    # 5. Enviar correo con Excel adjunto
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
