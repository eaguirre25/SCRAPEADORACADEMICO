# Definiciones de métricas de evaluación

Todas las métricas describen la solución provisional; ninguna valida sustantivamente un tópico.

| Métrica | Nivel | Definición y fórmula | Rango e interpretación | Faltantes, aplicabilidad y limitaciones | Código responsable |
|---|---|---|---|---|---|
| `coherence_cv` | tópico | Coherencia c_v de las 15 palabras c-TF-IDF, usando tokens Unicode y n-gramas literales del mismo `CountVectorizer`. | Habitualmente 0–1; mayor indica mayor coaparición contextual. | NA si hay menos de dos términos compatibles, corpus vacío, desajuste o error. No prueba validez sustantiva. | `compute_topic_coherence` |
| `coherence_npmi` | tópico | NPMI medio de coaparición de los términos del tópico. | -1 a 1; mayor es mejor. | Mismo tratamiento de NA que c_v; sensible a términos raros. | `compute_topic_coherence` |
| `coherence_umass` | tópico | Log-probabilidad condicional basada en bolsa de palabras del corpus. | ≤0 normalmente; valores menos negativos son mejores. | Sólo comparable con igual corpus y preprocesamiento. | `compute_topic_coherence` |
| `model_topic_diversity_top10` | modelo | Términos únicos entre los top 10 de todos los tópicos / total de términos top 10. | 0–1; mayor implica menor repetición global. | Se publica únicamente a nivel modelo. | `lexical_metrics` |
| `topic_unique_term_share` | tópico | Proporción de top 10 que no aparece en los top 10 de ningún otro tópico. | 0–1; mayor implica más exclusividad léxica. | No equivale a coherencia ni pureza semántica. | `lexical_metrics` |
| `topic_shared_term_share` | tópico | 1 menos `topic_unique_term_share`. | 0–1; mayor implica más términos compartidos. | Complementaria, no métrica global. | `lexical_metrics` |
| `silhouette_mean` | tópico | Media de siluetas de documentos asignados. | -1 a 1; mayor separación relativa. | Sólo documentos agrupados con valor calculado. | `recompute_evaluation` |
| `silhouette_negative_share` | tópico | Documentos con silueta <0 / documentos con silueta. | 0–1; alto indica asignaciones más cercanas a otro cluster. | No reasigna documentos. | `recompute_evaluation` |
| `borderline_document_share` | tópico | Documentos marcados `is_ambiguous` / documentos del tópico. | 0–1; alto prioriza revisión. | Depende de umbrales configurados de margen, pertenencia y consistencia local. | `recompute_evaluation` |
| `low_confidence_document_share` | tópico | Documentos con fuerza HDBSCAN <0,35 / documentos del tópico. | 0–1. | No es probabilidad posterior. | `recompute_evaluation` |
| `country_entropy` | tópico | Entropía de categorías de país conocidas. | ≥0; mayor implica mayor diversidad. | NA si cobertura <30%, menos de 10 conocidos, menos de dos categorías o columna ausente. | `metadata_metrics` |
| `source_entropy` | tópico | Entropía del proveedor/repositorio bibliográfico conocido. | ≥0; mayor implica mayor diversidad de procedencia. | No es revista. NA con cobertura/categorías insuficientes. | `metadata_metrics` |
| `contamination_share` | tópico | Documentos candidatos por estado de relevancia o señales léxicas de alta precisión / total. | 0–1; es señal de revisión, no tasa validada. | Nunca implica relevancia automática cuando vale cero. | `contamination_metrics` |
| `stability_ari` | modelo/candidato | ARI medio entre réplicas o estabilidad STM registrada. | -1 a 1; mayor es más estable. | NA en réplicas no convergentes. | exportación de estabilidad + `recompute_evaluation` |
| `stability_nmi` | modelo/candidato | NMI medio entre réplicas BERTopic. | 0–1; mayor es más estable. | No disponible para STM en la ejecución actual. | exportación de estabilidad + `recompute_evaluation` |
