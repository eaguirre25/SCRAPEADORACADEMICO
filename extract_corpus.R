# extract_corpus.R
# Fase 1: Extracción de texto de PDFs desde Google Drive
# Output: data/corpus.csv con texto completo + metadatos
#
# Estructura del corpus:
#   filename, doi, titulo, anio, autores, revista, texto, paginas, status

library(googledrive)
library(httr)
library(pdftools)
library(readr)
library(dplyr)

cat("=== Inicio de extracción de corpus ===\n")
cat("Fecha:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n\n")

# ── Autenticación con Google Drive ────────────────────────────────────────────

cat("Conectando con Google Drive...\n")

# Construir token OAuth2 desde refresh token (sin interacción manual)
token <- oauth2.0_token(
  endpoint  = oauth_endpoints("google"),
  app       = oauth_app(
    appname = "scraper",
    key     = Sys.getenv("GOOGLE_CLIENT_ID"),
    secret  = Sys.getenv("GOOGLE_CLIENT_SECRET")
  ),
  scope       = "https://www.googleapis.com/auth/drive.readonly",
  use_oob     = FALSE,
  as_header   = TRUE,
  credentials = list(
    access_token  = NULL,
    token_type    = "Bearer",
    refresh_token = Sys.getenv("GOOGLE_REFRESH_TOKEN"),
    expires_in    = NULL
  )
)

drive_auth(token = token)
cat("Autenticación exitosa.\n\n")

# ── Leer metadatos del CSV maestro ────────────────────────────────────────────

MASTER_CSV  <- "data/master_records.csv"
CORPUS_CSV  <- "data/corpus.csv"
LOG_FILE    <- "data/extraction_log.csv"
TEMP_DIR    <- tempdir()

metadata <- read_csv(MASTER_CSV, show_col_types = FALSE) %>%
  mutate(across(everything(), as.character))

cat(sprintf("Metadatos cargados: %d registros\n\n", nrow(metadata)))

# ── Cargar corpus previo (para resumir si el workflow se interrumpe) ──────────

if (file.exists(CORPUS_CSV)) {
  corpus_prev <- read_csv(CORPUS_CSV, show_col_types = FALSE)
  ya_procesados <- corpus_prev$filename
  cat(sprintf("Corpus previo encontrado: %d archivos ya procesados. Se saltearán.\n\n",
              length(ya_procesados)))
} else {
  corpus_prev  <- NULL
  ya_procesados <- character(0)
}

# ── Listar PDFs en la carpeta de Drive ───────────────────────────────────────

folder_id <- Sys.getenv("DRIVE_FOLDER_ID")
cat("Listando PDFs en Drive...\n")

archivos_drive <- drive_ls(
  path  = as_id(folder_id),
  type  = "application/pdf"
)

cat(sprintf("PDFs encontrados en Drive: %d\n\n", nrow(archivos_drive)))

# Filtrar los ya procesados
archivos_pendientes <- archivos_drive %>%
  filter(!name %in% ya_procesados)

cat(sprintf("PDFs pendientes de procesar: %d\n\n", nrow(archivos_pendientes)))

# ── Función de extracción de texto ───────────────────────────────────────────

extraer_texto <- function(drive_file) {
  nombre  <- drive_file$name
  file_id <- drive_file$id

  # Descargar a carpeta temporal
  destino <- file.path(TEMP_DIR, nombre)

  tryCatch({
    drive_download(
      file      = as_id(file_id),
      path      = destino,
      overwrite = TRUE
    )

    # Extraer texto con pdftools
    paginas <- pdf_text(destino)
    texto   <- paste(paginas, collapse = "\n")
    texto   <- trimws(texto)

    # Limpiar archivo temporal
    file.remove(destino)

    if (nchar(texto) < 100) {
      return(list(texto = "", paginas = length(paginas), status = "vacio"))
    }

    return(list(texto = texto, paginas = length(paginas), status = "ok"))

  }, error = function(e) {
    if (file.exists(destino)) file.remove(destino)
    return(list(texto = "", paginas = 0, status = paste0("error: ", conditionMessage(e))))
  })
}

# ── Inferir DOI desde nombre de archivo ──────────────────────────────────────

doi_desde_nombre <- function(nombre) {
  # Los PDFs se nombran como "10.1080_xxx.pdf" → restaurar DOI "10.1080/xxx"
  doi <- sub("\\.pdf$", "", nombre)
  doi <- sub("_", "/", doi, fixed = FALSE)  # solo el primer _
  return(tolower(trimws(doi)))
}

# ── Procesar PDFs ─────────────────────────────────────────────────────────────

resultados <- vector("list", nrow(archivos_pendientes))
log_rows   <- vector("list", nrow(archivos_pendientes))

for (i in seq_len(nrow(archivos_pendientes))) {
  archivo <- archivos_pendientes[i, ]
  nombre  <- archivo$name

  cat(sprintf("[%d/%d] Procesando: %s\n", i, nrow(archivos_pendientes), nombre))

  # Extraer texto
  resultado <- extraer_texto(archivo)

  # Recuperar metadatos cruzando por DOI
  doi_archivo <- doi_desde_nombre(nombre)
  meta_fila   <- metadata %>%
    filter(tolower(trimws(doi)) == doi_archivo | tolower(trimws(record_id)) == doi_archivo) %>%
    slice(1)

  resultados[[i]] <- tibble(
    filename        = nombre,
    doi             = if (nrow(meta_fila) > 0) meta_fila$doi[1]             else doi_archivo,
    titulo          = if (nrow(meta_fila) > 0) meta_fila$title[1]           else "",
    anio            = if (nrow(meta_fila) > 0) meta_fila$publication_year[1] else "",
    autores         = if (nrow(meta_fila) > 0) meta_fila$authors[1]         else "",
    revista         = if (nrow(meta_fila) > 0) meta_fila$origin[1]          else "",
    texto           = resultado$texto,
    paginas         = resultado$paginas,
    status          = resultado$status,
    fecha_extraccion = Sys.Date()
  )

  log_rows[[i]] <- tibble(
    filename = nombre,
    status   = resultado$status,
    paginas  = resultado$paginas,
    chars    = nchar(resultado$texto)
  )

  # Guardar progreso cada 50 archivos
  if (i %% 50 == 0) {
    parcial <- bind_rows(resultados[1:i])
    if (!is.null(corpus_prev)) {
      parcial <- bind_rows(corpus_prev, parcial)
    }
    write_csv(parcial, CORPUS_CSV)
    cat(sprintf("  → Progreso guardado: %d archivos procesados.\n", i))
  }
}

# ── Guardar corpus final ──────────────────────────────────────────────────────

corpus_nuevo <- bind_rows(resultados)

corpus_final <- if (!is.null(corpus_prev)) {
  bind_rows(corpus_prev, corpus_nuevo)
} else {
  corpus_nuevo
}

write_csv(corpus_final, CORPUS_CSV)

# Guardar log
log_final <- bind_rows(log_rows)
write_csv(log_final, LOG_FILE)

# ── Resumen final ─────────────────────────────────────────────────────────────

cat("\n=== Resumen de extracción ===\n")
cat(sprintf("Total en corpus: %d archivos\n", nrow(corpus_final)))
cat(sprintf("Exitosos (ok):   %d\n", sum(corpus_final$status == "ok")))
cat(sprintf("Vacíos:          %d\n", sum(corpus_final$status == "vacio")))
cat(sprintf("Con error:       %d\n", sum(grepl("^error", corpus_final$status))))
cat(sprintf("Tamaño corpus:   %.1f MB\n",
            file.size(CORPUS_CSV) / 1024 / 1024))
cat("\n=== Extracción completada ===\n")
