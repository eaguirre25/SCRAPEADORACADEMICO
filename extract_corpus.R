# extract_corpus.R
# Fase 1: Extracción de texto de PDFs desde Google Drive
# Output: data/corpus.csv con texto completo + metadatos

library(httr)
library(googledrive)
library(pdftools)
library(readr)
library(dplyr)

cat("=== Inicio de extracción de corpus ===\n")
cat("Fecha:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n\n")

# ── Autenticación con Google Drive ────────────────────────────────────────────

cat("Conectando con Google Drive...\n")

client_id     <- Sys.getenv("GOOGLE_CLIENT_ID")
client_secret <- Sys.getenv("GOOGLE_CLIENT_SECRET")
refresh_token <- Sys.getenv("GOOGLE_REFRESH_TOKEN")

# Obtener access token via httr
resp <- POST(
  "https://oauth2.googleapis.com/token",
  body = list(
    client_id     = client_id,
    client_secret = client_secret,
    refresh_token = refresh_token,
    grant_type    = "refresh_token"
  ),
  encode = "form"
)

if (http_error(resp)) {
  stop("Error al obtener access token: ", content(resp, "text"))
}

token_data   <- content(resp)
access_token <- token_data$access_token

# Construir token httr y pasárselo a googledrive
token_obj <- structure(
  list(
    app         = httr::oauth_app("google", key = client_id, secret = client_secret),
    endpoint    = httr::oauth_endpoints("google"),
    credentials = list(
      access_token  = access_token,
      token_type    = "Bearer",
      refresh_token = refresh_token,
      expires_in    = token_data$expires_in
    )
  ),
  class = c("Token2.0", "Token", "R6")
)

drive_auth(token = token_obj)
cat("Autenticación exitosa.\n\n")

# ── Rutas ─────────────────────────────────────────────────────────────────────

MASTER_CSV <- "data/master_records.csv"
CORPUS_CSV <- "data/corpus.csv"
LOG_FILE   <- "data/extraction_log.csv"
TEMP_DIR   <- tempdir()

# ── Leer metadatos ────────────────────────────────────────────────────────────

metadata <- read_csv(MASTER_CSV, show_col_types = FALSE) %>%
  mutate(across(everything(), as.character))
cat(sprintf("Metadatos cargados: %d registros\n\n", nrow(metadata)))

# ── Cargar corpus previo ──────────────────────────────────────────────────────

if (file.exists(CORPUS_CSV)) {
  corpus_prev   <- read_csv(CORPUS_CSV, show_col_types = FALSE)
  ya_procesados <- corpus_prev$filename
  cat(sprintf("Corpus previo: %d archivos ya procesados.\n\n", length(ya_procesados)))
} else {
  corpus_prev   <- NULL
  ya_procesados <- character(0)
}

# ── Listar PDFs en Drive ──────────────────────────────────────────────────────

folder_id <- Sys.getenv("DRIVE_FOLDER_ID")
cat(sprintf("Listando PDFs en carpeta: %s\n", folder_id))

archivos_drive <- drive_ls(as_id(folder_id))
archivos_drive <- archivos_drive[grepl("\\.pdf$", archivos_drive$name, ignore.case = TRUE), ]

cat(sprintf("PDFs encontrados: %d\n", nrow(archivos_drive)))

archivos_pendientes <- archivos_drive[!archivos_drive$name %in% ya_procesados, ]
cat(sprintf("PDFs pendientes:  %d\n\n", nrow(archivos_pendientes)))

# ── Funciones ─────────────────────────────────────────────────────────────────

doi_desde_nombre <- function(nombre) {
  doi <- sub("\\.pdf$", "", nombre, ignore.case = TRUE)
  doi <- sub("_", "/", doi, fixed = TRUE)
  tolower(trimws(doi))
}

extraer_texto <- function(file_id, nombre) {
  destino <- file.path(TEMP_DIR, nombre)
  tryCatch({
    drive_download(as_id(file_id), path = destino, overwrite = TRUE)
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
  )

  log_rows[[i]] <- tibble(
    filename = nombre,
    status   = resultado$status,
    paginas  = resultado$paginas,
    chars    = nchar(resultado$texto)
  )

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
