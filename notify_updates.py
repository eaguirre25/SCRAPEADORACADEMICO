#!/usr/bin/env python3
"""Envía el informe por correo usando solo novedades ya validadas."""
from __future__ import annotations

import csv
import os
from pathlib import Path

from main import count_master_records, generate_email_body, send_email


LATEST_RELEVANT_CSV = Path("data") / "latest_relevant_records.csv"


def read_latest_relevant() -> list[dict[str, str]]:
    if not LATEST_RELEVANT_CSV.exists():
        print(f"No existe {LATEST_RELEVANT_CSV}. Se enviará informe sin novedades.")
        return []
    with LATEST_RELEVANT_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def main() -> None:
    records = read_latest_relevant()
    total_records = count_master_records()
    body = generate_email_body(records, total_records)
    subject = "Informe diario – dirección/gestión escolar"

    gmail_user = os.getenv("GMAIL_USER", "").strip()
    gmail_password = (os.getenv("GMAIL_APP_PASSWORD", "") or os.getenv("GMAIL_PASSWORD", "")).strip()
    recipient = os.getenv("RECIPIENT_EMAIL", "").strip()
    if gmail_user and gmail_password and recipient:
        send_email(subject, body, gmail_user, gmail_password, recipient)
        print(f"Correo enviado con {len(records)} novedades validadas.")
    else:
        print("Faltan credenciales de correo. Informe en consola:")
        print(body)


if __name__ == "__main__":
    main()
