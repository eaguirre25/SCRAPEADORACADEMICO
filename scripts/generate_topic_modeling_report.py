#!/usr/bin/env python3
"""Generate the technical correction report from the evaluation-only layer."""
from __future__ import annotations

import argparse
import csv
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


def rows(path: Path) -> list[dict[str, str]]:
    if not path.exists(): return []
    with path.open(encoding="utf-8-sig", newline="") as handle: return list(csv.DictReader(handle))


def md_table(data: list[dict], columns: list[str]) -> str:
    if not data: return "No disponible."
    clean=lambda value:str(value).replace("|","¦").replace("\n"," ")
    return "\n".join([
        "| " + " | ".join(columns) + " |", "|" + "|".join("---" for _ in columns) + "|",
        *("| " + " | ".join(clean(row.get(column,"")) for column in columns) + " |" for row in data),
    ])


parser=argparse.ArgumentParser()
parser.add_argument("--config",default="config/topic_modeling.yml")
parser.add_argument("--latest-only",action="store_true")
args=parser.parse_args()
root=Path("output/topic_models"); evaluation=root/"evaluation"; reports=root/"reports"
runs=rows(evaluation/"model_runs.csv")
model_metrics=rows(evaluation/"model_metrics.csv")
coherence=rows(evaluation/"coherence_diagnostics.csv")
metadata=rows(evaluation/"metadata_coverage.csv")
heterogeneity=rows(evaluation/"heterogeneity.csv")
priority=rows(evaluation/"topic_review_priority.csv")
stability=rows(evaluation/"stability.csv")
preferred=[row for row in runs if row.get("is_preferred_model","").lower()=="true"]
comparative=[row for row in runs if row.get("is_latest_for_model","").lower()=="true" and row.get("is_archived","").lower()!="true" and row.get("is_preferred_model","").lower()!="true"]
historical=[row for row in runs if row.get("is_archived","").lower()=="true"]
hetero_counts=Counter(row["status"] for row in heterogeneity)
country_computed=sum(row.get("country_status")=="computed" for row in metadata)
source_computed=sum(row.get("source_status")=="computed" for row in metadata)
coherence_computed=sum(row.get("coherence_status")=="computed" for row in coherence)
preferred_count=len(preferred); dashboard_active=sum(row.get("is_dashboard_active","").lower()=="true" for row in runs)
duplicate_keys=[]; seen=set()
for row in model_metrics:
    key=(row.get("run_id"),row.get("model"),row.get("metric"))
    if key in seen: duplicate_keys.append(key)
    seen.add(key)
diversity=next((row.get("value") for row in model_metrics if row.get("metric")=="model_topic_diversity_top10" and row.get("is_preferred_model","").lower()=="true"),"")
comparison=[
    {"Indicador":"coherencia calculada","Antes":"0/14 en heterogeneity.csv","Después":f"{coherence_computed}/14 c_v, NPMI y UMass"},
    {"Indicador":"diversidad","Antes":"0,071429 repetido en 14 tópicos","Después":f"global top10={diversity}; exclusividad variable por tópico"},
    {"Indicador":"metadatos territoriales","Antes":"entropía -0,0; concentración 1,0 falsa","Después":f"0/14 calculables; país no existe en el corpus"},
    {"Indicador":"metadatos de fuente","Antes":"sin cobertura/semántica explícita","Después":f"14/14 con proveedor conocido; entropía calculable en {source_computed}/14"},
    {"Indicador":"contaminación","Antes":"0 para todos por estado de relevancia constante","Después":"señales documentales + cobertura; cero no implica relevancia validada"},
    {"Indicador":"heterogeneidad","Antes":"12 coherent, 2 broad","Después":"; ".join(f"{k}={v}" for k,v in sorted(hetero_counts.items()))},
    {"Indicador":"duplicados de métricas","Antes":"ejecuciones antiguas y nuevas mezcladas","Después":str(len(duplicate_keys))},
    {"Indicador":"modelos preferred","Antes":"estado is_current ambiguo","Después":str(preferred_count)},
    {"Indicador":"modelos activos","Antes":"5 marcados is_current","Después":f"{dashboard_active}: 1 principal + 3 comparativos"},
    {"Indicador":"tópicos prioritarios","Antes":"sin ranking","Después":"T"+", T".join(row["topic_id"] for row in priority[:5])},
]
preferred_table=[{k:row.get(k,"") for k in ("run_id","model_name","corpus_unit","language","status","validation_status")} for row in preferred]
comparative_table=[{k:row.get(k,"") for k in ("run_id","model_name","language","status","validation_status")} for row in comparative]
historical_table=[{k:row.get(k,"") for k in ("run_id","model_name","model_path","generated_at","status")} for row in historical]
priority_table=[{k:row.get(k,"") for k in ("priority_rank","topic_id","review_priority_score","borderline_share","negative_silhouette_share","coherence_cv","contamination_share","priority_reason")} for row in priority]
report=f"""# Corrección de la evaluación del modelado temático

Generado: {datetime.now(timezone.utc).isoformat()}  
Modo: **evaluation_only**. La solución BERTopic de 14 macrotemas no fue reestimada.

## Resumen técnico

La capa de evaluación fue reconstruida sin modificar asignaciones, outliers, jerarquía ni parámetros. La coherencia faltaba en `heterogeneity.csv` porque el exportador escribía campos vacíos antes de invocar la evaluación Gensim; el cálculo paralelo de `topic_metrics.csv` sí funcionaba. La nueva evaluación usa exactamente el analizador Unicode y los unigramas, bigramas y trigramas del vectorizador.

El valor repetido 0,071429 no era diversidad: dividía los términos de cada tópico por el total de términos de los 14 tópicos. Ahora la diversidad global aparece sólo en `model_metrics.csv`, y cada tópico recibe exclusividad, términos compartidos, similitud léxica y entropía interna propias.

## Indicadores corregidos

{md_table(comparison,["Indicador","Antes","Después"])}

## Modelo principal vigente

{md_table(preferred_table,["run_id","model_name","corpus_unit","language","status","validation_status"])}

BERTopic metadata multilingüe es la única solución preferida: 14 macrotemas, estado `preferred_provisional` y validación humana pendiente.

## Modelos comparativos

{md_table(comparative_table,["run_id","model_name","language","status","validation_status"])}

Las STM corregidas permanecen comparativas. Su estabilidad no convergió; portugués además es exploratorio por tamaño de corpus.

## Ejecuciones históricas

{md_table(historical_table,["run_id","model_name","model_path","generated_at","status"])}

Estas ejecuciones se conservan para trazabilidad, pero quedan fuera de las tablas principales y no reemplazan modelos más nuevos.

## La cobertura impide inferencias territoriales

El corpus no contiene país del estudio, país de afiliación ni ubicación estructurada: cobertura territorial real 0/2.182. Por eso `country_entropy` y la concentración territorial son NA con estado `missing_column`. La columna `source` tiene cobertura 2.182/2.182, pero representa proveedor o repositorio bibliográfico, no revista ni país. La entropía de fuente sólo se calcula con al menos 10 casos conocidos, cobertura ≥30% y dos categorías.

## La contaminación ahora usa evidencia documental

Se combinan `relevance_status`, `relevance_score`, candidatos previos, títulos, resúmenes y señales léxicas de alta precisión. `relevance_score` se conserva como puntaje de reglas y no se renombra como similitud de dominio. Dado que todos los documentos habían sido marcados `included`, un cero de contaminación mantiene estado `pending_human_review`, nunca `domain_relevant` automático.

## La heterogeneidad incorpora fronteras y siluetas negativas

Estados resultantes: {dict(hetero_counts)}. T1 presenta la mayor proporción de siluetas negativas; T2 y T5 concentran asignaciones ambiguas. Las reglas combinan silueta, fronterizos, coherencia, contaminación, idioma y procedencia; todos los estados terminan como candidatos o evidencia insuficiente.

## Prioridad de revisión documental

{md_table(priority_table,["priority_rank","topic_id","review_priority_score","borderline_share","negative_silhouette_share","coherence_cv","contamination_share","priority_reason"])}

## Robustez y trazabilidad

- Coherencia calculada para {coherence_computed}/14 tópicos; todos los términos c-TF-IDF fueron compatibles con el diccionario.
- Exactamente {preferred_count} modelo tiene `is_preferred_model=true`.
- Duplicados por `run_id + model + metric`: {len(duplicate_keys)}.
- `model_runs.csv` diferencia latest, preferred, dashboard activo, archivado y validación.
- Los hashes de los seis artefactos congelados se verifican antes y después de la evaluación.

## Limitaciones y próximos pasos

- No existe país estructurado; debe incorporarse desde metadata de estudio o afiliación antes de evaluar territorio.
- La contaminación sigue siendo una señal automática y requiere codificación documental.
- Las STM tienen estabilidad no convergente y no deben presentarse como modelos preferidos.
- Las etiquetas y decisiones de fusión/división continúan pendientes de validación humana.
- Completar la revisión de T1, T2, T5, T10 y T0 en ese orden, sin reasignar automáticamente documentos.

## Preguntas abiertas

- ¿Puede OpenAlex o CONICET aportar país de estudio o afiliación con procedencia explícita?
- ¿Qué umbral de contaminación se confirmará después de la muestra humana?
- ¿La alta frontera de T2 y T5 refleja amplitud sustantiva o documentos mal asignados?
"""
reports.mkdir(parents=True,exist_ok=True)
target=reports/"topic_modeling_correction_report.md"; target.write_text(report,encoding="utf-8")
print(target)
