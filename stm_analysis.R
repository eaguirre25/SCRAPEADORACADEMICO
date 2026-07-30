#!/usr/bin/env Rscript
# Entrada compatible. La implementación modular vive en topic_modeling/stm_pipeline.R.
source("topic_modeling/stm_pipeline.R", encoding = "UTF-8")
run_stm_pipeline(commandArgs(trailingOnly = TRUE))
