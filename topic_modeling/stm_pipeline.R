suppressPackageStartupMessages({
  library(stm); library(readr); library(dplyr); library(stringr)
  library(tidyr); library(ggplot2); library(yaml); library(jsonlite); library(digest)
})

arg_value <- function(args, name, default = NULL) {
  hit <- which(args == name)
  if (length(hit) && hit[1] < length(args)) args[hit[1] + 1] else default
}

normalize_metric <- function(x, higher_is_better = TRUE) {
  x <- as.numeric(x)
  if (all(is.na(x)) || diff(range(x, na.rm = TRUE)) == 0) return(rep(0.5, length(x)))
  z <- (x - min(x, na.rm = TRUE)) / diff(range(x, na.rm = TRUE))
  z[is.na(z)] <- 0
  if (higher_is_better) z else 1 - z
}

stable_document_id <- function(doi, record_id, title, year, author, filename) {
  clean_doi <- str_to_lower(str_remove(str_trim(ifelse(is.na(doi), "", doi)), "^https?://(dx\\.)?doi\\.org/"))
  if (nzchar(clean_doi)) return(paste0("doi:", clean_doi))
  if (!is.na(record_id) && nzchar(str_trim(record_id))) return(paste0("record:", str_trim(record_id)))
  basis <- paste(str_to_lower(str_squish(title)), year, str_to_lower(author), sep = "|")
  if (!nzchar(str_remove_all(basis, "[| ]"))) basis <- paste(filename, title, sep = "|")
  paste0("hash:", digest(basis, algo = "sha256", serialize = FALSE))
}

functional_stopwords <- c(
  "que","de","la","el","en","y","a","los","del","se","las","por","un","con","una","para","es",
  "the","and","for","are","this","that","with","from","they","their","about","which","between",
  "da","do","dos","das","em","uma","não","com","pela","para","como","onde","quando",
  "dan","yang","untuk","dengan","dalam","pada","dari","ini","itu","oleh","tidak","sebagai",
  "doi","issn","isbn","pp","vol","journal","revista","article","study","research"
)

domain_stopwords <- c(
  "school","schools","education","educational","educación","educativa","liderazgo","leadership",
  "management","gestión","gestion","escolar","escuela","dirección","direccion","director","principal",
  "teacher","teachers","docente","docentes","student","students","educação","gestão","escola"
)

clean_for_stm <- function(text) {
  text %>% str_remove_all("https?://\\S+|www\\.\\S+") %>%
    str_remove_all("(?i)10\\.\\d{4,9}/[-._;()/:A-Z0-9]+") %>%
    str_remove_all("(?i)creative\\s+commons|copyright|oai-pmh|issn[-: ]*\\d{4}-?\\d{3}[0-9xX]") %>%
    str_replace_all("[[:cntrl:]]", " ") %>% str_squish()
}

safe_result <- function(search, field, n) {
  value <- tryCatch(unlist(search$results[[field]]), error = function(e) rep(NA_real_, n))
  if (length(value) < n) value <- c(value, rep(NA_real_, n - length(value)))
  as.numeric(value[seq_len(n)])
}

topic_stability <- function(models, vocab, top_n = 15) {
  if (length(models) < 2) return(NA_real_)
  reference <- labelTopics(models[[1]], n = top_n)$frex
  scores <- c()
  for (i in 2:length(models)) {
    candidate <- labelTopics(models[[i]], n = top_n)$frex
    for (k in seq_len(min(nrow(reference), nrow(candidate)))) {
      scores <- c(scores, length(intersect(reference[k, ], candidate[k, ])) / length(union(reference[k, ], candidate[k, ])))
    }
  }
  mean(scores, na.rm = TRUE)
}

run_stm_pipeline <- function(args = character()) {
  started <- Sys.time()
  config_path <- arg_value(args, "--config", "config/topic_modeling.yml")
  cfg <- read_yaml(config_path)
  seed <- as.integer(Sys.getenv("TOPIC_MODELING_SEED", cfg$project$seed))
  set.seed(seed)
  out <- file.path(cfg$paths$output_root, "stm")
  dir.create(out, recursive = TRUE, showWarnings = FALSE)
  dir.create("output/plots", recursive = TRUE, showWarnings = FALSE)

  corpus <- read_csv(cfg$paths$corpus_pdf, show_col_types = FALSE) %>%
    filter(status == "ok", nchar(texto) >= cfg$corpus$minimum_characters) %>%
    mutate(anio = as.integer(anio)) %>%
    filter(!is.na(anio), anio >= cfg$project$start_year, anio <= cfg$project$end_year) %>%
    mutate(
      document_id = mapply(stable_document_id, doi, NA_character_, titulo, anio, autores, filename),
      texto_limpio = clean_for_stm(texto)
    )
  if (!nrow(corpus)) stop("No hay documentos válidos para STM")

  stops <- functional_stopwords
  if (isTRUE(cfg$stm$remove_domain_stopwords)) stops <- c(stops, domain_stopwords)
  processed <- textProcessor(corpus$texto_limpio, metadata = corpus, lowercase = TRUE,
    removestopwords = TRUE, removenumbers = TRUE, removepunctuation = TRUE, stem = FALSE,
    customstopwords = unique(stops), verbose = FALSE)
  prep <- prepDocuments(processed$documents, processed$vocab, processed$meta, lower.thresh = 3, verbose = FALSE)
  if (length(prep$documents) < 20) stop("El corpus procesado es demasiado pequeño para STM")

  k_cfg <- cfg$stm$candidate_k
  candidates <- seq(as.integer(k_cfg$start), as.integer(k_cfg$end), by = as.integer(k_cfg$step))
  candidates <- candidates[candidates < length(prep$documents)]
  prevalence_formula <- ~ splines::ns(anio, df = 3)
  resume <- "--resume-model" %in% args
  model_path <- file.path(out, "model.rds")
  diagnostics_path <- file.path(out, "k_diagnostics.csv")
  resumed <- resume && file.exists(model_path) && file.exists(diagnostics_path)
  if (resumed) {
    cat("Reanudando exportaciones desde el modelo STM guardado.\n")
    diagnostics <- read_csv(diagnostics_path, show_col_types = FALSE)
    K <- as.integer(diagnostics$K[1])
    model <- readRDS(model_path)
    if (nrow(model$theta) != length(prep$documents)) stop("El modelo guardado no corresponde al corpus procesado actual")
    saveRDS(model, "output/stm_model.rds")
  } else {
    set.seed(seed)
    search <- searchK(prep$documents, prep$vocab, K = candidates, prevalence = prevalence_formula,
      data = prep$meta, verbose = TRUE, cores = 1)
    saveRDS(search, file.path(out, "k_search.rds"))

    n <- length(candidates)
    diagnostics <- data.frame(
      K = candidates, coherence = safe_result(search, "semcoh", n), exclusivity = safe_result(search, "exclus", n),
      heldout = safe_result(search, "heldout", n), residual = safe_result(search, "residual", n),
      bound = safe_result(search, "bound", n), stability = NA_real_, convergence_rate = NA_real_
    )
    run_stability <- tolower(Sys.getenv("RUN_STABILITY", "false")) == "true"
    if (run_stability) {
      runs <- as.integer(cfg$stm$number_of_runs)
      for (i in seq_along(candidates)) {
        models <- lapply(seq_len(runs), function(run) {
          set.seed(seed + i * 100 + run)
          stm(prep$documents, prep$vocab, K = candidates[i], prevalence = prevalence_formula, data = prep$meta,
            max.em.its = as.integer(cfg$stm$max_em_iterations), init.type = cfg$stm$init_type, verbose = FALSE)
        })
        diagnostics$stability[i] <- topic_stability(models, prep$vocab)
        diagnostics$convergence_rate[i] <- mean(vapply(models, function(m) !is.null(m$convergence$bound), logical(1)))
      }
    }
    w <- cfg$stm$diagnostic_weights
    stability_score <- ifelse(is.na(diagnostics$stability), 0.5, diagnostics$stability)
    diagnostics$multicriteria_score <-
      w$coherence * normalize_metric(diagnostics$coherence) +
      w$exclusivity * normalize_metric(diagnostics$exclusivity) +
      w$heldout * normalize_metric(diagnostics$heldout) +
      w$residual * normalize_metric(diagnostics$residual, FALSE) +
      w$stability * stability_score
    diagnostics <- diagnostics %>% arrange(desc(multicriteria_score)) %>%
      mutate(K_recomendado = row_number() == 1, K_alternativo = row_number() %in% 2:3,
        justificacion = ifelse(K_recomendado, "Mayor puntaje multicriterio configurable", "Solución comparativa"),
        advertencias = ifelse(run_stability, "", "Estabilidad no ejecutada; activar RUN_STABILITY=true"))
    write_csv(diagnostics, diagnostics_path)
    K <- diagnostics$K[1]

    set.seed(seed)
    model <- stm(prep$documents, prep$vocab, K = K, prevalence = prevalence_formula, data = prep$meta,
      max.em.its = as.integer(cfg$stm$max_em_iterations), init.type = cfg$stm$init_type, verbose = TRUE)
    saveRDS(model, model_path); saveRDS(model, "output/stm_model.rds")
  }
  labels <- labelTopics(model, n = 20)
  theta <- model$theta
  dominant <- max.col(theta, ties.method = "first")
  second <- apply(theta, 1, function(x) order(x, decreasing = TRUE)[2])
  first_p <- theta[cbind(seq_len(nrow(theta)), dominant)]
  second_p <- theta[cbind(seq_len(nrow(theta)), second)]

  topics <- data.frame(
    model = "stm", topic_id = seq_len(K), topic_label = apply(labels$frex[, 1:4, drop = FALSE], 1, paste, collapse = " · "),
    automatic_label = apply(labels$frex[, 1:4, drop = FALSE], 1, paste, collapse = " · "), human_label = "",
    label_status = "pending", prevalence = round(colMeans(theta) * 100, 4), document_count = tabulate(dominant, nbins = K),
    top_words = apply(labels$frex[, 1:15, drop = FALSE], 1, paste, collapse = " | "), top_ngrams = "",
    representative_titles = vapply(seq_len(K), function(k) paste(head(prep$meta$titulo[order(theta[, k], decreasing = TRUE)], 5), collapse = " | "), character(1)),
    coherence = "", diversity = "", stability = diagnostics$stability[match(K, diagnostics$K)], is_outlier = FALSE
  )
  write_csv(topics, file.path(out, "topics.csv"))
  words <- bind_rows(lapply(seq_len(K), function(k) data.frame(
    model = "stm", topic_id = k, rank = seq_len(ncol(labels$frex)), term = labels$frex[k, ], metric = "FREX"
  )))
  write_csv(words, file.path(out, "topic_words.csv"))
  doc_topics <- data.frame(
    document_id = prep$meta$document_id, model = "stm", topic_id = dominant, topic_probability = first_p,
    second_topic_id = second, second_topic_probability = second_p, probability_margin = first_p - second_p,
    is_outlier = FALSE, is_ambiguous = (first_p - second_p) < cfg$validation$ambiguous_probability_margin,
    year = prep$meta$anio, language = "", title = prep$meta$titulo, doi = prep$meta$doi, source = "PDF",
    corpus_unit = "full_text", topic_entropy = apply(theta, 1, function(x) -sum(x * log(pmax(x, 1e-12))))
  )
  write_csv(doc_topics, file.path(out, "document_topics.csv"))

  years <- sort(unique(prep$meta$anio))
  over_time <- bind_rows(lapply(seq_len(K), function(k) bind_rows(lapply(years, function(year) {
    values <- theta[prep$meta$anio == year, k]
    data.frame(model = "stm", topic_id = k, year = year, document_count = length(values), documents_in_year = length(values),
      mean_probability_or_prevalence = mean(values), ci95_low = max(0, mean(values) - 1.96 * sd(values) / sqrt(length(values))),
      ci95_high = min(1, mean(values) + 1.96 * sd(values) / sqrt(length(values))), coverage_in_year = 1,
      outlier_percentage = 0, year_complete = year != cfg$project$end_year)
  }))))
  write_csv(over_time, file.path(out, "topics_over_time.csv"))
  effect_formula <- as.formula(sprintf("1:%d ~ splines::ns(anio, df = 3)", K))
  effects_path <- file.path(out, "temporal_effects.rds")
  if (!(resumed && file.exists(effects_path))) {
    effects <- estimateEffect(effect_formula, model, meta = prep$meta, uncertainty = "Global")
    saveRDS(effects, effects_path)
  }

  topic_palette <- c(
    "#E63946", "#F4A261", "#2A9D8F", "#457B9D", "#A8DADC", "#E9C46A", "#264653", "#F77F00",
    "#6A4C93", "#1982C4", "#8AC926", "#FF595E", "#FFCA3A", "#7B2D8B", "#0077B6", "#52B788",
    "#D62828", "#023E8A", "#F3722C", "#90BE6D", "#43AA8B", "#577590", "#F9C74F", "#F8961E"
  )
  legacy_topics <- topics %>% transmute(topico = topic_id, prevalencia = prevalence, frex_top10 = str_replace_all(top_words, " \\| ", ", "),
    prob_top10 = apply(labels$prob[, 1:10, drop = FALSE], 1, paste, collapse = ", "),
    lift_top5 = apply(labels$lift[, 1:5, drop = FALSE], 1, paste, collapse = ", "),
    color = topic_palette[((topic_id - 1) %% length(topic_palette)) + 1])
  write_csv(legacy_topics, "output/tabla_topicos.csv")
  write_csv(data.frame(doc_index = seq_len(nrow(prep$meta)), filename = prep$meta$filename, doi = prep$meta$doi,
    titulo = prep$meta$titulo, topico_dominante = dominant), "output/document_topics.csv")

  metadata <- list(model = "stm", seed = seed, generated_at_utc = format(Sys.time(), tz = "UTC"),
    git_commit = tryCatch(system("git rev-parse HEAD", intern = TRUE), error = function(e) "unknown"),
    R_version = R.version.string, packages = list(stm = as.character(packageVersion("stm"))), configuration = cfg,
    documents = length(prep$documents), discarded_documents = nrow(corpus) - length(prep$documents), selected_K = K,
    year_2026_incomplete = TRUE, execution_mode = ifelse(resumed, "resume_exports", "full"),
    model_completed_at = format(file.info(model_path)$mtime, tz = "UTC"),
    elapsed_seconds = as.numeric(difftime(Sys.time(), started, units = "secs")))
  write_json(metadata, file.path(out, "model_metadata.json"), pretty = TRUE, auto_unbox = TRUE)
  cat(sprintf("STM completada: K=%d, documentos=%d, semilla=%d\n", K, length(prep$documents), seed))
  invisible(metadata)
}
