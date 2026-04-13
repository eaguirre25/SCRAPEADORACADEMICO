# stm_analysis.R
# Análisis de tópicos (STM) sobre corpus de dirección/gestión escolar
# Covariable: año de publicación
# Output: PNGs + informe HTML

library(stm)
library(readr)
library(dplyr)
library(stringr)
library(ggplot2)
library(tidyr)

cat("=== Análisis STM – Dirección/Gestión Escolar ===\n")
cat("Fecha:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n\n")

# ── Directorios de output ─────────────────────────────────────────────────────

dir.create("output/plots", recursive = TRUE, showWarnings = FALSE)

# ── Cargar corpus ─────────────────────────────────────────────────────────────

cat("Cargando corpus...\n")
corpus <- read_csv("data/corpus.csv", show_col_types = FALSE)

# Solo registros con texto extraído correctamente
corpus <- corpus %>%
  filter(status == "ok", nchar(texto) > 200) %>%
  mutate(
    anio = as.integer(anio),
    anio = ifelse(is.na(anio) | anio < 2020 | anio > 2026, NA, anio)
  ) %>%
  filter(!is.na(anio))

cat(sprintf("Documentos con texto válido: %d\n\n", nrow(corpus)))

# ── Preprocesamiento de texto ─────────────────────────────────────────────────

cat("Preprocesando texto...\n")

# Stopwords en español e inglés
stopwords_es <- c(
  "que", "de", "la", "el", "en", "y", "a", "los", "del", "se", "las",
  "por", "un", "con", "una", "su", "para", "es", "al", "lo", "como",
  "más", "pero", "sus", "le", "ya", "o", "fue", "este", "ha", "si",
  "porque", "esta", "son", "entre", "cuando", "muy", "sin", "sobre",
  "ser", "tiene", "también", "me", "hasta", "hay", "donde", "han",
  "quien", "están", "estado", "desde", "todo", "nos", "durante",
  "estados", "todos", "uno", "les", "ni", "contra", "otros", "ese",
  "eso", "ante", "ellos", "e", "esto", "mí", "antes", "algunos",
  "qué", "unos", "yo", "otro", "otras", "otra", "él", "tanto", "esa",
  "estos", "mucho", "quienes", "nada", "muchos", "cual", "poco",
  "ella", "estar", "estas", "algunas", "algo", "nosotros", "mi",
  "mis", "tú", "te", "ti", "tu", "tus", "vosotros", "vosotras",
  "os", "mío", "mía", "míos", "mías", "tuyo", "tuya", "tuyos",
  "tuyas", "suyo", "suya", "suyos", "suyas", "nuestro", "nuestra",
  "nuestros", "nuestras", "vuestro", "vuestra", "vuestros", "vuestras",
  "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
  "aquel", "aquella", "aquellos", "aquellas", "así", "aunque",
  "bien", "cada", "cual", "cuales", "cuanto", "cuanta", "era",
  "ésta", "éste", "han", "haya", "hacer", "hacia", "mismo", "puede",
  "pues", "siempre", "sólo", "también", "tanto", "tienen", "toda",
  "además", "aquí", "después", "entonces", "mientras", "mediante",
  "través", "través", "según", "bajo", "cabo", "embargo", "vez"
)

stopwords_en <- c(
  "the", "and", "for", "are", "but", "not", "you", "all", "can",
  "her", "was", "one", "our", "out", "day", "get", "has", "him",
  "his", "how", "man", "new", "now", "old", "see", "two", "way",
  "who", "boy", "did", "its", "let", "put", "say", "she", "too",
  "use", "this", "that", "with", "have", "from", "they", "will",
  "been", "than", "them", "were", "what", "when", "your", "more",
  "also", "into", "some", "time", "very", "well", "just", "know",
  "take", "year", "good", "much", "even", "most", "work", "such",
  "give", "over", "think", "here", "after", "first", "never",
  "where", "while", "these", "those", "being", "other", "which",
  "their", "there", "about", "would", "could", "should", "between",
  "through", "during", "before", "however", "therefore", "although",
  "within", "without", "across", "among", "both", "each", "either",
  "neither", "only", "same", "than", "thus", "under", "using",
  "paper", "study", "research", "analysis", "results", "data",
  "journal", "volume", "issue", "pages", "doi", "https", "www",
  "http", "com", "org", "edu", "based", "approach", "context",
  "found", "used", "may", "per", "can", "must", "also", "well"
)

custom_stopwords <- c(stopwords_es, stopwords_en,
                      # términos no informativos para STM
                      "pp", "vol", "ibid", "op", "cit", "al",
                      "et", "fig", "table", "figure", "ref")

# Procesar texto con textProcessor de STM
processed <- textProcessor(
  documents  = corpus$texto,
  metadata   = corpus,
  lowercase  = TRUE,
  removestopwords = TRUE,
  removenumbers   = TRUE,
  removepunctuation = TRUE,
  stem       = FALSE,   # sin stemming para mantener legibilidad
  customstopwords = custom_stopwords,
  verbose    = TRUE
)

# Preparar documentos (eliminar términos muy raros o muy frecuentes)
prep <- prepDocuments(
  processed$documents,
  processed$vocab,
  processed$meta,
  lower.thresh = 5,    # término debe aparecer en al menos 5 docs
  upper.thresh = round(nrow(corpus) * 0.90)  # y en menos del 90%
)

cat(sprintf("\nDocumentos finales para STM: %d\n", length(prep$documents)))
cat(sprintf("Vocabulario: %d términos\n\n", length(prep$vocab)))

# ── Selección automática de K ─────────────────────────────────────────────────

cat("Buscando K óptimo (esto puede tardar 30-60 min)...\n")

# Probar K entre 5 y 25 con incrementos de 5
k_candidatos <- c(5, 10, 15, 20, 25)

k_search <- searchK(
  prep$documents,
  prep$vocab,
  K          = k_candidatos,
  prevalence = ~ anio,
  data       = prep$meta,
  verbose    = TRUE,
  cores      = 1
)

# Guardar resultados de searchK
saveRDS(k_search, "output/k_search.rds")

# Graficar diagnósticos de K
png("output/plots/01_seleccion_K.png", width = 1200, height = 800, res = 120)
plot(k_search)
dev.off()

# Elegir K por coherencia semántica + exclusividad
k_df <- data.frame(
  K            = unlist(k_search$results$K),
  coherence    = unlist(k_search$results$semcoh),
  exclusivity  = unlist(k_search$results$exclus),
  held_out     = unlist(k_search$results$heldout)
)

# Score combinado: normalizar ambas métricas y promediar
k_df <- k_df %>%
  mutate(
    coh_norm = (coherence - min(coherence)) / (max(coherence) - min(coherence)),
    exc_norm = (exclusivity - min(exclusivity)) / (max(exclusivity) - min(exclusivity)),
    score    = (coh_norm + exc_norm) / 2
  )

K_optimo <- k_df$K[which.max(k_df$score)]
cat(sprintf("\nK óptimo seleccionado: %d\n\n", K_optimo))

# ── Modelo STM final ──────────────────────────────────────────────────────────

cat(sprintf("Ajustando modelo STM con K=%d...\n", K_optimo))

modelo_stm <- stm(
  documents  = prep$documents,
  vocab      = prep$vocab,
  K          = K_optimo,
  prevalence = ~ anio,
  data       = prep$meta,
  max.em.its = 150,
  init.type  = "Spectral",
  verbose    = TRUE
)

saveRDS(modelo_stm, "output/stm_model.rds")
cat("Modelo STM guardado.\n\n")

# ── Visualizaciones ───────────────────────────────────────────────────────────

cat("Generando visualizaciones...\n")

# 1. Prevalencia de tópicos
png("output/plots/02_prevalencia_topicos.png", width = 1400, height = 900, res = 120)
plot(modelo_stm, type = "summary", n = 10,
     main = "Prevalencia de tópicos – Dirección/Gestión Escolar (2020-2026)")
dev.off()

# 2. Palabras top por tópico (FREX = frecuencia + exclusividad)
png("output/plots/03_palabras_frex.png", width = 1600, height = 1200, res = 120)
plot(modelo_stm, type = "labels", n = 8,
     main = "Palabras más representativas por tópico (FREX)")
dev.off()

# 3. Evolución temporal de tópicos
efecto_anio <- estimateEffect(
  1:K_optimo ~ anio,
  modelo_stm,
  meta       = prep$meta,
  uncertainty = "Global"
)

# Graficar los 6 tópicos más prevalentes por año
topicos_prevalentes <- order(colMeans(modelo_stm$theta), decreasing = TRUE)[1:min(6, K_optimo)]

png("output/plots/04_evolucion_temporal.png", width = 1600, height = 1200, res = 120)
par(mfrow = c(2, 3), mar = c(4, 4, 3, 1))
for (k in topicos_prevalentes) {
  palabras_top <- labelTopics(modelo_stm, topics = k)$frex[1, 1:5]
  label_topico <- paste0("T", k, ": ", paste(palabras_top, collapse = ", "))
  plot(efecto_anio, covariate = "anio", topics = k,
       model = modelo_stm, method = "continuous",
       xlab = "Año", ylab = "Prevalencia esperada",
       main = str_wrap(label_topico, width = 40),
       cex.main = 0.8)
}
dev.off()

# ── Tabla de tópicos ──────────────────────────────────────────────────────────

cat("Generando tabla de tópicos...\n")

etiquetas <- labelTopics(modelo_stm, n = 15)

tabla_topicos <- data.frame(
  topico      = seq_len(K_optimo),
  prevalencia = round(colMeans(modelo_stm$theta) * 100, 2),
  frex_top7   = apply(etiquetas$frex[, 1:7], 1, paste, collapse = ", "),
  prob_top7   = apply(etiquetas$prob[, 1:7], 1, paste, collapse = ", ")
)
tabla_topicos <- tabla_topicos[order(-tabla_topicos$prevalencia), ]

write_csv(tabla_topicos, "output/tabla_topicos.csv")

# ── Informe HTML ──────────────────────────────────────────────────────────────

cat("Generando informe HTML...\n")

filas_topicos <- ""
for (i in seq_len(nrow(tabla_topicos))) {
  fila <- tabla_topicos[i, ]
  filas_topicos <- paste0(filas_topicos, sprintf("
    <tr>
      <td><strong>Tópico %d</strong></td>
      <td>%.1f%%</td>
      <td>%s</td>
      <td>%s</td>
    </tr>",
    fila$topico, fila$prevalencia, fila$frex_top7, fila$prob_top7
  ))
}

html <- sprintf('<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>STM – Dirección Escolar</title>
<style>
  body { font-family: Georgia, serif; max-width: 1100px; margin: 40px auto; padding: 0 20px; color: #222; background: #fafafa; }
  h1 { color: #1a3a5c; border-bottom: 3px solid #1a3a5c; padding-bottom: 10px; }
  h2 { color: #2c5f8a; margin-top: 40px; }
  .meta { color: #666; font-size: 0.9em; margin-bottom: 30px; }
  .kpi { display: flex; gap: 20px; margin: 20px 0; flex-wrap: wrap; }
  .kpi-box { background: #1a3a5c; color: white; padding: 15px 25px; border-radius: 8px; text-align: center; min-width: 150px; }
  .kpi-num { font-size: 2em; font-weight: bold; }
  .kpi-label { font-size: 0.85em; opacity: 0.85; }
  table { width: 100%%; border-collapse: collapse; margin: 20px 0; font-size: 0.9em; }
  th { background: #1a3a5c; color: white; padding: 10px 12px; text-align: left; }
  td { padding: 9px 12px; border-bottom: 1px solid #ddd; vertical-align: top; }
  tr:hover { background: #f0f5fa; }
  .plot-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin: 20px 0; }
  .plot-box { background: white; border: 1px solid #ddd; border-radius: 8px; padding: 15px; }
  .plot-box img { width: 100%%; border-radius: 4px; }
  .plot-box h3 { margin: 10px 0 5px; font-size: 1em; color: #1a3a5c; }
  .note { background: #e8f0f8; border-left: 4px solid #2c5f8a; padding: 12px 16px; margin: 20px 0; border-radius: 0 6px 6px 0; font-size: 0.9em; }
  footer { margin-top: 60px; color: #999; font-size: 0.8em; border-top: 1px solid #ddd; padding-top: 15px; }
</style>
</head>
<body>

<h1>Análisis de Tópicos (STM)<br><small>Literatura sobre Dirección y Gestión Escolar</small></h1>
<p class="meta">Generado automáticamente · %s · Período: 2020–2026</p>

<div class="kpi">
  <div class="kpi-box"><div class="kpi-num">%d</div><div class="kpi-label">Artículos analizados</div></div>
  <div class="kpi-box"><div class="kpi-num">%d</div><div class="kpi-label">Tópicos identificados</div></div>
  <div class="kpi-box"><div class="kpi-num">%d</div><div class="kpi-label">Términos en vocabulario</div></div>
  <div class="kpi-box"><div class="kpi-num">2020–2026</div><div class="kpi-label">Período cubierto</div></div>
</div>

<div class="note">
  <strong>Metodología:</strong> Structural Topic Model (STM) con selección automática de K mediante búsqueda en grilla (K=%d).
  Covariable de prevalencia: año de publicación. Preprocesamiento: eliminación de stopwords en español e inglés,
  términos con frecuencia &lt;5 documentos y &gt;90%% de documentos. Palabras representativas calculadas por métrica FREX
  (frecuencia ponderada por exclusividad).
</div>

<h2>Tópicos identificados</h2>
<table>
  <tr>
    <th>Tópico</th>
    <th>Prevalencia</th>
    <th>Palabras FREX (frecuencia × exclusividad)</th>
    <th>Palabras más frecuentes</th>
  </tr>
  %s
</table>

<h2>Visualizaciones</h2>
<div class="plot-grid">
  <div class="plot-box">
    <img src="plots/01_seleccion_K.png" alt="Selección de K">
    <h3>Diagnósticos para selección de K</h3>
  </div>
  <div class="plot-box">
    <img src="plots/02_prevalencia_topicos.png" alt="Prevalencia de tópicos">
    <h3>Prevalencia de tópicos en el corpus</h3>
  </div>
  <div class="plot-box">
    <img src="plots/03_palabras_frex.png" alt="Palabras FREX">
    <h3>Palabras más representativas por tópico</h3>
  </div>
  <div class="plot-box">
    <img src="plots/04_evolucion_temporal.png" alt="Evolución temporal">
    <h3>Evolución temporal de tópicos principales</h3>
  </div>
</div>

<h2>Notas metodológicas</h2>
<p>El modelo STM permite identificar temas latentes en un corpus de textos y estimar cómo varía
su prevalencia según covariables (en este caso, el año de publicación). A diferencia del LDA clásico,
el STM incorpora información de metadatos directamente en el proceso de estimación.</p>
<p>Las palabras <strong>FREX</strong> combinan frecuencia y exclusividad: privilegian términos que son
frecuentes <em>en</em> el tópico pero poco frecuentes en los demás, lo que las hace más informativas
para la interpretación sustantiva.</p>
<p>La selección de K=<strong>%d</strong> se realizó comparando coherencia semántica y exclusividad
en una grilla de K ∈ {5, 10, 15, 20, 25}.</p>

<footer>
  Generado por GitHub Actions · extract_corpus.R + stm_analysis.R ·
  Corpus: PDFs en acceso abierto indexados en OpenAlex (2020–2026)
</footer>

</body>
</html>',
  format(Sys.Date(), "%%d/%%m/%%Y"),
  nrow(corpus),
  K_optimo,
  length(prep$vocab),
  K_optimo,
  filas_topicos,
  K_optimo
)

writeLines(html, "output/informe_stm.html")

cat("\n=== Análisis completado ===\n")
cat(sprintf("K óptimo: %d tópicos\n", K_optimo))
cat(sprintf("Archivos generados en output/:\n"))
cat("  - informe_stm.html\n")
cat("  - tabla_topicos.csv\n")
cat("  - stm_model.rds\n")
cat("  - plots/01_seleccion_K.png\n")
cat("  - plots/02_prevalencia_topicos.png\n")
cat("  - plots/03_palabras_frex.png\n")
cat("  - plots/04_evolucion_temporal.png\n")
