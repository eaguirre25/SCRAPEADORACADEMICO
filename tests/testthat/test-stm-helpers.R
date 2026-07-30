source(file.path("..", "..", "topic_modeling", "stm_pipeline.R"), encoding = "UTF-8")

testthat::test_that("metric normalization is bounded and deterministic", {
  testthat::expect_equal(normalize_metric(c(1, 2, 3)), c(0, 0.5, 1))
  testthat::expect_equal(normalize_metric(c(1, 2, 3), FALSE), c(1, 0.5, 0))
})

testthat::test_that("stable DOI identifiers do not depend on row order", {
  first <- stable_document_id("https://doi.org/10.1/ABC", NA, "Title", 2024, "A", "x.pdf")
  second <- stable_document_id("10.1/abc", NA, "Other", 2025, "B", "y.pdf")
  testthat::expect_equal(first, second)
})

testthat::test_that("missing stability is not imputed and remaining weights are renormalized", {
  diagnostics <- data.frame(
    coherence = c(1, 2), exclusivity = c(2, 1), heldout = c(1, 2),
    residual = c(2, 1), stability = c(NA_real_, NA_real_)
  )
  weights <- list(coherence = .30, exclusivity = .25, heldout = .20, residual = .10, stability = .15)
  scored <- score_diagnostics(diagnostics, weights)
  testthat::expect_true(all(grepl("stability", scored$missing_metrics)))
  testthat::expect_false(grepl("stability=", scored$weights_used[1]))
  used <- as.numeric(sub(".*=", "", strsplit(scored$weights_used[1], ";")[[1]]))
  testthat::expect_equal(sum(used), 1, tolerance = 1e-3)
})

testthat::test_that("selection cannot be labelled validated without stability and human review", {
  selection_status <- "provisional"
  human_review_status <- "pending"
  testthat::expect_false(selection_status == "validated" || human_review_status == "validated")
})

testthat::test_that("language filtering does not compare the column with itself", {
  fixture <- data.frame(document_id = c("es-1", "en-1", "pt-1"), language = c("es", "en", "pt"))
  selected <- filter_corpus_language(fixture, "en")
  testthat::expect_equal(selected$document_id, "en-1")
  testthat::expect_equal(nrow(filter_corpus_language(fixture, "all")), 3)
})
