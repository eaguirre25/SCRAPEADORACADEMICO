# Informe reproducible de modelado temático

Generado: 2026-07-30T22:28:21.999610+00:00

Semilla: 42

Período: 2020–2026 (2026 incompleto)

**Estado general: exploratorio; falta validación humana y ninguna etiqueta automática debe interpretarse como categoría objetiva.**

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

## Métricas de modelos

| model | corpus | metric | value | applicability |
|---|---|---|---|---|
| stm | full_text | documents | 863 | all |
| stm | full_text | topics_excluding_outliers | 22 | all |
| stm | full_text | minimum_topic_size | 2 | dominant STM assignment or BERTopic cluster |
| stm | full_text | topic_word_diversity | 1.0 | lexical representation |
| stm | full_text | outlier_percentage | 0.0 | BERTopic only; STM returns 0 |
| stm | full_text | ambiguous_documents | 133 | model-specific confidence |
| stm | full_text | coherence_computation_status | not_computed_empty_corpus | lexical representation |
| stm | full_text | mean_pairwise_topic_similarity | 0.0 | lexical overlap |
| stm | full_text | maximum_pairwise_topic_similarity | 0.0 | lexical overlap |
| stm | full_text | redundant_topic_pairs_0_5 | 0 | lexical overlap |
| stm | full_text | temporal_accounting_issues | 2020:dominant=0:documents=97 | 2020:mass=0.0:documents=97 | 2021:dominant=0:documents=110 | 2021:mass=0.0:documents=110 | 2022:dominant=0:documents=148 | 2022:mass=0.0:documents=148 | 2023:dominant=0:documents=174 | 2023:mass=0.0:documents=174 | 2024:dominant=0:documents=161 | 2024:mass=0.0:documents=161 | 2025:dominant=0:documents=144 | 2025:mass=0.0:documents=144 | 2026:dominant=0:documents=29 | 2026:mass=0.0:documents=29 | empty means annual counts and topic mass reconcile |
| STM-METADATA-EN | metadata | documents | 939 | all |
| STM-METADATA-EN | metadata | topics_excluding_outliers | 16 | all |
| STM-METADATA-EN | metadata | minimum_topic_size | 11 | dominant STM assignment or BERTopic cluster |
| STM-METADATA-EN | metadata | topic_word_diversity | 0.995833 | lexical representation |
| STM-METADATA-EN | metadata | outlier_percentage | 0.0 | BERTopic only; STM returns 0 |
| STM-METADATA-EN | metadata | ambiguous_documents | 173 | model-specific confidence |
| STM-METADATA-EN | metadata | coherence_computation_status | computed_gensim | lexical representation |
| STM-METADATA-EN | metadata | mean_pairwise_topic_similarity | 0.000287 | lexical overlap |
| STM-METADATA-EN | metadata | maximum_pairwise_topic_similarity | 0.034483 | lexical overlap |
| STM-METADATA-EN | metadata | redundant_topic_pairs_0_5 | 0 | lexical overlap |
| STM-METADATA-EN | metadata | temporal_accounting_issues |  | empty means annual counts and topic mass reconcile |
| STM-METADATA-ES | metadata | documents | 1195 | all |
| STM-METADATA-ES | metadata | topics_excluding_outliers | 16 | all |
| STM-METADATA-ES | metadata | minimum_topic_size | 29 | dominant STM assignment or BERTopic cluster |
| STM-METADATA-ES | metadata | topic_word_diversity | 0.991667 | lexical representation |
| STM-METADATA-ES | metadata | outlier_percentage | 0.0 | BERTopic only; STM returns 0 |
| STM-METADATA-ES | metadata | ambiguous_documents | 230 | model-specific confidence |
| STM-METADATA-ES | metadata | coherence_computation_status | computed_gensim | lexical representation |
| STM-METADATA-ES | metadata | mean_pairwise_topic_similarity | 0.000595 | lexical overlap |
| STM-METADATA-ES | metadata | maximum_pairwise_topic_similarity | 0.071429 | lexical overlap |
| STM-METADATA-ES | metadata | redundant_topic_pairs_0_5 | 0 | lexical overlap |
| STM-METADATA-ES | metadata | temporal_accounting_issues |  | empty means annual counts and topic mass reconcile |
| STM-METADATA-PT | metadata | documents | 42 | all |
| STM-METADATA-PT | metadata | topics_excluding_outliers | 8 | all |
| STM-METADATA-PT | metadata | minimum_topic_size | 3 | dominant STM assignment or BERTopic cluster |
| STM-METADATA-PT | metadata | topic_word_diversity | 0.866667 | lexical representation |
| STM-METADATA-PT | metadata | outlier_percentage | 0.0 | BERTopic only; STM returns 0 |
| STM-METADATA-PT | metadata | ambiguous_documents | 5 | model-specific confidence |
| STM-METADATA-PT | metadata | coherence_computation_status | computed_gensim | lexical representation |
| STM-METADATA-PT | metadata | mean_pairwise_topic_similarity | 0.020908 | lexical overlap |
| STM-METADATA-PT | metadata | maximum_pairwise_topic_similarity | 0.153846 | lexical overlap |
| STM-METADATA-PT | metadata | redundant_topic_pairs_0_5 | 0 | lexical overlap |
| STM-METADATA-PT | metadata | temporal_accounting_issues |  | empty means annual counts and topic mass reconcile |
| BERTopic-METADATA-MULTILINGUAL | metadata | documents | 2182 | all |
| BERTopic-METADATA-MULTILINGUAL | metadata | topics_excluding_outliers | 42 | all |
| BERTopic-METADATA-MULTILINGUAL | metadata | minimum_topic_size | 10 | dominant STM assignment or BERTopic cluster |
| BERTopic-METADATA-MULTILINGUAL | metadata | topic_word_diversity | 0.95 | lexical representation |
| BERTopic-METADATA-MULTILINGUAL | metadata | outlier_percentage | 53.2997 | BERTopic only; STM returns 0 |
| BERTopic-METADATA-MULTILINGUAL | metadata | ambiguous_documents | 1200 | model-specific confidence |
| BERTopic-METADATA-MULTILINGUAL | metadata | coherence_computation_status | computed_gensim | lexical representation |
| BERTopic-METADATA-MULTILINGUAL | metadata | mean_pairwise_topic_similarity | 0.001483 | lexical overlap |
| BERTopic-METADATA-MULTILINGUAL | metadata | maximum_pairwise_topic_similarity | 0.176471 | lexical overlap |
| BERTopic-METADATA-MULTILINGUAL | metadata | redundant_topic_pairs_0_5 | 0 | lexical overlap |
| BERTopic-METADATA-MULTILINGUAL | metadata | temporal_accounting_issues |  | empty means annual counts and topic mass reconcile |

## Comparación STM–BERTopic

| metric | value |
|---|---|
| shared_documents | 2176 |
| stm_language_models_compared | 3 |
| bertopic_documents | 2182 |
| bertopic_outliers | 1163 |
| one_to_one_alignments | 8 |
| comparison_status | exploratory_pending_human_review |

## Interpretación y limitaciones

STM estima masa temática promedio y mezclas por publicación; BERTopic produce agrupamientos documentales semánticos. Los resultados no son equivalentes y sus medidas no son intercambiables. Los corpus metadata y full text son representaciones separadas de publicaciones relacionadas, no documentos sumables. Los outliers se conservan, 2026 es parcial y las decisiones de relevancia, fusión, división y etiquetado esperan revisión humana.
