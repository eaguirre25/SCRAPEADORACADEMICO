# Resumen de validación sustantiva provisional

Generado el 2026-07-31 sobre la solución BERTopic seleccionada (`document_topics.csv` SHA-256 `71b2bcbdfc09…`).

## Alcance

- Corpus: 2.182 publicaciones; 1.340 asignadas a T0–T13 y 842 outliers conservados.
- Se propusieron 14 etiquetas humanas provisionales; **ninguna está validada por especialistas**.
- Se prepararon 582 filas de revisión (471 documentos únicos), 42 pruebas de intrusión léxica, 210 pruebas de intrusión temática y 262 outliers estratificados.
- No se modificaron embeddings, UMAP, HDBSCAN, asignaciones, outliers ni hiperparámetros.

## Decisiones interpretativas prioritarias

1. Mantener separados T1 (calidad/mejora) y T7 (planificación/innovación), revisando sus fronteras.
2. Mantener separados T2 (digitalización/TIC) y T9 (IA/analítica), tratándolos como relacionados jerárquicamente.
3. Revisar posibles divisiones en T3, T4 y T12; no ejecutarlas sin codificación humana.
4. Etiquetar T8 como género y desigualdades; la muestra revisada no sustenta todavía agregar “raza” al nombre.
5. Conservar alertas geográficas en T11 y T12.

## Cómo completar la validación

Dos revisores deben completar los campos `human_*` sin mirar la respuesta del otro. Luego se calcula acuerdo (porcentaje y kappa/alpha según escala), se resuelven discrepancias y sólo entonces se cambia `label_status` a `validated`. Las columnas `provisional_fit` y las propuestas de fusión/división son ayudas para priorizar, no verdad de terreno.
