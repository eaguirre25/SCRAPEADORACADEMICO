"""Build docs/matriz-data.json from data/matriz_analisis_textos.xlsx.

Handles the multi-section structure of the qualitative reading matrix where
sub-headers appear repeatedly with slightly varying column orders and labels.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import openpyxl


CANONICAL_COLUMNS = [
    {"key": "seccion", "label": "Sección / Capítulo"},
    {"key": "apa", "label": "Cita en norma APA"},
    {"key": "tema", "label": "Tema principal"},
    {"key": "conceptos", "label": "Conceptos clave (y su uso)"},
    {"key": "categorias", "label": "Categorías analíticas"},
    {"key": "metodologia", "label": "Metodología"},
    {"key": "problema", "label": "Construcción del problema"},
    {"key": "epistemologia", "label": "Ubicación epistemológica"},
    {"key": "contexto", "label": "Contexto de estudio"},
    {"key": "muestra", "label": "Muestra y alcance empírico"},
    {"key": "aportes_dir", "label": "Potenciales aportes a dirección escolar"},
    {"key": "implicaciones", "label": "Implicaciones prácticas y políticas"},
    {"key": "hallazgos", "label": "Principales hallazgos y conclusiones"},
    {"key": "citas", "label": "Citas literales clave"},
    {"key": "discusion", "label": "Discusión (diálogo/crítica)"},
    {"key": "limitaciones", "label": "Limitaciones reconocidas"},
    {"key": "futura", "label": "Propuestas de investigación futura"},
    {"key": "palabras_clave", "label": "Palabras clave"},
    {"key": "aportes_estudio", "label": "Aportes al estudio de la dirección escolar"},
]


def normalize_header(raw: str) -> str | None:
    """Map a raw Excel header label to a canonical column key."""
    s = re.sub(r"^\d+\.\s*", "", raw.strip()).lower()
    if not s or s.isdigit():
        return None
    if s.startswith(("capítulo", "sección", "texto", "clase")):
        return "seccion"
    if "cita en norma apa" in s:
        return "apa"
    if s == "tema principal":
        return "tema"
    if s.startswith("conceptos clave"):
        return "conceptos"
    if s.startswith("categorías analíticas") or s.startswith("categorias analiticas"):
        return "categorias"
    if s.startswith("metodología") or s.startswith("metodologia"):
        return "metodologia"
    if "construcción del problema" in s or "construccion del problema" in s:
        return "problema"
    if "epistemológica" in s or "epistemologica" in s:
        return "epistemologia"
    if s == "contexto de estudio":
        return "contexto"
    if s.startswith("muestra y alcance"):
        return "muestra"
    if s == "aportes al estudio de la dirección escolar":
        return "aportes_estudio"
    if "aportes" in s:
        return "aportes_dir"
    if s.startswith("implicaciones"):
        return "implicaciones"
    if "hallazgos" in s:
        return "hallazgos"
    if s.startswith("citas literales"):
        return "citas"
    if s.startswith("discusión") or s.startswith("discusion"):
        return "discusion"
    if s.startswith("limitaciones"):
        return "limitaciones"
    if "investigación futura" in s or "investigacion futura" in s:
        return "futura"
    if s.startswith("palabras clave"):
        return "palabras_clave"
    return None


def parse_matriz_xlsx(xlsx_path: Path) -> tuple[list[dict[str, str]], list[str]]:
    """Parse all rows from the matrix workbook using dynamic section headers."""
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)
    ws = wb[wb.sheetnames[0]]

    col_map: dict[int, str] = {}
    unmapped: set[str] = set()
    rows: list[dict[str, str]] = []

    for r in range(1, ws.max_row + 1):
        vals = [str(ws.cell(r, c).value or "").strip() for c in range(1, ws.max_column + 1)]
        if any("Cita en norma APA" in v for v in vals):
            col_map = {}
            for idx, v in enumerate(vals):
                if not v:
                    continue
                key = normalize_header(v)
                if key:
                    col_map[idx] = key
                elif not v.isdigit():
                    unmapped.add(v)
            continue

        if not col_map:
            continue

        # Skip pure section title banners or empty rows
        record: dict[str, str] = {col["key"]: "" for col in CANONICAL_COLUMNS}
        for idx, key in col_map.items():
            if idx < len(vals) and vals[idx]:
                if record[key]:
                    record[key] += "\n" + vals[idx]
                else:
                    record[key] = vals[idx]

        # If col 1 (0-indexed) has a section/number not mapped, use it only if seccion is empty and it's not just a bare row index
        if not record["seccion"] and len(vals) > 1 and vals[1] and not vals[1].isdigit():
            # Only if APA is also present so we don't grab banner rows
            if record["apa"]:
                record["seccion"] = vals[1]

        # Require at least APA or two analytical fields to be a valid entry
        non_empty = sum(1 for v in record.values() if v)
        if not record["apa"] and non_empty < 2:
            continue
        if not record["apa"] and not record["tema"] and not record["conceptos"]:
            continue

        record["_row"] = str(r)
        rows.append(record)

    return rows, sorted(unmapped)


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    xlsx_path = root / "data" / "matriz_analisis_textos.xlsx"
    out_path = root / "docs" / "matriz-data.json"

    if not xlsx_path.exists():
        print(f"Missing {xlsx_path}")
        return 1

    rows, unmapped = parse_matriz_xlsx(xlsx_path)
    payload = {
        "title": "Matriz de Análisis de Textos",
        "total": len(rows),
        "columns": CANONICAL_COLUMNS,
        "rows": rows,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {len(rows)} rows to {out_path} ({out_path.stat().st_size} bytes)")
    if unmapped:
        print("Unmapped headers:", unmapped)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
