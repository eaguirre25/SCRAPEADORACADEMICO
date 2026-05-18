#!/usr/bin/env python3
"""Sube a Drive los PDFs de registros ya validados en data/master_records.csv."""
from __future__ import annotations

import os

from main import DRIVE_AVAILABLE, DriveUploader, bulk_download_and_upload, env_flag


def skip_or_fail(message: str) -> None:
    """No bloquear el scraper si Drive no esta configurado, salvo modo estricto."""
    if env_flag("DRIVE_UPLOAD_STRICT"):
        raise SystemExit(message)
    print(f"Drive omitido: {message}")


def main() -> None:
    folder_id = os.getenv("DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        skip_or_fail("falta DRIVE_FOLDER_ID.")
        return
    if not DRIVE_AVAILABLE:
        skip_or_fail("no esta disponible drive_uploader.py o sus dependencias.")
        return

    missing = [
        name for name in ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET", "GOOGLE_REFRESH_TOKEN"]
        if not os.getenv(name, "").strip()
    ]
    if missing:
        skip_or_fail("faltan secretos de Google OAuth: " + ", ".join(missing) + ".")
        return

    try:
        uploader = DriveUploader(folder_id)
    except Exception as exc:
        skip_or_fail(f"no se pudo conectar con Google Drive ({exc}).")
        return
    print("Google Drive conectado. Subiendo PDFs validados...")
    bulk_download_and_upload(uploader)


if __name__ == "__main__":
    main()
