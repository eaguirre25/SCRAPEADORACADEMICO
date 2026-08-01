# Informe reproducible de modelado temático

Generado: 2026-08-01T00:49:04.705877+00:00

Semilla: 42

Período: 2020–2026 (2026 incompleto)

## Resumen técnico

**BERTopic metadata multilingüe es el único modelo principal vigente: 14 macrotemas, solución preferida provisional y validación humana pendiente.** Las STM corregidas se presentan sólo como modelos comparativos y los históricos quedan separados.

## Modelo principal vigente

| run_id | model_name | corpus_unit | language | status | validation_status |
|---|---|---|---|---|---|
| 3f4de8ee8c0c96b1 | BERTopic-METADATA-MULTILINGUAL | metadata | multilingual | preferred_provisional | pending_human_review |

## Modelos comparativos

| run_id | model_name | language | status | validation_status |
|---|---|---|---|---|
| 5adc9f83bb44b510 | STM-METADATA-EN | en | stability_nonconverged | stability_nonconverged |
| 22ecf8acc6e3bd31 | STM-METADATA-ES | es | stability_nonconverged | stability_nonconverged |
| 98600702f07dbabe | STM-METADATA-PT | pt | exploratory_small_corpus_stability_nonconverged | exploratory_small_corpus_stability_nonconverged |

## Ejecuciones históricas

| run_id | model_name | model_path | generated_at | status |
|---|---|---|---|---|
| a5b3020aebf80c00 | BERTopic-METADATA-MULTILINGUAL | bertopic/metadata_multilingual/archive/pre_unicode_fix | 2026-07-30T22:16:01.981579+00:00 | historical_provisional |
| a6ee71770c19524a | BERTopic-METADATA-MULTILINGUAL | bertopic/metadata_multilingual/archive/pre_unicode_fix/root_duplicates | 2026-07-30T22:16:01.981579+00:00 | historical_provisional |
| 47bbd742d47a7c4e | stm | stm | 2026-07-30 20:33:35 | historical_provisional |
| b8d796a336cf0da4 | STM-METADATA-EN | stm/metadata_en | 2026-07-30 21:47:01 | provisional_fixed_k |
| 4a698655b149236d | STM-METADATA-ES | stm/metadata_es | 2026-07-30 21:44:36 | provisional_fixed_k |
| cfeff175c27b79a7 | STM-METADATA-PT | stm/metadata_pt | 2026-07-30 21:47:21 | provisional_fixed_k |

## Calidad y cobertura del corpus

| metric_group | metric | value |
|---|---|---|
| unique_publication_metrics | unique_publications_observed | 3460 |
| metadata_metrics | metadata_eligible_publications | 2182 |
| fulltext_metrics | fulltext_candidates | 1246 |
| fulltext_metrics | fulltext_eligible | 672 |
| intersection_metrics | metadata_fulltext_intersection | 672 |
| representation_metrics | modeling_representations | 2854 |
| exclusion_metrics | excluded_representations | 1852 |
| duplicate_metrics | exact_duplicate_rows | 2 |
| duplicate_metrics | probable_duplicate_pairs | 7 |
| distribution | year_distribution_unique_publications | {"2016": 9, "2017": 18, "2018": 57, "2019": 58, "2020": 403, "2021": 422, "2022": 449, "2023": 499, "2024": 528, "2025": 501, "2026": 218, "missing": 298} |
| distribution | year_distribution_metadata | {"2020": 313, "2021": 321, "2022": 292, "2023": 341, "2024": 379, "2025": 389, "2026": 147} |
| distribution | year_distribution_fulltext | {"2020": 77, "2021": 85, "2022": 109, "2023": 141, "2024": 121, "2025": 111, "2026": 28} |
| distribution | language_distribution_metadata | {"en": 939, "es": 1195, "id": 4, "pt": 42, "und": 2} |
| distribution | language_distribution_fulltext | {"en": 223, "es": 406, "id": 15, "pt": 24, "und": 4} |

## Métricas de modelos vigentes

| run_id | model | corpus | metric | value | applicability |
|---|---|---|---|---|---|
| 3f4de8ee8c0c96b1 | BERTopic-METADATA-MULTILINGUAL | metadata | documents | 2182 | all |
| 3f4de8ee8c0c96b1 | BERTopic-METADATA-MULTILINGUAL | metadata | topics_excluding_outliers | 14 | all |
| 3f4de8ee8c0c96b1 | BERTopic-METADATA-MULTILINGUAL | metadata | minimum_topic_size | 38 | dominant assignment or cluster |
| 3f4de8ee8c0c96b1 | BERTopic-METADATA-MULTILINGUAL | metadata | model_topic_diversity_top10 | 0.914286 | lexical representation |
| 3f4de8ee8c0c96b1 | BERTopic-METADATA-MULTILINGUAL | metadata | outlier_percentage | 38.5885 | BERTopic |
| 5adc9f83bb44b510 | STM-METADATA-EN | metadata | documents | 939 | all |
| 5adc9f83bb44b510 | STM-METADATA-EN | metadata | topics_excluding_outliers | 16 | all |
| 5adc9f83bb44b510 | STM-METADATA-EN | metadata | minimum_topic_size | 29 | dominant assignment or cluster |
| 22ecf8acc6e3bd31 | STM-METADATA-ES | metadata | documents | 1195 | all |
| 22ecf8acc6e3bd31 | STM-METADATA-ES | metadata | topics_excluding_outliers | 16 | all |
| 22ecf8acc6e3bd31 | STM-METADATA-ES | metadata | minimum_topic_size | 32 | dominant assignment or cluster |
| 98600702f07dbabe | STM-METADATA-PT | metadata | documents | 42 | all |
| 98600702f07dbabe | STM-METADATA-PT | metadata | topics_excluding_outliers | 5 | all |
| 98600702f07dbabe | STM-METADATA-PT | metadata | minimum_topic_size | 6 | dominant assignment or cluster |

## Prioridad de revisión

| priority_rank | topic_id | review_priority_score | priority_reason |
|---|---|---|---|
| 1 | 1 | 21.674 | siluetas negativas | país sin cobertura suficiente | heterogeneous_candidate |
| 2 | 2 | 20.757 | alta proporción fronteriza | candidatos de contaminación | país sin cobertura suficiente | borderline_heavy_candidate |
| 3 | 5 | 20.456 | alta proporción fronteriza | país sin cobertura suficiente | borderline_heavy_candidate |
| 4 | 10 | 19.034 | país sin cobertura suficiente | broad_but_interpretable |
| 5 | 0 | 15.413 | país sin cobertura suficiente |
| 6 | 3 | 13.755 | siluetas negativas | país sin cobertura suficiente | language_concentrated_candidate |
| 7 | 12 | 12.436 | país sin cobertura suficiente | language_concentrated_candidate |
| 8 | 9 | 11.842 | candidatos de contaminación | país sin cobertura suficiente |
| 9 | 7 | 11.264 | país sin cobertura suficiente | language_concentrated_candidate |
| 10 | 13 | 10.01 | candidatos de contaminación | país sin cobertura suficiente | language_concentrated_candidate |
| 11 | 4 | 9.169 | país sin cobertura suficiente | language_concentrated_candidate |
| 12 | 6 | 8.505 | candidatos de contaminación | país sin cobertura suficiente |
| 13 | 8 | 7.598 | país sin cobertura suficiente |
| 14 | 11 | 6.324 | candidatos de contaminación | país sin cobertura suficiente | language_concentrated_candidate |

## Comparación STM–BERTopic

| metric | value |
|---|---|
| shared_documents | 2176 |
| stm_language_models_compared | 3 |
| bertopic_documents | 2182 |
| bertopic_outliers | 842 |
| one_to_one_alignments | 8 |
| comparison_status | exploratory_pending_human_review |

## Alcance, limitaciones y próximos pasos

STM estima masa temática promedio y mezclas por publicación; BERTopic produce agrupamientos documentales semánticos. Los resultados no son equivalentes y sus medidas no son intercambiables. Los corpus metadata y full text son representaciones separadas de publicaciones relacionadas, no documentos sumables. El país estructurado no está disponible; `source` significa proveedor/repositorio bibliográfico. Los outliers se conservan, 2026 es parcial y las decisiones de relevancia, fusión, división y etiquetado esperan revisión humana. Consulte `metric_definitions.md` y `evaluation_audit.json` para auditar fórmulas y cobertura.
