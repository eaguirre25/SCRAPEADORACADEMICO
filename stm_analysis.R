# stm_analysis.R
# Análisis STM inductivo – Dirección/Gestión Escolar
# Tópicos emergen libremente del corpus.
# Visualizaciones creativas con ggplot2.

library(stm)
library(readr)
library(dplyr)
library(stringr)
library(ggplot2)
library(tidyr)

cat("=== Análisis STM Inductivo – Dirección/Gestión Escolar ===\n")
cat("Fecha:", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), "\n\n")

dir.create("output/plots", recursive = TRUE, showWarnings = FALSE)

# ── Paleta de colores ─────────────────────────────────────────────────────────

PALETA <- c(
  "#E63946","#F4A261","#2A9D8F","#457B9D","#A8DADC",
  "#E9C46A","#264653","#F77F00","#6A4C93","#1982C4",
  "#8AC926","#FF595E","#FFCA3A","#6A4C93","#1982C4",
  "#52B788","#D62828","#023E8A","#F3722C","#90BE6D",
  "#43AA8B","#577590","#F9C74F","#F8961E","#277DA1",
  "#C77DFF","#FF6B6B","#4ECDC4","#FFE66D","#A8E6CF"
)

tema_stm <- theme_minimal(base_size = 13) +
  theme(
    plot.background  = element_rect(fill = "#0D1117", color = NA),
    panel.background = element_rect(fill = "#0D1117", color = NA),
    panel.grid.major = element_line(color = "#1E2A38", linewidth = 0.4),
    panel.grid.minor = element_blank(),
    plot.title       = element_text(color = "#E6EDF3", face = "bold", size = 16, hjust = 0.5, margin = margin(b = 8)),
    plot.subtitle    = element_text(color = "#8B949E", size = 11, hjust = 0.5, margin = margin(b = 16)),
    plot.caption     = element_text(color = "#484F58", size = 9),
    axis.text        = element_text(color = "#8B949E"),
    axis.title       = element_text(color = "#C9D1D9"),
    legend.background = element_rect(fill = "#161B22", color = NA),
    legend.text      = element_text(color = "#C9D1D9"),
    legend.title     = element_text(color = "#E6EDF3"),
    strip.text       = element_text(color = "#E6EDF3", face = "bold"),
    plot.margin      = margin(20, 20, 20, 20)
  )

# ── Cargar corpus ─────────────────────────────────────────────────────────────

cat("Cargando corpus...\n")
corpus <- read_csv("data/corpus.csv", show_col_types = FALSE) %>%
  filter(status == "ok", nchar(texto) > 200) %>%
  mutate(anio = as.integer(anio)) %>%
  filter(!is.na(anio), anio >= 2020, anio <= 2026)

cat(sprintf("Documentos válidos: %d\n\n", nrow(corpus)))

# ── Stopwords ─────────────────────────────────────────────────────────────────
# Solo funcionales + términos del dominio omnipresentes (no discriminan)

stopwords_funcion <- c(
  # Español funcional
  "que","de","la","el","en","y","a","los","del","se","las","por","un",
  "con","una","su","para","es","al","lo","como","más","pero","sus","le",
  "ya","o","fue","este","ha","si","porque","esta","son","entre","cuando",
  "muy","sin","sobre","ser","tiene","también","me","hasta","hay","donde",
  "han","quien","están","estado","desde","todo","nos","durante","todos",
  "uno","les","ni","contra","otros","ese","eso","ante","ellos","e","esto",
  "antes","algunos","unos","yo","otro","otras","otra","él","tanto","esa",
  "estos","mucho","quienes","nada","muchos","cual","poco","ella","estar",
  "estas","algunas","algo","nosotros","mi","mis","así","aunque","bien",
  "cada","era","han","haya","mismo","puede","pues","siempre","sólo",
  "tienen","toda","además","aquí","después","entonces","mientras",
  "mediante","través","según","bajo","embargo","vez","sido","siendo",
  "tenido","teniendo","habido","habiendo","hecho","haciendo","dicho",
  # Portugués funcional
  "que","da","do","dos","das","em","a","o","os","as","um","uma","por",
  "com","na","no","nas","nos","ao","às","pelo","pela","pelos","pelas",
  "seu","sua","seus","suas","não","mais","mas","ou","nem","já","ainda",
  "também","só","muito","bem","foi","era","são","tem","há","ser","ter",
  "fazer","estar","poder","dever","ir","ver","dar","saber","vir",
  # Inglés funcional
  "the","and","for","are","but","not","you","all","can","her","was","one",
  "our","out","has","him","his","how","new","now","see","two","way","who",
  "did","its","let","put","say","she","too","use","this","that","with",
  "have","from","they","will","been","than","them","were","what","when",
  "your","more","also","into","some","time","very","well","just","know",
  "take","year","good","much","even","most","such","give","over","think",
  "here","after","first","never","where","while","these","those","being",
  "other","which","their","there","about","would","could","should",
  "between","through","during","before","however","therefore","although",
  "within","without","across","among","both","each","either","neither",
  "only","same","thus","under","using","may","per","must","upon",
  # Indonesio/Malayo funcional
  "dan","yang","untuk","dengan","dalam","pada","dari","ini","itu","atau",
  "oleh","akan","juga","tidak","ada","telah","dapat","lebih","sebagai",
  "bahwa","tersebut","secara","serta","para","kepada","karena","namun",
  "antara","setiap","hal","bagi","melalui","pula","seperti","hasil",
  # Dominio omnipresente (aparece en +80% de documentos — no discrimina)
  "school","schools","education","educational","educación","educativa",
  "educativo","educativas","educativos","leadership","liderazgo",
  "management","gestión","gestion","escolar","escuela","escuelas",
  "dirección","direccion","director","directora","directores",
  "principal","principals","teaching","learning","aprendizaje",
  "enseñanza","teachers","teacher","docente","docentes","estudiantes",
  "students","student","academic","académico","académica","schooling",
  "administrative","administración","administrator","administrators",
  "pendidikan","sekolah","siswa","guru","kinerja","kepala",
  "educação","gestão","escola","ensino","escolar",
  # Ruido bibliográfico
  "pp","vol","ibid","op","cit","et","al","fig","table","figure","ref",
  "http","https","www","doi","com","org","edu","isbn","issn",
  "journal","revista","review","international","nacional","national",
  "research","estudio","study","studies","analysis","paper","trabajo",
  "article","artículo","conclusion","conclusions","introduction",
  "discussion","findings","methodology","methods","results","data",
  "sample","participants","survey","questionnaire","interview",
  "qualitative","quantitative","mixed","framework","model","theory",
  "theoretical","empirical","literature","based","approach","context",
  "found","used","using","also","well","across","within","related",
  "show","shows","showed","indicate","indicates","suggest","suggests"
)

# ── Preprocesamiento ──────────────────────────────────────────────────────────

cat("Preprocesando texto (modo inductivo)...\n")

processed <- textProcessor(
  documents         = corpus$texto,
  metadata          = corpus,
  lowercase         = TRUE,
  removestopwords   = TRUE,
  removenumbers     = TRUE,
  removepunctuation = TRUE,
  stem              = FALSE,
  customstopwords   = stopwords_funcion,
  verbose           = FALSE
)

prep <- prepDocuments(
  processed$documents,
  processed$vocab,
  processed$meta,
  lower.thresh = 3,
  verbose      = FALSE
)

cat(sprintf("Documentos para STM: %d\n", length(prep$documents)))
cat(sprintf("Vocabulario: %d términos\n\n", length(prep$vocab)))

# ── Búsqueda de K ─────────────────────────────────────────────────────────────

cat("Buscando K óptimo (K ∈ {10, 15, 20, 25, 30})...\n\n")

k_search <- searchK(
  prep$documents,
  prep$vocab,
  K          = c(10, 15, 20, 25, 30),
  prevalence = ~ anio,
  data       = prep$meta,
  verbose    = TRUE,
  cores      = 1
)

saveRDS(k_search, "output/k_search.rds")

# Gráfico de diagnóstico de K — estilo oscuro
k_df <- data.frame(
  K           = unlist(k_search$results$K),
  coherence   = unlist(k_search$results$semcoh),
  exclusivity = unlist(k_search$results$exclus),
  heldout     = unlist(k_search$results$heldout)
) %>%
  mutate(
    coh_norm = (coherence   - min(coherence))   / (max(coherence)   - min(coherence)),
    exc_norm = (exclusivity - min(exclusivity)) / (max(exclusivity) - min(exclusivity)),
    score    = (coh_norm + exc_norm) / 2
  )

K_optimo <- k_df$K[which.max(k_df$score)]
cat(sprintf("\nK óptimo: %d\n\n", K_optimo))

p_k <- k_df %>%
  pivot_longer(c(coherence, exclusivity, heldout), names_to = "metrica", values_to = "valor") %>%
  mutate(metrica = recode(metrica,
    coherence   = "Coherencia semántica",
    exclusivity = "Exclusividad",
    heldout     = "Held-out likelihood"
  )) %>%
  ggplot(aes(x = K, y = valor, color = metrica, group = metrica)) +
  geom_line(linewidth = 1.2) +
  geom_point(size = 3) +
  geom_vline(xintercept = K_optimo, color = "#FFD700", linetype = "dashed", linewidth = 0.8) +
  annotate("text", x = K_optimo + 0.4, y = -Inf, vjust = -0.5,
           label = paste("K óptimo =", K_optimo), color = "#FFD700", size = 4) +
  scale_color_manual(values = c("#E63946","#2A9D8F","#F4A261")) +
  facet_wrap(~ metrica, scales = "free_y", ncol = 3) +
  labs(title = "Selección del número de tópicos (K)",
       subtitle = "Comparación de métricas de diagnóstico",
       x = "Número de tópicos (K)", y = NULL, color = NULL) +
  tema_stm +
  theme(legend.position = "none")

ggsave("output/plots/01_seleccion_K.png", p_k,
       width = 14, height = 5, dpi = 150, bg = "#0D1117")

# ── Modelo STM ────────────────────────────────────────────────────────────────

cat(sprintf("Ajustando STM con K=%d...\n", K_optimo))

modelo_stm <- stm(
  documents  = prep$documents,
  vocab      = prep$vocab,
  K          = K_optimo,
  prevalence = ~ anio,
  data       = prep$meta,
  max.em.its = 200,
  init.type  = "Spectral",
  verbose    = TRUE
)

saveRDS(modelo_stm, "output/stm_model.rds")

# ── Visualización 2: Prevalencia (lollipop horizontal) ────────────────────────

etiq <- labelTopics(modelo_stm, n = 7)
frex_labels <- apply(etiq$frex[, 1:5], 1, paste, collapse = " · ")

prev_df <- data.frame(
  topico      = paste0("T", seq_len(K_optimo)),
  prevalencia = colMeans(modelo_stm$theta) * 100,
  palabras    = frex_labels,
  color       = PALETA[seq_len(K_optimo)]
) %>%
  arrange(desc(prevalencia)) %>%
  mutate(topico = factor(topico, levels = rev(topico)))

p_prev <- ggplot(prev_df, aes(x = prevalencia, y = topico)) +
  geom_segment(aes(x = 0, xend = prevalencia, y = topico, yend = topico),
               color = "#1E2A38", linewidth = 3) +
  geom_point(aes(color = color), size = 5) +
  geom_text(aes(label = palabras, color = color),
            hjust = -0.08, size = 3.2, fontface = "italic") +
  scale_color_identity() +
  scale_x_continuous(expand = expansion(mult = c(0, 0.55)),
                     labels = function(x) paste0(round(x, 1), "%")) +
  labs(
    title    = "Prevalencia de tópicos emergentes",
    subtitle = sprintf("Corpus de dirección/gestión escolar 2020–2026 · K=%d · n=%d documentos",
                       K_optimo, nrow(corpus)),
    x = "Prevalencia esperada (%)", y = NULL,
    caption  = "Palabras clave: métrica FREX (frecuencia × exclusividad)"
  ) +
  tema_stm

ggsave("output/plots/02_prevalencia_topicos.png", p_prev,
       width = 15, height = max(8, K_optimo * 0.55), dpi = 150, bg = "#0D1117")

# ── Visualización 3: Burbuja de palabras por tópico ──────────────────────────

etiq10 <- labelTopics(modelo_stm, n = 10)
palabras_df <- do.call(rbind, lapply(seq_len(K_optimo), function(k) {
  data.frame(
    topico  = paste0("T", k),
    palabra = etiq10$frex[k, ],
    rank    = seq_len(10),
    color   = PALETA[k],
    stringsAsFactors = FALSE
  )
})) %>%
  mutate(
    size  = (11 - rank) / 10,
    alpha = 0.4 + size * 0.5
  )

n_cols_wrap <- ceiling(sqrt(K_optimo))

p_words <- ggplot(palabras_df, aes(x = rank, y = 1)) +
  geom_point(aes(size = size * 8, color = color, alpha = alpha), shape = 16) +
  geom_text(aes(label = palabra, color = color, size = size * 3.5),
            vjust = 0.5, fontface = "bold", show.legend = FALSE) +
  scale_color_identity() +
  scale_alpha_identity() +
  scale_size_identity() +
  facet_wrap(~ topico, ncol = n_cols_wrap) +
  labs(
    title    = "Palabras más representativas por tópico",
    subtitle = "Métrica FREX: mayor peso = mayor frecuencia y exclusividad",
    caption  = "Análisis inductivo — los tópicos emergen del corpus sin categorías previas"
  ) +
  tema_stm +
  theme(
    axis.text  = element_blank(),
    axis.title = element_blank(),
    panel.grid = element_blank()
  )

ggsave("output/plots/03_palabras_frex.png", p_words,
       width = 16, height = max(10, ceiling(K_optimo / n_cols_wrap) * 2.5),
       dpi = 150, bg = "#0D1117")

# ── Visualización 4: Evolución temporal (ribbon) ──────────────────────────────

efecto_anio <- estimateEffect(
  1:K_optimo ~ anio,
  modelo_stm,
  meta        = prep$meta,
  uncertainty = "Global"
)

# Extraer valores para cada tópico y año
anios_seq <- seq(2020, 2026, by = 0.25)
top_prevalentes <- order(colMeans(modelo_stm$theta), decreasing = TRUE)[1:min(8, K_optimo)]

evol_df <- do.call(rbind, lapply(top_prevalentes, function(k) {
  est <- efecto_anio$parameters[[k]][[1]]$est
  cov_matrix <- efecto_anio$parameters[[k]][[1]]$vcov
  data.frame(
    topico      = paste0("T", k),
    anio        = anios_seq,
    prevalencia = sapply(anios_seq, function(yr) {
      coefs <- efecto_anio$parameters[[k]][[1]]$est
      coefs[1] + coefs[2] * yr
    }),
    color = PALETA[k],
    stringsAsFactors = FALSE
  )
}))

frex_short <- apply(etiq$frex[top_prevalentes, 1:3], 1, paste, collapse = " · ")
evol_df$label <- frex_short[match(evol_df$topico, paste0("T", top_prevalentes))]
evol_df$topico_label <- paste0(evol_df$topico, ": ", evol_df$label)

p_evol <- ggplot(evol_df, aes(x = anio, y = prevalencia,
                               color = topico_label, group = topico_label)) +
  geom_line(linewidth = 1.3, alpha = 0.9) +
  geom_point(data = evol_df %>% filter(anio == round(anio)),
             size = 2.5, alpha = 0.8) +
  scale_color_manual(values = setNames(
    PALETA[seq_along(top_prevalentes)],
    unique(evol_df$topico_label)
  )) +
  scale_x_continuous(breaks = 2020:2026) +
  scale_y_continuous(labels = scales::percent_format(accuracy = 0.1)) +
  labs(
    title    = "Evolución temporal de los tópicos principales",
    subtitle = "Prevalencia esperada por año de publicación · 8 tópicos más frecuentes",
    x = "Año de publicación", y = "Prevalencia esperada",
    color    = "Tópico",
    caption  = "Estimación via STM con covariable continua de año"
  ) +
  tema_stm +
  theme(
    legend.position = "right",
    legend.key.size = unit(0.8, "lines"),
    legend.text     = element_text(size = 9)
  )

ggsave("output/plots/04_evolucion_temporal.png", p_evol,
       width = 16, height = 8, dpi = 150, bg = "#0D1117")

# ── Tabla y HTML ──────────────────────────────────────────────────────────────

etiq_full <- labelTopics(modelo_stm, n = 20)

tabla <- data.frame(
  topico      = seq_len(K_optimo),
  prevalencia = round(colMeans(modelo_stm$theta) * 100, 2),
  frex_top10  = apply(etiq_full$frex[, 1:10], 1, paste, collapse = ", "),
  prob_top10  = apply(etiq_full$prob[, 1:10], 1, paste, collapse = ", "),
  lift_top5   = apply(etiq_full$lift[, 1:5],  1, paste, collapse = ", ")
) %>% arrange(desc(prevalencia))

write_csv(tabla, "output/tabla_topicos.csv")

filas_html <- ""
for (i in seq_len(nrow(tabla))) {
  f <- tabla[i, ]
  color_hex <- PALETA[f$topico]
  filas_html <- paste0(filas_html, sprintf("
    <tr>
      <td><span class='tag' style='background:%s'>T%d</span></td>
      <td class='prev'>%.1f%%</td>
      <td class='words'>%s</td>
      <td class='words'>%s</td>
    </tr>",
    color_hex, f$topico, f$prevalencia, f$frex_top10, f$prob_top10
  ))
}

html <- sprintf('<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>STM Inductivo – Dirección Escolar</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{font-family:"Segoe UI",system-ui,sans-serif;background:#0D1117;color:#C9D1D9;max-width:1200px;margin:0 auto;padding:32px 24px}
  h1{font-size:1.8em;color:#E6EDF3;border-bottom:2px solid #21262D;padding-bottom:12px;margin-bottom:8px}
  h1 small{font-size:.55em;color:#8B949E;display:block;margin-top:4px}
  h2{color:#58A6FF;margin:40px 0 16px;font-size:1.1em;text-transform:uppercase;letter-spacing:.05em}
  .meta{color:#484F58;font-size:.85em;margin-bottom:28px}
  .kpi{display:flex;gap:12px;flex-wrap:wrap;margin:20px 0}
  .kpi-box{background:#161B22;border:1px solid #21262D;padding:16px 24px;border-radius:10px;text-align:center;min-width:140px;flex:1}
  .kpi-num{font-size:2.2em;font-weight:700;color:#58A6FF}
  .kpi-lbl{font-size:.78em;color:#8B949E;margin-top:4px}
  .note{background:#161B22;border-left:3px solid #58A6FF;padding:14px 18px;margin:20px 0;border-radius:0 8px 8px 0;font-size:.88em;line-height:1.6;color:#8B949E}
  .note strong{color:#C9D1D9}
  table{width:100%%;border-collapse:collapse;margin:16px 0;font-size:.85em}
  th{background:#161B22;color:#8B949E;padding:10px 14px;text-align:left;font-weight:500;text-transform:uppercase;font-size:.78em;letter-spacing:.05em;border-bottom:1px solid #21262D}
  td{padding:10px 14px;border-bottom:1px solid #161B22;vertical-align:top}
  td.prev{text-align:center;font-weight:700;color:#58A6FF;font-size:1.05em}
  td.words{color:#8B949E;font-size:.82em;line-height:1.5}
  tr:hover td{background:#161B22}
  .tag{display:inline-block;padding:3px 10px;border-radius:20px;color:#fff;font-weight:700;font-size:.85em}
  .plots{display:grid;grid-template-columns:1fr 1fr;gap:16px;margin:20px 0}
  .plot-box{background:#161B22;border:1px solid #21262D;border-radius:10px;padding:16px;overflow:hidden}
  .plot-box img{width:100%%;border-radius:6px}
  .plot-box h3{color:#C9D1D9;font-size:.9em;margin:10px 0 4px;font-weight:500}
  .plot-box p{color:#484F58;font-size:.8em}
  footer{margin-top:60px;color:#484F58;font-size:.78em;border-top:1px solid #21262D;padding-top:16px;text-align:center}
  @media(max-width:700px){.plots{grid-template-columns:1fr}.kpi-box{min-width:100px}}
</style>
</head>
<body>
<h1>Análisis de Tópicos (STM) Inductivo
<small>Literatura sobre Dirección y Gestión Escolar · 2020–2026</small></h1>
<p class="meta">Generado: %s</p>

<div class="kpi">
  <div class="kpi-box"><div class="kpi-num">%d</div><div class="kpi-lbl">Artículos analizados</div></div>
  <div class="kpi-box"><div class="kpi-num">%d</div><div class="kpi-lbl">Tópicos emergentes</div></div>
  <div class="kpi-box"><div class="kpi-num">%d</div><div class="kpi-lbl">Términos en vocabulario</div></div>
  <div class="kpi-box"><div class="kpi-num">2020–2026</div><div class="kpi-lbl">Período</div></div>
</div>

<div class="note">
<strong>Diseño inductivo:</strong> Los tópicos emergen libremente del análisis del corpus.
El preprocesamiento elimina únicamente palabras funcionales y términos del dominio omnipresentes
que no discriminan entre documentos. Sin umbral superior de vocabulario.
K=%d seleccionado automáticamente optimizando coherencia semántica y exclusividad (K ∈ {10,15,20,25,30}).
</div>

<h2>Tópicos emergentes del corpus</h2>
<table>
  <tr><th>Tópico</th><th>Prevalencia</th><th>FREX top 10</th><th>Más frecuentes</th></tr>
  %s
</table>

<h2>Visualizaciones</h2>
<div class="plots">
  <div class="plot-box">
    <img src="plots/01_seleccion_K.png" alt="Selección K">
    <h3>Selección de K</h3>
    <p>Diagnósticos de coherencia, exclusividad y held-out likelihood</p>
  </div>
  <div class="plot-box">
    <img src="plots/02_prevalencia_topicos.png" alt="Prevalencia">
    <h3>Prevalencia de tópicos</h3>
    <p>Proporción esperada de cada tópico en el corpus</p>
  </div>
  <div class="plot-box">
    <img src="plots/03_palabras_frex.png" alt="FREX">
    <h3>Palabras representativas</h3>
    <p>Términos con mayor frecuencia y exclusividad por tópico</p>
  </div>
  <div class="plot-box">
    <img src="plots/04_evolucion_temporal.png" alt="Evolución">
    <h3>Evolución temporal</h3>
    <p>Cómo varía la prevalencia de cada tópico entre 2020 y 2026</p>
  </div>
</div>

<footer>
Generado por GitHub Actions · stm_analysis.R ·
Corpus: %d artículos en acceso abierto indexados en OpenAlex (2020–2026)
</footer>
</body>
</html>',
  format(Sys.Date(), "%%d/%%m/%%Y"),
  nrow(corpus), K_optimo, length(prep$vocab),
  K_optimo, filas_html, nrow(corpus)
)

writeLines(html, "output/informe_stm.html")

cat("\n=== Completado ===\n")
cat(sprintf("K=%d tópicos · %d documentos · %d términos\n",
            K_optimo, nrow(corpus), length(prep$vocab)))
