source("topic_modeling/stm_pipeline.R", encoding = "UTF-8")

testthat::test_that("metric normalization is bounded and deterministic", {
  testthat::expect_equal(normalize_metric(c(1, 2, 3)), c(0, 0.5, 1))
  testthat::expect_equal(normalize_metric(c(1, 2, 3), FALSE), c(1, 0.5, 0))
})

testthat::test_that("stable DOI identifiers do not depend on row order", {
  first <- stable_document_id("https://doi.org/10.1/ABC", NA, "Title", 2024, "A", "x.pdf")
  second <- stable_document_id("10.1/abc", NA, "Other", 2025, "B", "y.pdf")
  testthat::expect_equal(first, second)
})
