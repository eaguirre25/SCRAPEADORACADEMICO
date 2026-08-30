# Genera un manifiesto de los PDFs ya guardados en Google Drive.
# No descarga archivos: solo lista ID, nombre y URL de vista previa.

library(httr)
library(readr)
library(dplyr)

cat("=== Generando manifiesto de Google Drive ===\n")

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
headers <- add_headers(Authorization = paste("Bearer", access_token))
folder_id <- Sys.getenv("DRIVE_FOLDER_ID")

all_files <- list()
page_token <- NULL
repeat {
  params <- list(
    q = sprintf("'%s' in parents and trashed=false and mimeType='application/pdf'", folder_id),
    fields = "nextPageToken,files(id,name,size,modifiedTime,webViewLink)",
    pageSize = 1000
  )
  if (!is.null(page_token)) params$pageToken <- page_token
  r <- GET("https://www.googleapis.com/drive/v3/files", headers, query=params)
  stop_for_status(r)
  dat <- content(r)
  all_files <- c(all_files, dat$files)
  page_token <- dat$nextPageToken
  if (is.null(page_token)) break
}

getv <- function(x, name) if (is.null(x[[name]])) "" else as.character(x[[name]])
doi_from_name <- function(nombre) {
  doi <- sub("\\.pdf$", "", nombre, ignore.case=TRUE)
  doi <- sub("_", "/", doi, fixed=TRUE)
  tolower(trimws(doi))
}

manifest <- tibble(
  drive_file_id = sapply(all_files, getv, name="id"),
  filename = sapply(all_files, getv, name="name"),
  size = sapply(all_files, getv, name="size"),
  modified_time = sapply(all_files, getv, name="modifiedTime"),
  web_view_link = sapply(all_files, getv, name="webViewLink")
) %>%
  mutate(
    doi = vapply(filename, doi_from_name, character(1)),
    preview_url = ifelse(drive_file_id != "", paste0("https://drive.google.com/file/d/", drive_file_id, "/preview"), ""),
    open_url = ifelse(drive_file_id != "", paste0("https://drive.google.com/file/d/", drive_file_id, "/view"), web_view_link)
  )

dir.create("data", showWarnings=FALSE)
write_csv(manifest, "data/drive_manifest.csv")
cat(sprintf("PDFs indexados en Drive: %d\n", nrow(manifest)))
