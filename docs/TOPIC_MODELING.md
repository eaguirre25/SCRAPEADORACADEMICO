# Modelado temático híbrido

## Qué resuelve cada modelo

La STM se conserva como línea de base estadística. Cada documento es una mezcla de tópicos y su prevalencia puede relacionarse con el año mediante una spline. BERTopic es el mapa semántico principal: usa embeddings multilingües, UMAP y HDBSCAN para agrupar documentos por contexto.

Las medidas no son intercambiables: prevalence en STM es el promedio de una proporción temática; en BERTopic es el porcentaje de documentos asignados al cluster. El tópico BERTopic -1 identifica outliers y no se elimina del reporte.

## Corpus e identificadores

El constructor genera dos corpus. Metadata usa título por tres, palabras clave por dos y resumen una vez; es el mapa principal de todos los registros validados. Fulltext contiene textos extraídos de PDF con retiro prudente y auditado de referencias.

El document_id usa DOI normalizado; en su ausencia, identificador persistente y luego un hash de título, año y primer autor. No depende del número de fila. El filtro predeterminado es 2020–2026 y 2026 se marca como incompleto.

La limpieza BERTopic conserva sintaxis y términos del dominio. La STM aplica una limpieza más agresiva. Los términos de dominio sólo se quitan si stm.remove_domain_stopwords está activado.

## Ejecución

    python scripts/build_modeling_corpus.py --config config/topic_modeling.yml
    Rscript stm_analysis.R --config config/topic_modeling.yml
    python scripts/run_bertopic.py --config config/topic_modeling.yml --corpus-unit metadata
    python scripts/evaluate_topic_models.py --config config/topic_modeling.yml
    python scripts/compare_topic_models.py --config config/topic_modeling.yml
    python scripts/export_topic_dashboard.py --config config/topic_modeling.yml
    python generate_dashboard.py

El orquestador equivalente es:

    python scripts/run_topic_pipeline.py --config config/topic_modeling.yml --mode full

La configuración admite variables TOPIC_MODELING__SECCION__CLAVE. Los scripts compatibles aceptan --set seccion.clave=valor. La semilla predeterminada es 42. Para réplicas STM use --run-stability en el orquestador o RUN_STABILITY=true.

## Selección e interpretación

La STM busca K=8,10,…,40 y combina coherencia, exclusividad, held-out likelihood, residuales y estabilidad con pesos configurables. Si no se ejecutan réplicas, la tabla lo advierte y usa un valor neutral para estabilidad. K_recomendado es una recomendación multicriterio, no un óptimo universal.

BERTopic usa paraphrase-multilingual-mpnet-base-v2, embeddings normalizados y almacenados como NPY, UMAP reproducible y HDBSCAN. El manifiesto guarda hashes, IDs, modelo y dimensión. Se exportan probabilidades, segundo tópico, margen, ambigüedad y outliers.

La alineación combina solapamiento documental (70 %) y palabras (30 %). centroid_similarity queda vacío hasta disponer de centroides comparables; no se imputa. Las relaciones son ayudas de revisión, no equivalencias objetivas.

## Validación humana

La plantilla output/topic_models/validation/topic_validation_template.csv conserva respuestas anteriores. Las etiquetas estables se cargan desde config/topic_labels.csv. Ninguna propuesta automática se marca como validada.

## Salidas y compatibilidad

Las salidas normalizadas viven en output/topic_models. Se conservan output/tabla_topicos.csv y output/document_topics.csv para el dashboard heredado. Modelos, embeddings y corpus analíticos regenerables no se versionan; Actions publica tablas e informes como artefactos.

## GitHub Actions y memoria

Ejecute Modelado temático híbrido manualmente y seleccione corpus, stm, bertopic, compare, dashboard o full. El scraper frecuente no dispara el modelado pesado. La caché conserva Hugging Face y embeddings.

En CPU, MPNet puede requerir aproximadamente 2–5 GB y decenas de minutos para unos 3.000 resúmenes. STM con grilla completa y cinco réplicas puede tardar varias horas. Ante falta de memoria reduzca bertopic.batch_size, desactive probabilidades completas mediante configuración, ejecute etapas separadas y deje run_stability en false.

## Limitaciones

- La calidad temática sigue dependiendo del filtro de relevancia. Un tópico ambiental, hospitalario u otro fuera del dominio es una señal de contaminación, no un motivo para borrar sin trazabilidad.
- La cobertura de PDF no es uniforme por idioma, fuente o año; sus tendencias pueden reflejar disponibilidad y no cambio científico.
- 2026 es incompleto.
- Las etiquetas son interpretaciones humanas o propuestas automáticas.
- La estabilidad BERTopic avanzada, centroides cruzados y fusiones revisadas requieren ejecución completa y revisión humana; no se sustituyen con valores inventados.
