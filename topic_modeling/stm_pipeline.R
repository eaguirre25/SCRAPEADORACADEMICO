suppressPackageStartupMessages({
  library(stm); library(readr); library(dplyr); library(stringr)
  library(tidyr); library(yaml); library(jsonlite); library(digest)
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
  run_scores <- c()
  for (i in 2:length(models)) {
    candidate <- labelTopics(models[[i]], n = top_n)$frex
    similarities <- outer(seq_len(nrow(reference)), seq_len(nrow(candidate)), Vectorize(function(a, b) {
      length(intersect(reference[a, ], candidate[b, ])) / max(length(union(reference[a, ], candidate[b, ])), 1)
    }))
    run_scores <- c(run_scores, mean(apply(similarities, 1, max), na.rm = TRUE))
  }
  mean(run_scores, na.rm = TRUE)
}

score_diagnostics <- function(diagnostics, weights) {
  definitions <- list(coherence = TRUE, exclusivity = TRUE, heldout = TRUE, residual = FALSE, stability = TRUE)
  available <- names(definitions)[vapply(names(definitions), function(name) !all(is.na(diagnostics[[name]])), logical(1))]
  raw_weights <- unlist(weights[available])
  raw_weights <- raw_weights / sum(raw_weights)
  score <- rep(0, nrow(diagnostics))
  for (name in available) score <- score + raw_weights[[name]] * normalize_metric(diagnostics[[name]], definitions[[name]])
  diagnostics$multicriteria_score <- score
  diagnostics$weights_used <- paste(paste0(names(raw_weights), "=", round(raw_weights, 4)), collapse = ";")
  diagnostics$missing_metrics <- paste(setdiff(names(definitions), available), collapse = ";")
  diagnostics
}

filter_corpus_language <- function(corpus, selected_language) {
  if (selected_language == "all") return(corpus)
  corpus %>% filter(.data$language == .env$selected_language)
}

run_stm_pipeline <- function(args = character()) {
  started <- Sys.time()
  config_path <- arg_value(args, "--config", "config/topic_modeling.yml")
  cfg <- read_yaml(config_path)
  seed <- as.integer(Sys.getenv("TOPIC_MODELING_SEED", cfg$project$seed))
  corpus_unit <- arg_value(args, "--corpus-unit", "metadata")
  language <- arg_value(args, "--language", "es")
  output_name <- arg_value(args, "--output-name", paste0(corpus_unit, "_", language))
  preliminary_only <- "--preliminary" %in% args
  fixed_k_value <- arg_value(args, "--fixed-k", NULL)
  fixed_k <- if (is.null(fixed_k_value)) NA_integer_ else as.integer(fixed_k_value)
  run_stability <- tolower(Sys.getenv("RUN_STABILITY", "false")) == "true" && !preliminary_only
  set.seed(seed)
  out <- file.path(cfg$paths$output_root, "stm", output_name)
  dir.create(out, recursive = TRUE, showWarnings = FALSE)

  corpus_path <- file.path(cfg$paths$output_root, "corpus", paste0("modeling_corpus_", corpus_unit, ".csv"))
  corpus <- read_csv(corpus_path, show_col_types = FALSE)
  corpus <- filter_corpus_language(corpus, language)
  corpus <- corpus %>% mutate(
    anio = as.integer(.data$year), titulo = .data$title,
    texto_limpio = clean_for_stm(coalesce(.data$text_for_stm, .data$text_for_modeling, .data$texto_modelado)),
    source_model = coalesce(.data$source, "unknown")
  ) %>% filter(!is.na(anio), anio >= cfg$project$start_year, anio <= cfg$project$end_year)
  if (nrow(corpus) < 20) stop("El corpus elegible es demasiado pequeño para STM")

  candidates_before <- corpus %>% transmute(
    publication_document_id, document_id, title, stage = "fulltext_candidates", reason = "eligible_input"
  )
  stops <- functional_stopwords
  if (isTRUE(cfg$stm$remove_domain_stopwords)) stops <- c(stops, domain_stopwords)
  processed <- textProcessor(corpus$texto_limpio, metadata = corpus, lowercase = TRUE,
    removestopwords = TRUE, removenumbers = TRUE, removepunctuation = TRUE, stem = FALSE,
    customstopwords = unique(stops), verbose = FALSE)
  processed_ids <- unique(processed$meta$document_id)
  removed_processor <- candidates_before %>% filter(!document_id %in% processed_ids) %>%
    mutate(stage = "textProcessor", reason = "removed_by_textProcessor")
  prep <- prepDocuments(processed$documents, processed$vocab, processed$meta, lower.thresh = 3, verbose = FALSE)
  prep_ids <- unique(prep$meta$document_id)
  removed_prep <- candidates_before %>% filter(document_id %in% processed_ids, !document_id %in% prep_ids) %>%
    mutate(stage = "prepDocuments", reason = "removed_by_prepDocuments")
  if (length(prep$documents) < 20) stop("El corpus procesado es demasiado pequeño para STM")
  write_csv(bind_rows(removed_processor, removed_prep), file.path(out, "preprocessing_exclusions.csv"))
  prep_counts <- data.frame(
    metric = c(paste0(corpus_unit, "_candidates"), paste0(corpus_unit, "_eligible"), "removed_by_cleaning",
      "removed_by_textProcessor", "removed_by_prepDocuments", paste0(corpus_unit, "_in_final_model")),
    value = c(nrow(corpus), nrow(corpus), 0, nrow(removed_processor), nrow(removed_prep), length(prep$documents))
  )
  write_csv(prep_counts, file.path(out, "preprocessing_counts.csv"))

  candidates <- as.integer(unlist(cfg$stm$coarse_k))
  candidates <- candidates[candidates < length(prep$documents)]
  prevalence_formula <- ~ splines::ns(anio, df = 3)
  resume <- "--resume-model" %in% args
  model_path <- file.path(out, "model.rds")
  diagnostics_path <- file.path(out, "k_diagnostics.csv")
  resumed <- resume && file.exists(model_path) && file.exists(diagnostics_path)
  if (resumed) {
    diagnostics <- read_csv(diagnostics_path, show_col_types = FALSE)
    K <- as.integer(diagnostics$K[1]); model <- readRDS(model_path)
    if (nrow(model$theta) != length(prep$documents)) stop("El modelo guardado no corresponde al corpus actual")
  } else if (!is.na(fixed_k)) {
    if (fixed_k < 2 || fixed_k >= length(prep$documents)) stop("--fixed-k debe ser >= 2 y menor que el número de documentos")
    K <- fixed_k
    diagnostics <- data.frame(
      K = K, coherence = NA_real_, exclusivity = NA_real_, heldout = NA_real_, residual = NA_real_,
      bound = NA_real_, stability = NA_real_, convergence_rate = NA_real_, multicriteria_score = NA_real_,
      weights_used = "", missing_metrics = "coherence;exclusivity;heldout;residual;stability", search_phase = "fixed_preliminary",
      K_preferred = TRUE, K_competitive = FALSE, K_rejected = FALSE,
      selection_status = "provisional_fixed_k", human_review_status = "pending",
      warning = "Preliminary fixed-K fit: computational K selection and stability have not been executed"
    )
    write_csv(diagnostics, diagnostics_path)
    set.seed(seed)
    model <- stm(prep$documents, prep$vocab, K = K, prevalence = prevalence_formula, data = prep$meta,
      max.em.its = as.integer(cfg$stm$max_em_iterations), init.type = cfg$stm$init_type, verbose = TRUE)
    saveRDS(model, model_path)
  } else {
    set.seed(seed)
    search <- searchK(prep$documents, prep$vocab, K = candidates, prevalence = prevalence_formula,
      data = prep$meta, verbose = TRUE, cores = 1)
    n <- length(candidates)
    diagnostics <- data.frame(
      K = candidates, coherence = safe_result(search, "semcoh", n), exclusivity = safe_result(search, "exclus", n),
      heldout = safe_result(search, "heldout", n), residual = safe_result(search, "residual", n),
      bound = safe_result(search, "bound", n), stability = NA_real_, convergence_rate = NA_real_, search_phase = "coarse"
    )
    diagnostics <- score_diagnostics(diagnostics, cfg$stm$diagnostic_weights)
    promising <- diagnostics %>% arrange(desc(multicriteria_score)) %>% slice_head(n = min(2, n())) %>% pull(K)
    offsets <- as.integer(unlist(cfg$stm$fine_offsets))
    fine_candidates <- sort(unique(as.integer(outer(promising, offsets, "+"))))
    fine_candidates <- fine_candidates[fine_candidates >= 2 & fine_candidates < length(prep$documents) & !fine_candidates %in% candidates]
    fine_search <- NULL
    if (length(fine_candidates)) {
      set.seed(seed + 1)
      fine_search <- searchK(prep$documents, prep$vocab, K = fine_candidates, prevalence = prevalence_formula,
        data = prep$meta, verbose = TRUE, cores = 1)
      nf <- length(fine_candidates)
      fine_diagnostics <- data.frame(
        K = fine_candidates, coherence = safe_result(fine_search, "semcoh", nf), exclusivity = safe_result(fine_search, "exclus", nf),
        heldout = safe_result(fine_search, "heldout", nf), residual = safe_result(fine_search, "residual", nf),
        bound = safe_result(fine_search, "bound", nf), stability = NA_real_, convergence_rate = NA_real_, search_phase = "fine"
      )
      diagnostics <- bind_rows(diagnostics %>% select(-multicriteria_score, -weights_used, -missing_metrics), fine_diagnostics)
      diagnostics <- score_diagnostics(diagnostics, cfg$stm$diagnostic_weights)
    }
    saveRDS(list(coarse = search, fine = fine_search, coarse_K = candidates, fine_K = fine_candidates), file.path(out, "k_search.rds"))
    finalists <- diagnostics %>% arrange(desc(multicriteria_score)) %>% slice_head(n = min(3, n())) %>% pull(K)
    if (run_stability) {
      runs <- as.integer(cfg$stm$stability_runs)
      for (candidate in finalists) {
        models <- lapply(seq_len(runs), function(run) {
          set.seed(seed + candidate * 100 + run)
          stm(prep$documents, prep$vocab, K = candidate, prevalence = prevalence_formula, data = prep$meta,
            max.em.its = as.integer(cfg$stm$max_em_iterations), init.type = cfg$stm$init_type, verbose = FALSE)
        })
        diagnostics$stability[diagnostics$K == candidate] <- topic_stability(models, prep$vocab)
        diagnostics$convergence_rate[diagnostics$K == candidate] <- mean(vapply(models, function(m) !is.null(m$convergence$bound), logical(1)))
      }
      diagnostics <- score_diagnostics(diagnostics, cfg$stm$diagnostic_weights)
    }
    diagnostics <- diagnostics %>% arrange(desc(multicriteria_score)) %>% mutate(
      K_preferred = row_number() == 1, K_competitive = row_number() %in% 2:3,
      K_rejected = !(K_preferred | K_competitive),
      selection_status = ifelse(run_stability, "metrics_complete", "provisional"),
      human_review_status = "pending",
      warning = ifelse(run_stability, "Human review is still required", "Stability not executed; missing weight removed and remaining weights renormalized")
    )
    write_csv(diagnostics, diagnostics_path)
    K <- diagnostics$K[1]
    set.seed(seed)
    model <- stm(prep$documents, prep$vocab, K = K, prevalence = prevalence_formula, data = prep$meta,
      max.em.its = as.integer(cfg$stm$max_em_iterations), init.type = cfg$stm$init_type, verbose = TRUE)
    saveRDS(model, model_path)
  }

  labels <- labelTopics(model, n = 20); theta <- model$theta
  dominant <- max.col(theta, ties.method = "first")
  second <- apply(theta, 1, function(x) order(x, decreasing = TRUE)[2])
  first_p <- theta[cbind(seq_len(nrow(theta)), dominant)]
  second_p <- theta[cbind(seq_len(nrow(theta)), second)]
  model_label <- paste0("STM-", toupper(corpus_unit), "-", toupper(language))
  topics <- data.frame(
    model = model_label, corpus = corpus_unit, language = language, topic_id = seq_len(K),
    topic_label = apply(labels$frex[, 1:4, drop = FALSE], 1, paste, collapse = " · "),
    automatic_label = apply(labels$frex[, 1:4, drop = FALSE], 1, paste, collapse = " · "), human_label = "",
    label_status = "pending", validation_status = "exploratory",
    selection_status = ifelse(!is.na(fixed_k), "provisional_fixed_k", ifelse(run_stability, "metrics_complete", "provisional")),
    prevalence = round(colMeans(theta) * 100, 4),
    document_count = tabulate(dominant, nbins = K),
    small_topic_warning = tabulate(dominant, nbins = K) < as.integer(cfg$stm$minimum_dominant_documents_warning),
    top_words = apply(labels$frex[, 1:15, drop = FALSE], 1, paste, collapse = " | "), top_ngrams = "",
    representative_titles = vapply(seq_len(K), function(k) paste(head(prep$meta$titulo[order(theta[, k], decreasing = TRUE)], 10), collapse = " | "), character(1)),
    coherence = "", diversity = "", stability = diagnostics$stability[match(K, diagnostics$K)], is_outlier = FALSE
  )
  write_csv(topics, file.path(out, "topics.csv"))
  write_csv(bind_rows(lapply(seq_len(K), function(k) data.frame(
    model = model_label, corpus = corpus_unit, language = language, topic_id = k,
    rank = seq_len(ncol(labels$frex)), term = labels$frex[k, ], metric = "FREX"
  ))), file.path(out, "topic_words.csv"))
  doc_topics <- data.frame(
    document_id = prep$meta$document_id, publication_document_id = prep$meta$publication_document_id,
    model = model_label, corpus = corpus_unit, language = prep$meta$language, topic_id = dominant,
    topic_probability = first_p, second_topic_id = second, second_topic_probability = second_p,
    probability_margin = first_p - second_p, is_outlier = FALSE,
    is_ambiguous = (first_p - second_p) < cfg$validation$ambiguous_probability_margin,
    year = prep$meta$anio, title = prep$meta$titulo, doi = prep$meta$doi, source = prep$meta$source_model,
    corpus_unit = corpus_unit, topic_entropy = apply(theta, 1, function(x) -sum(x * log(pmax(x, 1e-12))))
  )
  write_csv(doc_topics, file.path(out, "document_topics.csv"))

  effects <- estimateEffect(as.formula(sprintf("1:%d ~ splines::ns(anio, df = 3)", K)), model, meta = prep$meta, uncertainty = "Global")
  saveRDS(effects, file.path(out, "temporal_effects.rds"))
  effect_curve <- plot(effects, "anio", method = "continuous", topics = seq_len(K), model = model,
    npoints = 100, nsims = 100, ci.level = 0.95, omit.plot = TRUE, printlegend = FALSE)
  coverage <- read_csv(file.path(cfg$paths$output_root, "corpus", "annual_coverage.csv"), show_col_types = FALSE)
  years <- sort(unique(prep$meta$anio))
  over_time <- bind_rows(lapply(seq_len(K), function(k) bind_rows(lapply(years, function(year) {
    index <- prep$meta$anio == year; values <- theta[index, k]; n_year <- sum(index)
    dominant_count <- sum(dominant[index] == k); effective_mass <- sum(values)
    expected <- approx(effect_curve$x, effect_curve$means[[k]], xout = year, rule = 2)$y
    effect_low <- approx(effect_curve$x, effect_curve$ci[[k]][1, ], xout = year, rule = 2)$y
    effect_high <- approx(effect_curve$x, effect_curve$ci[[k]][2, ], xout = year, rule = 2)$y
    coverage_row <- coverage %>% filter(.data$year == !!year)
    data.frame(
      model = model_label, corpus = corpus_unit, language = language, topic_id = k, year = year,
      documents_in_year = n_year, dominant_topic_documents = dominant_count,
      effective_topic_mass = effective_mass, mean_prevalence = mean(values), median_prevalence = median(values),
      expected_prevalence = expected, topic_presence_above_threshold = sum(values >= 0.10),
      lower_95 = effect_low, upper_95 = effect_high, uncertainty_method = "estimateEffect_global_simulation",
      year_complete = year != cfg$project$end_year,
      metadata_coverage = ifelse(nrow(coverage_row), 1, NA),
      fulltext_coverage = ifelse(nrow(coverage_row), coverage_row$fulltext_coverage_in_year[1], NA)
    )
  }))))
  write_csv(over_time, file.path(out, "topics_over_time.csv"))

  metadata <- list(
    model = model_label, corpus = corpus_unit, language = language, seed = seed,
    generated_at_utc = format(Sys.time(), tz = "UTC"),
    git_commit = tryCatch(system("git rev-parse HEAD", intern = TRUE), error = function(e) "unknown"),
    R_version = R.version.string, packages = list(stm = as.character(packageVersion("stm"))), configuration = cfg,
    documents = length(prep$documents), input_candidates = nrow(corpus), removed_by_textProcessor = nrow(removed_processor),
    removed_by_prepDocuments = nrow(removed_prep), selected_K = K,
    selection_status = ifelse(!is.na(fixed_k), "provisional_fixed_k", ifelse(run_stability, "metrics_complete", "provisional")), human_review_status = "pending",
    year_2026_incomplete = TRUE, execution_mode = ifelse(resumed, "resume_exports", "full"),
    elapsed_seconds = as.numeric(difftime(Sys.time(), started, units = "secs"))
  )
  write_json(metadata, file.path(out, "model_metadata.json"), pretty = TRUE, auto_unbox = TRUE)
  cat(sprintf("STM preliminar completada: modelo=%s K=%d documentos=%d semilla=%d\n", model_label, K, length(prep$documents), seed))
  invisible(metadata)
}
