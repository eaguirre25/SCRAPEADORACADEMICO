#!/usr/bin/env python3
"""Sube a Drive los PDFs de registros ya validados en data/master_records.csv."""
from __future__ import annotations

import os

from main import DRIVE_AVAILABLE, DriveUploader, bulk_download_and_upload


def main() -> None:
    folder_id = os.getenv("DRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        raise SystemExit("Falta DRIVE_FOLDER_ID. No se puede subir a Google Drive.")
    if not DRIVE_AVAILABLE:
        raise SystemExit("No esta disponible drive_uploader.py o sus dependencias.")

    uploader = DriveUploader(folder_id)
    print("Google Drive conectado. Subiendo PDFs validados...")
    bulk_download_and_upload(uploader)


if __name__ == "__main__":
    main()
