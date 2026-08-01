# Corrección de la evaluación del modelado temático

Generado: 2026-08-01T00:49:03.754777+00:00  
Modo: **evaluation_only**. La solución BERTopic de 14 macrotemas no fue reestimada.

## Resumen técnico

La capa de evaluación fue reconstruida sin modificar asignaciones, outliers, jerarquía ni parámetros. La coherencia faltaba en `heterogeneity.csv` porque el exportador escribía campos vacíos antes de invocar la evaluación Gensim; el cálculo paralelo de `topic_metrics.csv` sí funcionaba. La nueva evaluación usa exactamente el analizador Unicode y los unigramas, bigramas y trigramas del vectorizador.

El valor repetido 0,071429 no era diversidad: dividía los términos de cada tópico por el total de términos de los 14 tópicos. Ahora la diversidad global aparece sólo en `model_metrics.csv`, y cada tópico recibe exclusividad, términos compartidos, similitud léxica y entropía interna propias.

## Indicadores corregidos

| Indicador | Antes | Después |
|---|---|---|
| coherencia calculada | 0/14 en heterogeneity.csv | 14/14 c_v, NPMI y UMass |
| diversidad | 0,071429 repetido en 14 tópicos | global top10=0.914286; exclusividad variable por tópico |
| metadatos territoriales | entropía -0,0; concentración 1,0 falsa | 0/14 calculables; país no existe en el corpus |
| metadatos de fuente | sin cobertura/semántica explícita | 14/14 con proveedor conocido; entropía calculable en 6/14 |
| contaminación | 0 para todos por estado de relevancia constante | señales documentales + cobertura; cero no implica relevancia validada |
| heterogeneidad | 12 coherent, 2 broad | borderline_heavy_candidate=2; broad_but_interpretable=1; coherent_candidate=4; heterogeneous_candidate=1; language_concentrated_candidate=6 |
| duplicados de métricas | ejecuciones antiguas y nuevas mezcladas | 0 |
| modelos preferred | estado is_current ambiguo | 1 |
| modelos activos | 5 marcados is_current | 4: 1 principal + 3 comparativos |
| tópicos prioritarios | sin ranking | T1, T2, T5, T10, T0 |

## Modelo principal vigente

| run_id | model_name | corpus_unit | language | status | validation_status |
|---|---|---|---|---|---|
| 3f4de8ee8c0c96b1 | BERTopic-METADATA-MULTILINGUAL | metadata | multilingual | preferred_provisional | pending_human_review |

BERTopic metadata multilingüe es la única solución preferida: 14 macrotemas, estado `preferred_provisional` y validación humana pendiente.

## Modelos comparativos

| run_id | model_name | language | status | validation_status |
|---|---|---|---|---|
| 5adc9f83bb44b510 | STM-METADATA-EN | en | stability_nonconverged | stability_nonconverged |
| 22ecf8acc6e3bd31 | STM-METADATA-ES | es | stability_nonconverged | stability_nonconverged |
| 98600702f07dbabe | STM-METADATA-PT | pt | exploratory_small_corpus_stability_nonconverged | exploratory_small_corpus_stability_nonconverged |

Las STM corregidas permanecen comparativas. Su estabilidad no convergió; portugués además es exploratorio por tamaño de corpus.

## Ejecuciones históricas

| run_id | model_name | model_path | generated_at | status |
|---|---|---|---|---|
| a5b3020aebf80c00 | BERTopic-METADATA-MULTILINGUAL | bertopic/metadata_multilingual/archive/pre_unicode_fix | 2026-07-30T22:16:01.981579+00:00 | historical_provisional |
| a6ee71770c19524a | BERTopic-METADATA-MULTILINGUAL | bertopic/metadata_multilingual/archive/pre_unicode_fix/root_duplicates | 2026-07-30T22:16:01.981579+00:00 | historical_provisional |
| 47bbd742d47a7c4e | stm | stm | 2026-07-30 20:33:35 | historical_provisional |
| b8d796a336cf0da4 | STM-METADATA-EN | stm/metadata_en | 2026-07-30 21:47:01 | provisional_fixed_k |
| 4a698655b149236d | STM-METADATA-ES | stm/metadata_es | 2026-07-30 21:44:36 | provisional_fixed_k |
| cfeff175c27b79a7 | STM-METADATA-PT | stm/metadata_pt | 2026-07-30 21:47:21 | provisional_fixed_k |

Estas ejecuciones se conservan para trazabilidad, pero quedan fuera de las tablas principales y no reemplazan modelos más nuevos.

## La cobertura impide inferencias territoriales

El corpus no contiene país del estudio, país de afiliación ni ubicación estructurada: cobertura territorial real 0/2.182. Por eso `country_entropy` y la concentración territorial son NA con estado `missing_column`. La columna `source` tiene cobertura 2.182/2.182, pero representa proveedor o repositorio bibliográfico, no revista ni país. La entropía de fuente sólo se calcula con al menos 10 casos conocidos, cobertura ≥30% y dos categorías.

## La contaminación ahora usa evidencia documental

Se combinan `relevance_status`, `relevance_score`, candidatos previos, títulos, resúmenes y señales léxicas de alta precisión. `relevance_score` se conserva como puntaje de reglas y no se renombra como similitud de dominio. Dado que todos los documentos habían sido marcados `included`, un cero de contaminación mantiene estado `pending_human_review`, nunca `domain_relevant` automático.

## La heterogeneidad incorpora fronteras y siluetas negativas

Estados resultantes: {'coherent_candidate': 4, 'heterogeneous_candidate': 1, 'borderline_heavy_candidate': 2, 'language_concentrated_candidate': 6, 'broad_but_interpretable': 1}. T1 presenta la mayor proporción de siluetas negativas; T2 y T5 concentran asignaciones ambiguas. Las reglas combinan silueta, fronterizos, coherencia, contaminación, idioma y procedencia; todos los estados terminan como candidatos o evidencia insuficiente.

## Prioridad de revisión documental

| priority_rank | topic_id | review_priority_score | borderline_share | negative_silhouette_share | coherence_cv | contamination_share | priority_reason |
|---|---|---|---|---|---|---|---|
| 1 | 1 | 21.674 | 0.056962 | 0.297468 | 0.331413 | 0.0 | siluetas negativas ¦ país sin cobertura suficiente ¦ heterogeneous_candidate |
| 2 | 2 | 20.757 | 0.297872 | 0.0 | 0.397541 | 0.028369 | alta proporción fronteriza ¦ candidatos de contaminación ¦ país sin cobertura suficiente ¦ borderline_heavy_candidate |
| 3 | 5 | 20.456 | 0.26506 | 0.012048 | 0.401316 | 0.0 | alta proporción fronteriza ¦ país sin cobertura suficiente ¦ borderline_heavy_candidate |
| 4 | 10 | 19.034 | 0.173913 | 0.0 | 0.245564 | 0.0 | país sin cobertura suficiente ¦ broad_but_interpretable |
| 5 | 0 | 15.413 | 0.066456 | 0.03481 | 0.336411 | 0.009494 | país sin cobertura suficiente |
| 6 | 3 | 13.755 | 0.123077 | 0.130769 | 0.724057 | 0.015385 | siluetas negativas ¦ país sin cobertura suficiente ¦ language_concentrated_candidate |
| 7 | 12 | 12.436 | 0.078947 | 0.0 | 0.49547 | 0.0 | país sin cobertura suficiente ¦ language_concentrated_candidate |
| 8 | 9 | 11.842 | 0.043478 | 0.0 | 0.529372 | 0.065217 | candidatos de contaminación ¦ país sin cobertura suficiente |
| 9 | 7 | 11.264 | 0.03125 | 0.0 | 0.478218 | 0.0 | país sin cobertura suficiente ¦ language_concentrated_candidate |
| 10 | 13 | 10.01 | 0.0 | 0.0 | 0.53444 | 0.052632 | candidatos de contaminación ¦ país sin cobertura suficiente ¦ language_concentrated_candidate |
| 11 | 4 | 9.169 | 0.07 | 0.0 | 0.695395 | 0.0 | país sin cobertura suficiente ¦ language_concentrated_candidate |
| 12 | 6 | 8.505 | 0.106667 | 0.0 | 0.901877 | 0.053333 | candidatos de contaminación ¦ país sin cobertura suficiente |
| 13 | 8 | 7.598 | 0.0 | 0.0 | 0.670875 | 0.016129 | país sin cobertura suficiente |
| 14 | 11 | 6.324 | 0.023256 | 0.0 | 0.807055 | 0.023256 | candidatos de contaminación ¦ país sin cobertura suficiente ¦ language_concentrated_candidate |

## Robustez y trazabilidad

- Coherencia calculada para 14/14 tópicos; todos los términos c-TF-IDF fueron compatibles con el diccionario.
- Exactamente 1 modelo tiene `is_preferred_model=true`.
- Duplicados por `run_id + model + metric`: 0.
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
