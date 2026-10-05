# SCRAPEADORACADEMICO

## Modelado temático híbrido

El repositorio conserva la STM y agrega BERTopic multilingüe, corpus auditables, comparación entre modelos y validación humana. Consulte la guía reproducible en [docs/TOPIC_MODELING.md](docs/TOPIC_MODELING.md).

Repositorio para recolectar, filtrar, analizar y publicar un tablero de literatura academica sobre direccion, gestion y liderazgo escolar.

El proyecto combina scraping desde fuentes abiertas, curado de relevancia, corpus para analisis STM y un dashboard HTML publicado desde `docs/index.html`.

## Que contiene

- `main.py`: scraper principal y actualizacion de registros.
- `relevance_filter.py`: clasificacion de registros relevantes, en revision y rechazados.
- `generate_dashboard.py`: dashboard interactivo con redes tematicas por modelo, topicos STM y tabla paginada.
- `generate_article_table.py`: tabla de trabajo con buscador de texto completo y cita APA 7 por articulo.
- `apa_citation.py`: construccion de referencias en normas APA 7 desde los registros del scraper.
- `generate_dashboard_three_columns.py`: dashboard liviano de tres columnas desde `data/master_records.csv`.
- `dashboard_healthcheck.py`: chequeo rapido de archivos, cantidades y estado STM.
- `data/`: registros, corpus, logs y reportes.
- `output/`: resultados STM, tablas y graficos.
- `docs/index.html`: tablero navegable para GitHub Pages o inspeccion local.
- `.github/workflows/`: automatizaciones para scraping, dashboard, corpus y STM.

## Inspeccion local rapida

Desde la raiz del repositorio:

```powershell
py -3 dashboard_healthcheck.py
```

El widget local incluye un acceso directo para abrir la tabla navegable de articulos (`docs/index.html#articulos`) y dejar listo el buscador. Esa tabla permite filtrar rapidamente por titulo, autor, resumen, palabras clave, revista, fuente o anio.

## Redes tematicas por modelo

En `docs/index.html` el selector de modelado redibuja el grafo, no solo las tarjetas. Cada modelo (BERTopic macros y subtopicos, STM es/en/pt, STM historica) trae dos vistas conmutables:

- **Red de documentos**: nodos = articulos, aristas = palabras clave compartidas, color = topico asignado por el modelo activo. La leyenda inferior traduce cada color a su topico.
- **Red de topicos**: nodos = topicos dimensionados por cantidad de documentos. Las aristas usan la similitud c-TF-IDF que exporta BERTopic; para las STM, que no exportan matriz de similitud, se derivan del segundo topico de cada documento.

Las dos vistas comparten un fondo azul estelar y nodos esféricos con relieve. La simulación D3 conserva el arrastre del conjunto. Al seleccionar un nodo se iluminan sus enlaces directos y se abre una ficha lateral; clic en el fondo, Escape o el botón de cierre quitan la selección. Los documentos muestran etiquetas autor–año al acercar el zoom (o al seleccionar), con control de superposición; los tópicos muestran sus nombres. La ficha documental reutiliza las referencias de `apa_citation.py` y avisa qué datos faltan. Los controles permiten acercar, alejar y encuadrar la red. El renderizador y los estilos viven en `docs/stellar-network.js` y `docs/stellar-network.css`, incorporados por el generador y conservados en cada actualización.

La red documental incluye todos los registros de `data/master_records.csv`, incluso sin DOI, sin etiquetas, sin tema y sin enlaces. El cálculo se encuentra en `keyword_network.py`; se usa el diccionario revisable `config/keyword_thesaurus.csv`. Las equivalencias multilingües y exclusiones son propuestas pendientes de revisión. Dirección, gestión y liderazgo conservan entradas diferenciadas; también se distinguen liderazgo instruccional y pedagógico. Las etiquetas originales no se modifican.

Cada enlace requiere dos etiquetas distintas compartidas y un mínimo de semejanza. La medida predeterminada es Jaccard ponderado por IDF: suma de los pesos de la intersección dividida por la suma de los pesos de la unión. El peso de cada etiqueta es `log((N + 1) / (df + 1)) + 1`, donde N es el número de registros con etiquetas retenidas y df su frecuencia documental. Se consideran todas las etiquetas retenidas, sin recortes de doce etiquetas ni de cuarenta apariciones. Se ofrecen niveles 0,10, 0,20 y 0,30, además de un control Jaccard simple de 0,20. El nivel 0,20 es una referencia exploratoria intermedia, no una selección validada ni optimizada por apariencia.

El botón **Método y comparación** informa la cobertura por fuente, las exclusiones, las equivalencias, los enlaces y componentes de cada configuración y una comparación descriptiva con los temas de cada modelo. Las etiquetas históricas no conservan su procedencia exacta: `main.py` lee keywords de OpenAlex y, cuando faltan, topics; también lee campos subject de repositorios. La fuente del registro no acredita palabras clave de autor. La auditoría marca esta inferencia y los casos de fuentes combinadas como inciertos. El sesgo de cobertura requiere atención: no se completan etiquetas faltantes ni se asignan temas artificialmente.

La geometría resulta de fuerzas D3; las distancias dibujadas no son una escala de semejanza semántica. Los enlaces documentales se dibujan en Canvas para conservar las redes densas sin miles de líneas SVG; los nodos mantienen selección, arrastre y etiquetas accesibles. El tamaño documental depende del grado de la configuración activa; el de los tópicos, de su cantidad documental exportada. La ficha de un documento muestra las etiquetas retenidas, la procedencia inferida y las etiquetas compartidas y puntuación de cada enlace. No se recortan nodos ni enlaces.

Para reproducir: `python generate_dashboard.py`. Se regeneran `docs/keyword-network-data.js`, `docs/keyword-network-audit.json` y una copia de consulta `docs/keyword-thesaurus.csv`. La auditoría registra el hash SHA-256 del diccionario. Las pruebas en `tests/test_keyword_network.py` verifican un ejemplo calculado a mano, las distinciones conceptuales, la falta de datos y la ausencia de recortes.

Referencias metodológicas: van Eck, N. J., & Waltman, L. (2010). Software survey: VOSviewer, a computer program for bibliometric mapping. *Scientometrics, 84*, 523–538. https://doi.org/10.1007/s11192-009-0146-3; van Eck, N. J., & Waltman, L. (2023). *VOSviewer manual* (versión 1.6.20). https://www.vosviewer.com/documentation/Manual_VOSviewer_1.6.20.pdf. Estas fuentes fundamentan la limpieza y normalización bibliométrica; la implementación y sus filtros son decisiones explícitas de este proyecto.

Las tarjetas temáticas abren una ficha de revisión con los diagnósticos y todas las asignaciones exportadas, búsqueda y paginación. Permite corregir el nombre, marcar un tema como validado o pendiente de correcciones, escribir notas y revisar documentos. Las revisiones se guardan en este navegador y se exportan/importan como JSON; no modifican automáticamente las asignaciones originales ni reentrenan los modelos. `docs/topic-review-data.json` se regenera junto con el dashboard. Las cantidades del corpus maestro y las filas del modelado se identifican por separado: un registro sin asignación vinculada no implica necesariamente que el modelo no lo haya procesado.

## Búsqueda y filtro de pertinencia

**Búsqueda (`main.py`).** OpenAlex se consulta con 15 frases exactas en español, inglés y portugués (gestión/dirección escolar, liderazgo escolar y directivo, school leadership, principalship, gestão escolar, entre otras). CONICET Digital se consulta con las frases **entre comillas**: sin ellas su buscador devolvía cualquier trabajo con las palabras sueltas («school» y «principal»). El resumen de CONICET se guarda sin la cabecera de títulos y autores que antepone su buscador.

**Filtro (`relevance_filter.py`).** Una auditoría de octubre de 2026 mostró que alrededor del 90 % de los registros de CONICET en el maestro no trataban sobre dirección escolar (paleobotánica, peronismo, aves) y que unos 500 trabajos pertinentes de OpenAlex habían quedado rechazados. Las reglas corregidas:

- «principal» cuenta como cargo solo en contexto inglés escolar («school principal», «principals», junto a «school» o «teacher»); en castellano es casi siempre un adjetivo.
- Un cargo directivo o una acción de gestión deben aparecer **a no más de 8 palabras** de un término escolar; antes bastaba con que ambos figuraran en cualquier lugar del resumen.
- No cuentan como gestión escolar «escuela de gestión estatal/privada/social» (tipo de sostenimiento), la gestión del agua, de residuos, ambiental o del aula, ni «escuela de pensamiento», «business school» y similares.
- Un título que nombra el campo («gestión educativa», «educational leadership», «educational administration») se incluye, salvo que el foco sea la educación superior.
- Se reconocen términos en portugués y cargos en el título («El director como líder…»).
- Los rechazados **se reevalúan en cada corrida**, así las correcciones recuperan trabajos descartados antes.
- `config/relevance_overrides.csv` (`record_id,decision,nota`, con `incluir` o `excluir`) fija decisiones manuales que prevalecen sobre las reglas.

Sobre los datos de `main` del 4 de octubre de 2026, el maestro pasa de 4.359 a 4.460 registros: OpenAlex de 3.519 a 4.122 y CONICET de 840 a 338. Las guías de biblioteca (LibGuides) se excluyen por no ser trabajos académicos.

**Validación.** `scripts/build_relevance_validation.py` sortea 200 registros estratificados por fuente y decisión del filtro en `data/validacion/muestra_pertinencia.xlsx`, sin mostrar la decisión. Los títulos que nombran explícitamente la dirección o gestión escolar vienen marcados «si» (editable); tras marcar el resto de la columna «pertinente» (si / no / dudoso), `scripts/evaluate_relevance_validation.py` estima precisión y exhaustividad ponderadas por estrato en `data/validacion/resultado_validacion.json`.

## App para el celular

El sitio de `docs/` funciona como aplicación instalable (PWA): se abre desde la dirección de GitHub Pages del repositorio y se agrega a la pantalla de inicio, sin pasar por tiendas de aplicaciones.

- **Android (Chrome):** abrir el tablero y tocar **Instalar** en el aviso inferior, o menú ⋮ → *Instalar aplicación*.
- **iPhone (Safari):** botón Compartir → *Agregar a inicio*.

Una vez instalada, abre a pantalla completa con una barra inferior para Tablero, Artículos, Biblioteca, Argentina y Asistente. En pantallas chicas la tabla de artículos se muestra como tarjetas y al tocar una se baja a su ficha con la cita APA 7. Las páginas ya abiertas quedan guardadas en el teléfono y se pueden consultar sin conexión; lo que nunca se abrió requiere conexión. Las revisiones y el fichado siguen guardándose en el navegador del dispositivo, como en la versión de escritorio: conviene exportarlas.

Archivos: `docs/manifest.webmanifest`, `docs/sw.js` (service worker: red primero y copia local sin conexión), `docs/pwa.js` (barra inferior y aviso de instalación), `docs/mobile.css` (ajustes para teléfonos) y `docs/icons/`. `inject_pwa.py` agrega estas referencias a cada página HTML; el workflow **Generar Dashboard** lo ejecuta después de regenerar, por lo que la app se mantiene en cada actualización automática. Si se cambia `sw.js`, subir `VERSION` para que los teléfonos descarten la copia anterior.

## Recuperación de metadatos de CONICET Digital

Los registros cosechados del buscador de CONICET traen título, autores, resumen y handle, pero no DOI, revista, volumen, número, páginas, palabras clave ni tipo documental. Además, su año es el de **carga en el repositorio**, no el de publicación, lo que afecta los filtros por período (por ejemplo, Argentina 2020–2026).

`scripts/enrich_metadata.py` busca cada registro por título y autores en fuentes alternativas: CONICET OAI-PMH por handle (si responde), OpenAlex y Crossref; con el DOI completa volumen, número y páginas. Una coincidencia se acepta solo si el título es casi idéntico (similitud ≥ 0,90), comparte al menos un apellido y el año encontrado no es posterior al de carga. Los casos parecidos que no cumplen todo quedan como «revisar» y no se aplican. Nunca se modifican título, autores ni resumen.

- Se ejecuta en GitHub Actions: workflow **Enriquecer metadatos CONICET** (manual) y como paso del **Academic Scraper** para los registros nuevos. Al terminar dispara Argentina · BERTopic y el dashboard.
- `data/metadata_enrichment.csv` registra, por registro, la fuente, las puntuaciones, el año original y si se aplicó; sirve de caché. Si una fuente no responde, el registro queda en «error» y se reintenta en la próxima corrida.
- `data/metadata_enrichment_report.json` resume la corrida e informa los registros cuya clasificación de pertinencia cambiaría con los nuevos datos.
- Volumen, número y páginas se leen desde `data/metadata_enrichment.csv` al armar la cita APA 7 (`apa_citation.py`), porque el maestro no tiene esas columnas.
- Para decidir a mano un caso «revisar» (o anular uno aceptado), agregar una fila en `config/metadata_enrichment_overrides.csv` con `record_id,decision,nota` y decisión `aceptar` o `rechazar`; se aplica en la siguiente corrida.

## Citas en normas APA 7

`docs/articulos.html` incluye la columna **Normas APA** con un boton que copia la referencia al portapapeles en texto plano y en HTML con cursivas.

Los registros no traen volumen, numero, paginas ni editorial, asi que la cita los emite como marcadores visibles (`[vol]`, `[num]`, `[pp.]`, `[Editorial]`) y la fila indica que campos completar a mano.

La inversion del nombre depende del idioma del registro: en espanol y portugues se asumen dos apellidos cuando el nombre lo permite, en ingles uno solo. El idioma sale del modelado multilingue cuando existe y, si no, se infiere del titulo y el resumen.

Para abrir el dashboard localmente:

```powershell
cd docs
py -3 -m http.server 8082
```

Luego abrir:

```text
http://localhost:8082/
```

## Estado actual del tablero

El healthcheck valida:

- existencia de `docs/index.html`;
- cantidad de registros en `data/master_records.csv`, `data/review_records.csv` y `data/rejected_records.csv`;
- presencia de insumos y salidas STM en `data/corpus.csv.gz` y `output/`;
- generacion de `data/dashboard_healthcheck.json` para auditoria.

## Regenerar dashboard

Dashboard completo con red, topicos STM y articulos:

```powershell
py -3 generate_dashboard.py
```

Dashboard operativo liviano de tres columnas:

```powershell
py -3 generate_dashboard_three_columns.py
```

Despues de regenerar, volver a ejecutar:

```powershell
py -3 dashboard_healthcheck.py
```

## Subida de PDFs a Google Drive

El workflow principal corre cada 3 dias. Primero recolecta registros, luego filtra la base con `relevance_filter.py` y recien despues sube a Google Drive los PDFs de registros validados en `data/master_records.csv`.

Para recuperar pendientes desde la ultima subida historica, el workflow usa:

```text
PDF_UPLOAD_AFTER_DATE=2026-04-25
```

Los PDFs se nombran con este formato:

```text
ApellidoAutor1 ApellidoAutor2 - anio - recorte del titulo.pdf
```

Si hay mas de dos autores:

```text
ApellidoAutor1 et al - anio - recorte del titulo.pdf
```

La subida requiere estos secrets en GitHub Actions:

```text
DRIVE_FOLDER_ID
GOOGLE_CLIENT_ID
GOOGLE_CLIENT_SECRET
GOOGLE_REFRESH_TOKEN
```

## Dependencias Python

```powershell
py -3 -m pip install -r requirements.txt
```

## Automatizaciones

Los workflows de GitHub Actions corren en cascada:

1. `Academic Scraper`: cada 3 dias recolecta registros, actualiza la base, filtra relevancia y sube a Google Drive los PDFs validados.
2. `Extracción de corpus (PDFs → texto)`: se dispara cuando termina bien el scraper; lee los PDFs de Drive y actualiza `data/corpus.csv.gz` (comprimido para respetar el límite de 100 MiB por archivo de GitHub).
3. `Análisis STM – Dirección Escolar`: se dispara cuando termina bien la extracción de corpus; recalcula tópicos, tablas, modelo e informe STM en `output/`.
4. `Generar Dashboard`: se dispara cuando termina bien STM; regenera `docs/index.html` y corre `dashboard_healthcheck.py`.

Cada workflow conserva `workflow_dispatch`, por lo que tambien puede ejecutarse manualmente desde GitHub Actions.

### Formato del corpus de texto y limite de tamano

`data/corpus.csv.gz` es el corpus de texto extraido de los PDFs de Drive (CSV comprimido con gzip, UTF-8; las columnas incluyen `filename`, `doi`, `texto` y `status`). Pandas, readr y el modulo `csv` con `gzip` lo leen directamente. Se comprime para mantener el archivo por debajo del limite de tamano por archivo de GitHub y reducir el peso del repositorio.

## Fuentes y licencia

Los datos provienen de fuentes academicas abiertas, incluyendo OpenAlex y repositorios institucionales. Revisar las condiciones de cada fuente antes de redistribuir datos enriquecidos o archivos derivados.
### Argentina · BERTopic 2020–2026

El botón **Argentina · BERTopic 2020–2026** del dashboard abre `docs/argentina.html`. Esta rama ajusta un modelo independiente sobre publicaciones del master reunido por el workflow, con deduplicación del pipeline existente y años de publicación 2020–2026. El criterio es **objeto de estudio en Argentina**, incluidos estudios comparativos; repositorio y afiliación no sustituyen país del estudio. Las menciones del título/resumen producen candidatos pendientes de revisión. Los registros sin evidencia permanecen accesibles en «Revisar corpus» para inclusión manual. Se excluyen del ajuste los candidatos con puntaje de pertinencia ≤ 0 del filtro general (aceptados solo por la segunda revisión; en la revisión de octubre de 2026 eran los 14 trabajos ajenos a la gestión escolar: biología, agro, arqueología, turismo). Figuran en el filtro «Fuera de tema» y una inclusión manual los recupera; el umbral es `min_relevance_score` en `config/argentina_analysis.json`. No se afirma cobertura exhaustiva de la producción argentina; 2026 está en curso.

La constelación permite alternar vecinos semánticos recíprocos (cinco vecinos, coseno ≥ 0,70 en embeddings originales) y palabras clave (Jaccard IDF ≥ 0,20, dos términos). La vecindad semántica es una reducción explícita de enlaces, no citación; se reportan nueve combinaciones de k/umbral. Todos los candidatos, aislados y documentos sin tópico permanecen representados. Los tópicos usan conexiones c-TF-IDF ≥ 0,35, sin enlaces agregados para forzar conectividad.

El ajuste usa UMAP con 10 vecinos, 10 dimensiones y min_dist 0,1, y HDBSCAN con min_samples 5. El tamaño mínimo de tópico ya no se hereda del modelo global (35, demasiado grande para unos 500 documentos: dejaba 38 % sin tópico y la estabilidad entre semillas era casi nula). Se elige con una regla declarada: entre los tamaños 10, 15, 20, 25 y 35, los que en cinco semillas de UMAP dejan en promedio como máximo 35 % sin tópico y forman al menos tres tópicos; de ellos, el de mayor ARI medio entre pares de semillas (empate: el mayor). Si ninguno cumple, se usa 15. La tabla completa figura en «Criterios y método». La vectorización usa min_df=1/max_df=1, ya que BERTopic vectoriza textos agregados por tópico y filtros mayores pueden eliminar el vocabulario con pocos grupos. Se conservan embeddings multilingües y pesos por campo del pipeline. Dos limpiezas se aplican solo en este análisis, sin modificar el maestro: se quita la cabecera que CONICET antepone al resumen (títulos, traducciones y autores), que repetía el título y sumaba nombres propios a los embeddings; y se excluyen los topónimos (Argentina, provincias) del vocabulario de los tópicos, porque todo el corpus se seleccionó por mencionarlos y dominaban las etiquetas. Los topónimos siguen en el texto de los embeddings y en la evidencia territorial; revisar igualmente si un grupo refleja geografía o contenido. El ajuste es exploratorio: no se presenta como solución validada.

Para reproducir: instalar `requirements-topic-modeling.txt` y ejecutar `python scripts/run_argentina_analysis.py --mode all`. Configuración: `config/argentina_analysis.json`; resultados y trazabilidad: `output/argentina/`; corpus seleccionado descargable: `docs/argentina-corpus.csv`. `--mode render` requiere solo bibliotecas estándar y recalcula la selección/red léxica, reutilizando resultados únicamente si coinciden selección y configuración; ante cambios publica estado «ajuste pendiente».

Las revisiones documentales y de etiquetas se guardan en el navegador. Exportar el JSON e incorporarlo en `config/argentina_document_reviews.json`; ejecutar **Argentina · BERTopic 2020–2026** en Actions para incorporar decisiones y recalcular. Cambiar una etiqueta/decisión en la página no reentrena BERTopic. Las interpretaciones se vinculan al identificador del ajuste y no se trasladan automáticamente a tópicos de un modelo distinto. La rama se actualiza al finalizar **Academic Scraper** y ante cambios del corpus/configuración.
