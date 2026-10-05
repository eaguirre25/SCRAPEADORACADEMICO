#!/usr/bin/env python3
"""Calcula precisión y exhaustividad del filtro con la muestra validada a mano.

Lee data/validacion/muestra_pertinencia.xlsx (columna «pertinente»), pondera
cada estrato por su tamaño en la población y estima:

- precisión: proporción de pertinentes entre los registros que el filtro incluye;
- exhaustividad (recall): proporción de los pertinentes reunidos que el filtro incluye.

Los «dudoso» se informan aparte y no entran en el cálculo. También compara las
marcas con la decisión del filtro vigente, para medir el efecto de un cambio de reglas.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import openpyxl  # noqa: E402

SHEET = ROOT / "data" / "validacion" / "muestra_pertinencia.xlsx"
OUT = ROOT / "data" / "validacion" / "resultado_validacion.json"


def rows(ws):
    values = list(ws.values)
    header = [str(h) for h in values[0]]
    return [dict(zip(header, v)) for v in values[1:]]


def current_filter_agreement(wb) -> dict:
    """Matriz de confusión del filtro vigente sobre la muestra (sin ponderar).

    Reclasifica cada registro con el texto guardado en la planilla (resumen
    recortado a 1500 caracteres), para medir un cambio de reglas sin resortear.
    """
    try:
        import relevance_filter as rf
    except Exception:
        return {}
    out: dict = {}
    for r in rows(wb["Muestra"]):
        label = str(r.get("pertinente") or "").strip().lower()
        if label not in ("si", "no"):
            continue
        row = {"title": r.get("titulo") or "", "abstract": r.get("resumen") or "",
               "keywords": r.get("palabras_clave") or "", "document_type": r.get("tipo") or "",
               "source": r.get("fuente") or ""}
        status = rf.classify_relevance(row)[0]
        if status == "revisar":
            status = {"promover": "alta", "descartar": "rechazada"}.get(rf.second_review(row)[0], "revisar")
        source = "CONICET" if "conicet" in str(r.get("fuente")).lower() else "OpenAlex"
        m = out.setdefault(source, {"vp": 0, "fp": 0, "fn": 0, "vn": 0})
        m[("v" if label == "si" else "f") + "p" if status == "alta" else ("f" if label == "si" else "v") + "n"] += 1
    for m in out.values():
        m["precision"] = round(m["vp"] / (m["vp"] + m["fp"]), 3) if m["vp"] + m["fp"] else None
        m["exhaustividad"] = round(m["vp"] / (m["vp"] + m["fn"]), 3) if m["vp"] + m["fn"] else None
    return out


def evaluate(path: Path = SHEET) -> dict:
    wb = openpyxl.load_workbook(path)
    labels = {str(r["record_id"]): str(r.get("pertinente") or "").strip().lower() for r in rows(wb["Muestra"])}
    strata = {str(r["record_id"]): (r["fuente"], r["decision_filtro"]) for r in rows(wb["Estratos"])}
    population = {(r["fuente"], r["decision_filtro"]): int(r["registros"]) for r in rows(wb["Poblacion"])}

    by_stratum: dict = {}
    for rid, key in strata.items():
        label = labels.get(rid, "")
        s = by_stratum.setdefault(key, {"si": 0, "no": 0, "dudoso": 0, "sin_marcar": 0})
        s[label if label in ("si", "no", "dudoso") else "sin_marcar"] += 1

    def rate(key):
        s = by_stratum.get(key, {})
        judged = s.get("si", 0) + s.get("no", 0)
        return (s.get("si", 0) / judged) if judged else None

    def weighted(decision, source=None):
        keys = [k for k in population if k[1] == decision and (source is None or k[0] == source)]
        pertinent = sum(population[k] * (rate(k) or 0) for k in keys if rate(k) is not None)
        total = sum(population[k] for k in keys if rate(k) is not None)
        return pertinent, total

    result = {"estratos": {f"{k[0]} / {k[1]}": {**v, "poblacion": population.get(k, 0),
                                                "proporcion_pertinente": rate(k)} for k, v in by_stratum.items()}}
    for source in (None, "OpenAlex", "CONICET"):
        inc_p, inc_n = weighted("incluido", source)
        exc_p, _ = weighted("no incluido", source)
        name = source or "total"
        result[name] = {
            "precision": round(inc_p / inc_n, 3) if inc_n else None,
            "exhaustividad": round(inc_p / (inc_p + exc_p), 3) if (inc_p + exc_p) else None,
            "pertinentes_estimados_incluidos": round(inc_p),
            "pertinentes_estimados_perdidos": round(exc_p),
        }
    result["filtro_vigente_en_la_muestra"] = current_filter_agreement(wb)
    marked = sum(1 for v in labels.values() if v in ("si", "no", "dudoso"))
    result["marcados"] = f"{marked} de {len(labels)}"
    return result


def main() -> None:
    result = evaluate()
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
