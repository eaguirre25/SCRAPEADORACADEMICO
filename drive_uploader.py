"""
drive_uploader.py — versión OAuth2 (usa la cuota de tu cuenta de Google).

Secretos necesarios en GitHub (reemplazan a GOOGLE_CREDENTIALS_JSON):
  GOOGLE_CLIENT_ID      → client_id del JSON OAuth descargado
  GOOGLE_CLIENT_SECRET  → client_secret del JSON OAuth descargado
  GOOGLE_REFRESH_TOKEN  → obtenido ejecutando get_token.py una sola vez
"""

from __future__ import annotations

import logging
import mimetypes
import os
from pathlib import Path
from typing import Optional

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

log = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class DriveUploader:
    """Sube archivos a Google Drive usando OAuth2 (cuenta de usuario)."""

    def __init__(self, folder_id: str) -> None:
        if not folder_id:
            raise ValueError("folder_id no puede estar vacío.")
        self.folder_id = folder_id

        client_id = os.environ["GOOGLE_CLIENT_ID"]
        client_secret = os.environ["GOOGLE_CLIENT_SECRET"]
        refresh_token = os.environ["GOOGLE_REFRESH_TOKEN"]

        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        # Refresca el access token automáticamente
        creds.refresh(Request())

        self.service = build("drive", "v3", credentials=creds, cache_discovery=False)
        self._uploaded: set[str] = self._list_existing_files()
        log.info("Drive conectado. Archivos existentes en carpeta: %d", len(self._uploaded))

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
