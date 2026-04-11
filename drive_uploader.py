"""
drive_uploader.py
Sube archivos a una carpeta de Google Drive usando una service account.

Configuración (una sola vez):
  1. En Google Cloud Console: habilitar Google Drive API
  2. Crear Service Account → descargar JSON de credenciales
  3. Guardar el JSON como  data/credentials.json
     o definir la variable de entorno GOOGLE_CREDENTIALS_FILE
  4. Compartir la carpeta de Drive con el client_email del JSON (rol Editor)
  5. Agregar el ID de la carpeta como secreto DRIVE_FOLDER_ID en GitHub
"""

from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]
CREDENTIALS_FILE = os.environ.get(
    "GOOGLE_CREDENTIALS_FILE",
    str(Path("data") / "credentials.json"),
)


class DriveUploader:
    """Sube archivos a una carpeta de Google Drive."""

    def __init__(self, folder_id: str) -> None:
        if not folder_id:
            raise ValueError("folder_id no puede estar vacío.")
        self.folder_id = folder_id
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES
        )
        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self._uploaded: set[str] = self._list_existing_files()

    def _list_existing_files(self) -> set[str]:
        try:
            result = (
                self.service.files()
                .list(
                    q=f"'{self.folder_id}' in parents and trashed=false",
                    fields="files(name)",
                    pageSize=1000,
                )
                .execute()
            )
            return {f["name"] for f in result.get("files", [])}
        except Exception as exc:
            log.warning("No se pudo listar archivos en Drive: %s", exc)
            return set()

    def upload(self, file_path: Path) -> Optional[str]:
        """Sube un archivo. Omite si ya existe con el mismo nombre."""
        if file_path.name in self._uploaded:
            log.debug("Ya existe en Drive: %s", file_path.name)
            return None

        mime_type, _ = mimetypes.guess_type(str(file_path))
        mime_type = mime_type or "application/octet-stream"

        metadata = {"name": file_path.name, "parents": [self.folder_id]}
        media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)

        try:
            result = (
                self.service.files()
                .create(body=metadata, media_body=media, fields="id")
                .execute()
            )
            file_id = result.get("id")
            self._uploaded.add(file_path.name)
            log.info("Subido a Drive: %s (id=%s)", file_path.name, file_id)
            return file_id
        except Exception as exc:
            log.error("Error al subir %s a Drive: %s", file_path.name, exc)
            return None
