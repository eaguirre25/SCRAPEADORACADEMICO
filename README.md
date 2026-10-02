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

La base documental de cada red se elige por cobertura: se toma el universo que mas asignaciones del modelo llega a representar.

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
