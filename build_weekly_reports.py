#!/usr/bin/env python3
"""Junta las selecciones semanales de lecturas en docs/weekly_reports.json.

Cada semana se agrega un archivo nuevo en data/weekly_reports/, sin tocar los
anteriores:

- AAAA-MM-DD.md: el texto de la selección tal como se envía por correo
  (Markdown). Cada recomendación es un ítem numerado con la referencia APA en
  negrita, seguido opcionalmente de «DOI: …» y de la explicación (con o sin
  «Por qué importa:»). Se reconocen las secciones «Prioridad de lectura».
- AAAA-MM-DD.json: la misma información ya estructurada
  ({date, title, items: [{title, authors, year, apa, why, doi, url}]}).

Así quien redacta la selección (p. ej., una tarea programada de ChatGPT) solo
crea un archivo pequeño y no necesita leer ni reescribir el acumulado.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

SRC = Path("data/weekly_reports")
OUT = Path("docs/weekly_reports.json")
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s<>\"*]+")
ITEM_RE = re.compile(r"^\s*(\d+)\.\s+\*\*(.+?)\*\*\s*$")
STOP_RE = re.compile(r"^\s*(#{1,6}\s|\*\*(prioridad|estado|sincronizaci)|(prioridad de lectura|estado de biblioteca|sincronizaci))", re.I)


def plain(text: str) -> str:
    """Quita marcas Markdown de negrita/cursiva conservando el texto."""
    text = re.sub(r"\*\*|__", "", text)
    text = re.sub(r"(?<![\w/])_([^_]+?)_(?![\w/])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def clean_doi(value: str) -> str:
    return value.rstrip(".,;)]*_").lower()


def parse_reference(raw: str) -> dict:
    """Separa autores, año y título de una referencia APA en Markdown."""
    m = re.match(r"\s*(.+?)\s*\((\d{4})[a-z]?(?:,[^)]*)?\)\.\s*(.*)", raw)
    if not m:
        return {"authors": "", "year": "", "title": plain(raw)}
    authors, year, rest = m.groups()
    if rest.startswith("_"):
        end = rest.find("_", 1)
        title = rest[1:end] if end > 0 else rest
    else:
        cut = [i for i in (rest.find(". _"), rest.find(". http"), rest.find(". In ")) if i > 0]
        title = rest[: min(cut)] if cut else rest.split(". ")[0]
    authors = re.sub(r",\s*&\s*|\s*&\s*", "; ", plain(authors))
    authors = re.sub(r"(\.)\s*,\s*", r"\1; ", authors)
    return {"authors": authors.strip("; "), "year": int(year), "title": plain(title).rstrip(".")}


def parse_markdown(text: str, date: str) -> dict:
    lines = text.splitlines()
    title = next((plain(l.lstrip("#")) for l in lines if l.strip().startswith("#")), "")
    title = title or f"Selección semanal de investigación sobre dirección escolar — {date}"
    items, current, intro, priority = [], None, [], []
    section = "intro"
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#") and plain(stripped.lstrip("#")) == title:
            continue
        m = ITEM_RE.match(line)
        if m:
            current = {"raw": m.group(2), "body": []}
            items.append(current)
            section = "items"
            continue
        if STOP_RE.match(stripped):
            low = plain(stripped).lower()
            section = "priority" if "prioridad" in low else "skip"
            rest = re.sub(r"^#+\s*|^\*\*[^*]+\*\*:?\s*", "", stripped)
            if section == "priority" and rest and "prioridad" not in rest.lower():
                priority.append(rest)
            current = None
            continue
        if not stripped:
            continue
        if section == "intro":
            intro.append(stripped)
        elif section == "items" and current is not None:
            current["body"].append(stripped)
        elif section == "priority":
            priority.append(stripped)
    out_items = []
    for item in items:
        ref = parse_reference(item["raw"])
        doi, why = "", []
        for b in item["body"]:
            if re.match(r"(?i)^doi:\s*", b):
                doi = clean_doi(re.sub(r"(?i)^doi:\s*", "", b))
            else:
                why.append(re.sub(r"(?i)^por qué importa:\s*", "", b))
        if not doi:
            found = DOI_RE.search(item["raw"])
            doi = clean_doi(found.group(0)) if found else ""
        url_match = re.search(r"https?://\S+", item["raw"])
        url = f"https://doi.org/{doi}" if doi else (url_match.group(0).rstrip(".*_") if url_match else "")
        out_items.append({**ref, "apa": plain(item["raw"]), "why": plain(" ".join(why)), "doi": doi, "url": url})
    return {"date": date, "title": title, "intro": plain(" ".join(intro)),
            "priority": plain(" ".join(priority)), "items": out_items}


def load(path: Path) -> dict:
    date = path.stem
    if path.suffix == ".json":
        data = json.loads(path.read_text(encoding="utf-8"))
        data.setdefault("date", date)
        return data
    return parse_markdown(path.read_text(encoding="utf-8"), date)


def main() -> int:
    reports, problems = [], []
    for path in sorted(SRC.glob("*")):
        if path.suffix not in (".md", ".json") or not re.match(r"\d{4}-\d{2}-\d{2}$", path.stem):
            continue
        report = load(path)
        if not report.get("items"):
            problems.append(f"{path.name}: no se reconocieron recomendaciones")
            continue
        report["source_file"] = path.as_posix()
        reports.append(report)
    reports.sort(key=lambda r: r["date"])
    OUT.write_text(json.dumps(reports, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Selecciones semanales: {len(reports)} (última: {reports[-1]['date'] if reports else '—'})")
    for p in problems:
        print("AVISO:", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
