# Registro de revisión metodológica del modelado temático

## Diagnóstico inicial — 2026-07-30

Estado: **necesita revisión; los modelos existentes son exploratorios y no están validados**.

- `data/master_records.csv` contiene 2.975 registros, de los cuales 2.829 están dentro de 2020–2026. La salida anterior sumaba esas 2.829 representaciones de metadata y 864 representaciones full text para informar 3.693 observaciones. Esa suma no representa publicaciones únicas.
- `data/corpus.csv` contiene 1.246 filas: 1.231 con extracción marcada `ok` y 15 errores. Hay 79 grupos de DOI repetido que involucran 158 filas y cinco grupos de título exacto repetido.
- Sólo 693 publicaciones distintas de `master_records.csv` se relacionan actualmente con algún PDF por DOI o título exacto; 561 filas del corpus PDF no tienen una relación bibliográfica inequívoca y 12 presentan más de una coincidencia posible.
- El corpus metadata anterior tiene 2.829 filas y el full text 864, pero ambos son representaciones distintas de publicaciones que pueden solaparse. Las distribuciones anuales e idiomáticas no deben sumarlos.
- La STM vigente contiene 863 documentos, todos identificados como `full_text`, pese a que la configuración declara metadata como unidad principal. La diferencia 864→863 ocurre después de construir el CSV y debe trazarse dentro del preprocesamiento STM.
- La deduplicación anterior sólo detectaba colisiones del `document_id` durante la construcción. No auditaba títulos exactos, similitud alta, título+año, título+primer autor ni relación PDF–metadata.
- La tabla temporal STM anterior no distingue masa temática efectiva, documentos dominantes ni cobertura real.
- BERTopic no cuenta todavía con una ejecución principal comparable sobre exactamente las mismas publicaciones elegibles que una STM metadata.
- `K=22` carece de estabilidad y revisión humana; se conserva únicamente como resultado full text provisional.

Este registro se actualizará con los conteos canónicos, exclusiones, modelos preliminares y controles ejecutados.

## Primera reconstrucción canónica — 2026-07-30

Estado: **corpus construido y auditado; filtro y modelos todavía no validados por personas**.

- Publicaciones observadas en la tabla canónica: 3.460. Incluyen 2.974 publicaciones bibliográficas canónicas y 486 registros PDF sin metadata enlazada; no se suman representaciones metadata+full text.
- Registros con PDF señalado: 2.310. Publicaciones con extracción factual utilizable antes del filtro: 1.152. Textos completos elegibles como corpus secundario después de vínculo, período, limpieza y relevancia: 672.
- Corpus metadata principal claramente incluido: 2.182 publicaciones únicas. Intersección metadata–full text elegible: 672.
- Relevancia sobre 2.974 publicaciones bibliográficas: 2.198 `included`, 736 `borderline`, 39 `manual_review` y 1 `excluded`. De las incluidas, 16 no ingresan al corpus metadata por período o suficiencia textual. Los 775 casos no claros permanecen disponibles para revisión; no fueron borrados.
- Relaciones PDF: 760 vinculadas inequívocamente a metadata y 486 conservadas como publicaciones PDF independientes pendientes de revisión. Tras la deduplicación canónica no quedaron relaciones multívocas activas.
- Deduplicación: dos filas pertenecen a un grupo exacto fusionado; siete pares de similitud alta quedan como probables y no se fusionan automáticamente.
- Idiomas del corpus metadata: español 1.195, inglés 939, portugués 42, indonesio 4 y no determinado 2. Por ello STM se ejecuta separada para ES/EN/PT; ID queda sólo en BERTopic.
- Idiomas del full text elegible: español 406, inglés 223, portugués 24, indonesio 15 y no determinado 4.
- La muestra estratificada de relevancia contiene 200 publicaciones. Aún tiene cero codificaciones humanas; precision, recall, F1, acuerdo y kappa permanecen vacíos con estado `pending_human_review`.
- Todas las filas de ambos corpus tienen `document_id` único y la cobertura anual usa publicaciones relacionadas, no la suma de representaciones.

## Primera ejecución exploratoria — 2026-07-30

Estado: **ejecutada y auditable; no validada por especialistas**.

- STM metadata se estimó por idioma: español, 1.195 documentos y K=16; inglés, 939 y K=16; portugués, 42 y K=8. Son valores fijos preliminares, no una selección óptima de K. Los tres modelos reconcilian exactamente documentos, asignaciones dominantes y masa temática anual.
- La ejecución STM anterior de full text (863 documentos, K=22) se conserva sólo como legado. Su archivo temporal no contiene las columnas nuevas de conciliación y no debe compararse como si fuera una ejecución equivalente.
- La búsqueda BERTopic probó 12 configuraciones escalonadas. La configuración preliminar seleccionada produjo 42 clústeres y conservó 1.163 de 2.182 publicaciones como outliers (53,30%); no se forzó su reasignación ni se aplicó fusión automática de tópicos.
- BERTopic marcó 28 de 42 clústeres como potencialmente guiados por idioma por superar 80% de concentración en una lengua. Es una alerta descriptiva, no prueba causal. Los 42 clústeres superan el control geométrico interno implementado, pero todos siguen pendientes de juicio humano.
- La evaluación detectó vocabulario potencialmente contaminante en 4 clústeres BERTopic, 3 tópicos STM español y 6 STM inglés. No se eliminó automáticamente: aparece en las tablas de evaluación para inspección.
- La comparación usa 2.176 publicaciones compartidas entre BERTopic metadata y los tres STM por idioma. Identificó ocho alineamientos uno-a-uno preliminares; las relaciones restantes deben interpretarse como divisiones, fusiones, coincidencias débiles o ausencia de correspondencia, no como equivalencias.
- Se generaron 105 filas de validación temática, además de plantillas de intrusión de palabras y de tópicos. Ninguna tiene aún decisión experta, por lo que las etiquetas automáticas siguen marcadas `pending`.
- La auditoría del full text registra 1.246 candidatos, 672 textos elegibles y 15 eliminaciones en limpieza. Las pérdidas posteriores de `textProcessor` y `prepDocuments` quedan pendientes hasta ejecutar el STM full text rediseñado.
- Se listaron 166 candidatos a artefactos residuales (identificadores alfanuméricos y secuencias anómalas) para revisión antes de ampliar el análisis de texto completo.
- El dashboard permite alternar STM español/inglés/portugués, BERTopic metadata, salidas full text cuando existan, el modelo legado y la comparación. La red superior histórica conserva su universo de 2.975 publicaciones y no debe confundirse con el corpus metadata filtrado de 2.182 publicaciones mostrado por los modelos nuevos.
