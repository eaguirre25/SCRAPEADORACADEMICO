# extract_corpus.R
# Fase 1: Extracción de texto de PDFs desde Google Drive
# Usa httr directamente contra la Drive REST API (sin paquete googledrive)
# Output: data/corpus.csv

library(httr)
library(pdftools)
library(readr)
library(dplyr)

cat("=== Inicio de extracción de corpus ===\n")
cat("Fecha:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n\n")

# ── Obtener access token ──────────────────────────────────────────────────────

cat("Obteniendo access token...\n")

resp <- POST(
  "https://oauth2.googleapis.com/token",
  body = list(
    client_id     = Sys.getenv("GOOGLE_CLIENT_ID"),
    client_secret = Sys.getenv("GOOGLE_CLIENT_SECRET"),
    refresh_token = Sys.getenv("GOOGLE_REFRESH_TOKEN"),
    grant_type    = "refresh_token"
  ),
  encode = "form"
)
stop_for_status(resp)
access_token <- content(resp)$access_token
cat("Access token obtenido OK.\n\n")

# ── Funciones Drive REST API ──────────────────────────────────────────────────

drive_headers <- function() {
  add_headers(Authorization = paste("Bearer", access_token))
}

# Listar archivos en una carpeta
drive_list_files <- function(folder_id) {
  all_files <- list()
  page_token <- NULL

  repeat {
    params <- list(
      q         = sprintf("'%s' in parents and trashed=false and mimeType='application/pdf'", folder_id),
      fields    = "nextPageToken,files(id,name)",
      pageSize  = 1000
    )
    if (!is.null(page_token)) params$pageToken <- page_token

    r <- GET("https://www.googleapis.com/drive/v3/files",
             drive_headers(), query = params)
    stop_for_status(r)
    data <- content(r)
    all_files <- c(all_files, data$files)

    page_token <- data$nextPageToken
    if (is.null(page_token)) break
  }

  data.frame(
    id   = sapply(all_files, `[[`, "id"),
    name = sapply(all_files, `[[`, "name"),
    stringsAsFactors = FALSE
  )
}

# Descargar un archivo por ID
drive_download_file <- function(file_id, destino) {
  r <- GET(
    sprintf("https://www.googleapis.com/drive/v3/files/%s", file_id),
    drive_headers(),
    query   = list(alt = "media"),
    write_disk(destino, overwrite = TRUE)
  )
  stop_for_status(r)
  invisible(destino)
}

# ── Rutas ─────────────────────────────────────────────────────────────────────

MASTER_CSV <- "data/master_records.csv"
CORPUS_CSV <- "data/corpus.csv"
LOG_FILE   <- "data/extraction_log.csv"
TEMP_DIR   <- tempdir()
folder_id  <- Sys.getenv("DRIVE_FOLDER_ID")

# ── Leer metadatos ────────────────────────────────────────────────────────────

metadata <- read_csv(MASTER_CSV, show_col_types = FALSE) %>%
  mutate(across(everything(), as.character))
cat(sprintf("Metadatos cargados: %d registros\n\n", nrow(metadata)))

# ── Cargar corpus previo ──────────────────────────────────────────────────────

if (file.exists(CORPUS_CSV)) {
  corpus_prev   <- read_csv(CORPUS_CSV, show_col_types = FALSE) %>%
    mutate(across(everything(), as.character))
  ya_procesados <- corpus_prev$filename
  cat(sprintf("Corpus previo: %d archivos ya procesados.\n\n", length(ya_procesados)))
} else {
  corpus_prev   <- NULL
  ya_procesados <- character(0)
}

# ── Listar PDFs ───────────────────────────────────────────────────────────────

cat(sprintf("Listando PDFs en carpeta: %s\n", folder_id))
archivos_drive <- drive_list_files(folder_id)
cat(sprintf("PDFs encontrados: %d\n", nrow(archivos_drive)))

archivos_pendientes <- archivos_drive[!archivos_drive$name %in% ya_procesados, ]
cat(sprintf("PDFs pendientes:  %d\n\n", nrow(archivos_pendientes)))

# ── Funciones de extracción ───────────────────────────────────────────────────

doi_desde_nombre <- function(nombre) {
  doi <- sub("\\.pdf$", "", nombre, ignore.case = TRUE)
  doi <- sub("_", "/", doi, fixed = TRUE)
  tolower(trimws(doi))
}

extraer_texto <- function(file_id, nombre) {
  destino <- file.path(TEMP_DIR, nombre)
  tryCatch({
    drive_download_file(file_id, destino)
    paginas <- pdf_text(destino)
    texto   <- trimws(paste(paginas, collapse = "\n"))
    file.remove(destino)
    if (nchar(texto) < 100) {
      return(list(texto = "", paginas = length(paginas), status = "vacio"))
    }
    list(texto = texto, paginas = length(paginas), status = "ok")
  }, error = function(e) {
    if (file.exists(destino)) file.remove(destino)
    list(texto = "", paginas = 0, status = paste0("error: ", conditionMessage(e)))
  })
}

# ── Procesar PDFs ─────────────────────────────────────────────────────────────

resultados <- list()
log_rows   <- list()
n          <- nrow(archivos_pendientes)

for (i in seq_len(n)) {
  nombre  <- archivos_pendientes$name[i]
  file_id <- archivos_pendientes$id[i]

  cat(sprintf("[%d/%d] %s\n", i, n, nombre))

  resultado   <- extraer_texto(file_id, nombre)
  doi_archivo <- doi_desde_nombre(nombre)

  meta_fila <- metadata %>%
    filter(
      tolower(trimws(doi))       == doi_archivo |
      tolower(trimws(record_id)) == doi_archivo
    ) %>%
    slice(1)

  resultados[[i]] <- tibble(
    filename         = nombre,
    doi              = if (nrow(meta_fila) > 0) meta_fila$doi[1]              else doi_archivo,
    titulo           = if (nrow(meta_fila) > 0) meta_fila$title[1]            else "",
    anio             = if (nrow(meta_fila) > 0) meta_fila$publication_year[1] else "",
    autores          = if (nrow(meta_fila) > 0) meta_fila$authors[1]          else "",
    revista          = if (nrow(meta_fila) > 0) meta_fila$origin[1]           else "",
    texto            = resultado$texto,
    paginas          = resultado$paginas,
    status           = resultado$status,
    fecha_extraccion = Sys.Date()
  ) %>% mutate(across(everything(), as.character))

  log_rows[[i]] <- tibble(
    filename = nombre,
    status   = resultado$status,
    paginas  = resultado$paginas,
    chars    = nchar(resultado$texto)
  ) %>% mutate(across(everything(), as.character))

  if (i %% 50 == 0) {
    parcial <- bind_rows(resultados[1:i])
    if (!is.null(corpus_prev)) parcial <- bind_rows(corpus_prev, parcial)
    write_csv(parcial, CORPUS_CSV)
    cat(sprintf("  → Progreso guardado (%d/%d)\n", i, n))
  }
}

# ── Guardar corpus final ──────────────────────────────────────────────────────

corpus_nuevo <- bind_rows(resultados)
corpus_final <- if (!is.null(corpus_prev)) bind_rows(corpus_prev, corpus_nuevo) else corpus_nuevo

write_csv(corpus_final, CORPUS_CSV)
write_csv(bind_rows(log_rows), LOG_FILE)

cat("\n=== Resumen ===\n")
cat(sprintf("Total en corpus:  %d\n", nrow(corpus_final)))
cat(sprintf("Exitosos (ok):    %d\n", sum(corpus_final$status == "ok")))
cat(sprintf("Vacíos:           %d\n", sum(corpus_final$status == "vacio")))
cat(sprintf("Con error:        %d\n", sum(grepl("^error", corpus_final$status))))
cat(sprintf("Tamaño:           %.1f MB\n", file.size(CORPUS_CSV) / 1024 / 1024))
cat("=== Extracción completada ===\n")
