# Modelado temático de dirección, gestión y liderazgo escolar

## Alcance y estado epistemológico

Este pipeline organiza literatura publicada entre 2020 y 2026. Sus resultados son **construcciones analíticas exploratorias**, no categorías naturales descubiertas de forma objetiva. Ningún descriptor automático, exclusión fronteriza, fusión o selección de hiperparámetros se considera validado hasta completar la revisión humana documentada. El año 2026 es incompleto.

STM y BERTopic responden preguntas diferentes. STM representa cada publicación como una mezcla de tópicos y permite estudiar prevalencia y covariables con incertidumbre. BERTopic agrupa representaciones semánticas contextuales, conserva outliers y facilita recuperación, jerarquías y documentos representativos. Por eso no se equipara la masa temática promedio de STM con el porcentaje de documentos de un cluster BERTopic.

## Unidad canónica y corpus

La unidad de conteo es la **publicación**, identificada en este orden: DOI normalizado, identificador persistente de fuente, hash de título normalizado + año + primer autor y, por último, hash estable de los campos disponibles. `publications_master.csv` tiene una fila por publicación observada. Metadata y texto completo son representaciones relacionadas mediante `publication_document_id`; nunca se suman como si fueran publicaciones distintas.

La deduplicación fusiona automáticamente sólo DOI normalizado idéntico o título+año+primer autor idénticos. Las similitudes altas de título quedan en `probable_duplicates.csv` para revisión. `corpus_relationships.csv` documenta la correspondencia PDF–metadata y conserva vínculos ambiguos.

El corpus principal es `modeling_corpus_metadata.csv`: título, resumen y palabras clave sin repetición literal. STM puede evaluar variantes ponderadas, pero la base es no ponderada. BERTopic codifica cada campo por separado y combina los vectores disponibles con pesos iniciales título 0,35, resumen 0,50 y palabras clave 0,15; también admite una variante título+resumen.

`modeling_corpus_fulltext.csv` es secundario. Intenta separar resumen, introducción, métodos, resultados, discusión, conclusiones, referencias y anexos; excluye referencias del modelado y registra longitud, secciones, truncamiento y fracción removida. Su estrategia inicial prioriza resumen+introducción+conclusiones. La disponibilidad factual de un PDF y su elegibilidad analítica son campos distintos.

## Relevancia y limpieza

El filtro previo al modelado combina: reglas de alta precisión, similitud TF–IDF con prototipos positivos/negativos y revisión humana. Produce `included`, `borderline`, `excluded` y `manual_review`. Enfermería, hospitales, tributación, contabilidad, gestión empresarial y administración universitaria activan señales de riesgo, pero una palabra aislada no decide la exclusión. Los casos dudosos se conservan en archivos de revisión y una muestra estratificada de 200 casos; precision, recall, F1, matriz de confusión y acuerdo sólo podrán calcularse cuando se complete la codificación humana.

Hay funciones diferenciadas para visualización, embeddings y STM. La limpieza detecta URLs, DOI/ISSN/ISBN, correos, licencias, navegación, líneas editoriales, referencias, controles Unicode, tokens dañados y patrones repetidos. No elimina todos los nombres propios ni aplica stemming por defecto. `cleaning_audit.csv`, `frequent_removed_patterns.csv` y `residual_artifact_candidates.csv` permiten revisar lo removido y lo residual.

## Multilingüismo

La STM principal se estima por separado para español, inglés y portugués. Indonesio permanece en BERTopic por su tamaño insuficiente para una STM comparable. Una STM armonizada está prevista pero desactivada hasta disponer de traducción reproducible, preservación del original y evaluación cruzada.

BERTopic usa por defecto `sentence-transformers/paraphrase-multilingual-mpnet-base-v2`. Para cada cluster se exportan distribución y entropía idiomáticas, idioma dominante y su proporción. Una proporción dominante superior al umbral configura una alerta; no prueba por sí sola que el tópico sea meramente lingüístico.

## STM

La búsqueda completa de K tiene una fase gruesa (8, 12, 16, 20, 24, 28, 32) y finalistas alrededor de las soluciones plausibles. Para cada finalista la segunda fase debe ejecutar al menos cinco réplicas. La selección combina coherencia, exclusividad, held-out likelihood, residuales y estabilidad. Una métrica ausente se retira y los pesos restantes se renormalizan; nunca se imputa estabilidad neutral. Se exportan solución preferida, competitivas y rechazadas con estado `provisional`, `metrics_complete`, `human_reviewed` o `validated`.

La primera ejecución puede usar `--preliminary --fixed-k N`. Eso crea deliberadamente un ajuste provisional: no afirma que N sea óptimo. Los tópicos con menos de diez asignaciones dominantes generan alerta. `estimateEffect` conserva el objeto para inferencia temporal; la tabla anual separa documentos del año, asignaciones dominantes, masa efectiva, media, mediana, presencia por umbral e intervalos.

## BERTopic

La búsqueda escalonada prueba configuraciones contenidas de UMAP y HDBSCAN y registra clusters, outliers, tamaños, concentración, silueta, dependencia idiomática y puntaje preliminar. Menos outliers no implica automáticamente mejor modelo. La solución original `-1` se conserva; cualquier reasignación es una alternativa con método y confianza separados.

Se exportan c-TF-IDF, unigramas/bigramas/trigramas, representantes, documentos centrales, fronterizos y de baja confianza, distancia al centroide, silueta y consistencia local. También se generan similitud, candidatos de fusión, jerarquía y heterogeneidad. Las fusiones quedan pendientes de juicio humano.

## Evaluación y comparación

La evaluación separa calidad léxica, diversidad, redundancia, asignación, estabilidad, idioma, contaminación, heterogeneidad y utilidad documental. Cuando `gensim` está disponible calcula c_v, c_npmi y UMass sobre el corpus correspondiente; una métrica no aplicable o fallida queda explícitamente ausente. Coherencia no equivale a validez.

La comparación principal alinea STM-METADATA por idioma con BERTopic-METADATA multilingüe usando sólo publicaciones compartidas del mismo período y filtro. Informa solapamiento documental, mezcla ponderada, palabras, representantes y alineación combinada; `centroid_similarity` queda como no calculada hasta existir centroides comparables. Las relaciones (`one_to_one`, divisiones, combinaciones, solapamientos parciales o débiles) son propuestas matemáticas para revisión sustantiva.

### Evaluación sin reestimación

La modalidad predeterminada para corregir métricas es `evaluation_only`. Lee la solución `preferred_solution`, calcula sus métricas y compara hashes SHA-256 antes y después. No carga ni ajusta BERTopic, embeddings, UMAP o HDBSCAN. Tampoco modifica asignaciones, outliers, palabras, centroides o jerarquía.

La coherencia usa `text_for_vectorizer` y el mismo `CountVectorizer` Unicode multilingüe. Unigramas, bigramas y trigramas se conservan como tokens literales: `gestión escolar` se compara con el mismo token generado por el analizador. Por tópico se exportan c_v, NPMI, UMass, términos usados/faltantes, documentos y estado. Un error o falta de cobertura produce NA más una causa; nunca cero artificial.

`model_topic_diversity_top10` es global y sólo aparece en `model_metrics.csv`. A nivel tópico se distinguen `topic_unique_term_share`, `topic_shared_term_share`, similitud léxica media/máxima, tópico más similar y entropía de pesos c-TF-IDF.

El corpus no contiene país estructurado. `country_entropy` queda NA con `country_status=missing_column`; no se convierte el vacío en una categoría. `source` significa proveedor/repositorio bibliográfico, no revista ni país. Entropías de metadata requieren al menos 10 valores conocidos, cobertura de 30% y dos categorías.

La contaminación combina estados y puntajes de relevancia, candidatos previos, título, resumen y patrones de alta precisión. `relevance_score` es un puntaje de reglas, no una similitud coseno; por eso `domain_similarity_*` permanece NA hasta existir una medida válida. Contaminación cero no autoriza el estado “relevante para el dominio”: sigue pendiente de revisión.

La heterogeneidad integra media, mediana, mínimo y proporción negativa de silueta; distancia al centroide; fronterizos; baja confianza; coherencia; exclusividad; idioma; metadata y contaminación. Las reglas configurables viven en `evaluation.heterogeneity`. Todos los resultados son candidatos provisionales.

`model_runs.csv` separa `is_latest_for_model`, `is_preferred_model`, `is_dashboard_active` e `is_archived`. Sólo BERTopic metadata multilingüe de 14 macrotemas es preferido. Las STM corregidas son comparativas; la STM de texto completo y las corridas previas quedan históricas.

La validación genera `topic_validation.csv`, word intrusion y topic intrusion. Requiere revisar documentos centrales y fronterizos, calificar pureza, distinción, relevancia y dependencia idiomática, y responder si el tópico ayuda a comprender la investigación sobre dirección, gestión o liderazgo escolar. Con dos revisores deben calcularse acuerdo porcentual y kappa o alpha según la escala.

### Capa de interpretación sustantiva provisional

La solución BERTopic seleccionada tiene 14 macrotópicos (T0–T13), 17 subtópicos y 842 outliers conservados sobre 2.182 publicaciones. `scripts/generate_topic_validation_review.py` cruza la asignación algorítmica con título, resumen, autores, año, fuente e idioma y crea una capa separada de interpretación. No reestima embeddings, UMAP o HDBSCAN; tampoco reasigna clusters u outliers.

Cada tópico tiene tres niveles de identificación que nunca deben confundirse:

1. `topic_id`: identificador algorítmico estable de la corrida.
2. `automatic_label`: descriptor producido por c-TF-IDF/KeyBERT.
3. `proposed_human_label`: interpretación sustantiva provisional, pendiente de revisión documental independiente.

Los expedientes `output/topic_models/validation/topic_dossiers/T00.md` a `T13.md` documentan definición, evidencia léxica, estructura interna, documentos centrales y fronterizos, idiomas, fuentes y relaciones. `topic_document_review.csv` conserva muestras central, fronteriza, de baja confianza y aleatoria; para los tópicos con menos de 40 casos amplía la cobertura hasta incluir todos los documentos. Las columnas `human_*` permanecen vacías deliberadamente.

`topic_merge_proposals.csv` y `topic_split_proposals.csv` son hipótesis de revisión, no operaciones ejecutadas. `word_intrusion.csv`, `topic_intrusion.csv` y `outlier_review_sample.csv` son plantillas reproducibles sin respuestas humanas precargadas. Sólo después de dos codificaciones independientes, cálculo de acuerdo y resolución de discrepancias corresponde cambiar una etiqueta a `validated` en `config/topic_labels.csv`.

Las evaluaciones registran cada corrida en `output/topic_models/evaluation/model_runs.csv` mediante `run_id`, `is_current`, `generated_at`, `commit` y `status`. Si existe `metadata_<idioma>_corrected`, la evaluación excluye la carpeta STM anterior del informe operativo para evitar duplicados.

## Ejecución

Auditoría y recomputación de métricas, sin reestimar el modelo:

```powershell
python scripts/audit_topic_evaluation.py --config config/topic_modeling.yml
python scripts/recompute_topic_metrics.py --config config/topic_modeling.yml --model preferred --recompute-model false
python scripts/rebuild_model_runs.py --config config/topic_modeling.yml
python scripts/generate_topic_modeling_report.py --config config/topic_modeling.yml --latest-only
python generate_dashboard.py
```

El atajo equivalente es:

```powershell
python scripts/run_topic_pipeline.py --mode evaluation_only --config config/topic_modeling.yml
```

Primera fase, deliberadamente preliminar:

```powershell
python scripts/build_modeling_corpus.py --config config/topic_modeling.yml
python scripts/run_topic_pipeline.py --mode stm --corpus-unit metadata --preliminary
python scripts/search_bertopic_parameters.py --corpus-unit metadata
python scripts/run_bertopic.py --corpus-unit metadata
python scripts/run_topic_pipeline.py --mode compare
python scripts/generate_topic_validation_review.py
python scripts/run_topic_pipeline.py --mode dashboard
```

Segunda fase, sólo después de revisar relevancia y etiquetas:

```powershell
python scripts/run_topic_pipeline.py --mode stm --corpus-unit metadata --run-stability
```

Las salidas viven en `output/topic_models/{corpus,stm,bertopic,evaluation,comparison,validation,reports}`. Los modelos binarios y embeddings se almacenan en caché y no necesitan API paga. Semilla predeterminada: 42.

## Limitaciones vigentes

- El filtro híbrido no está validado hasta codificar la muestra de relevancia.
- Los PDF sin vínculo inequívoco con metadata quedan fuera del modelado y dentro de la auditoría.
- La cobertura PDF varía por año, fuente e idioma; las tendencias full text pueden reflejar disponibilidad.
- El modelo de embeddings alternativo y la STM armonizada están previstos, no seleccionados.
- Ningún K, cluster, etiqueta o fusión automática se declara definitivo sin estabilidad y revisión humana.

## Referencias

- Roberts, M. E., Stewart, B. M., Tingley, D., Lucas, C., Leder-Luis, J., Gadarian, S. K., Albertson, B., & Rand, D. G. (2014). Structural Topic Models for Open-Ended Survey Responses. *American Journal of Political Science, 58*(4), 1064–1082. https://doi.org/10.1111/ajps.12103
- Roberts, M. E., Stewart, B. M., & Tingley, D. (2019). stm: An R Package for Structural Topic Models. *Journal of Statistical Software, 91*(2), 1–40. https://doi.org/10.18637/jss.v091.i02
- Grootendorst, M. (2022). BERTopic: Neural topic modeling with a class-based TF-IDF procedure. arXiv:2203.05794. https://doi.org/10.48550/arXiv.2203.05794
- Bianchi, F., Terragni, S., & Hovy, D. (2021). Cross-lingual Contextualized Topic Models with Zero-shot Learning. *Proceedings of EACL 2021*, 1676–1683. https://doi.org/10.18653/v1/2021.eacl-main.143
- Chang, J., Gerrish, S., Wang, C., Boyd-Graber, J., & Blei, D. M. (2009). Reading Tea Leaves: How Humans Interpret Topic Models. *NeurIPS 22*, 288–296.
- Mimno, D., Wallach, H., Talley, E., Leenders, M., & McCallum, A. (2011). Optimizing Semantic Coherence in Topic Models. *EMNLP 2011*, 262–272. https://aclanthology.org/D11-1024/
- Röder, M., Both, A., & Hinneburg, A. (2015). Exploring the Space of Topic Coherence Measures. *WSDM 2015*, 399–408. https://doi.org/10.1145/2684822.2685324
- Greene, D., O’Callaghan, D., & Cunningham, P. (2014). How Many Topics? Stability Analysis for Topic Models. arXiv:1404.4606. https://doi.org/10.48550/arXiv.1404.4606
