#!/usr/bin/env python3
import argparse, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic_modeling.config import load_config
from topic_modeling.corpus_builder import read_csv, write_csv
from topic_modeling.embeddings import load_or_create_embeddings, load_or_create_metadata_embeddings
from topic_modeling.bertopic_diagnostics import ambiguity_flag, build_document_hierarchy, export_outlier_analysis, export_review_sets, export_topic_diagnostics
p=argparse.ArgumentParser(); p.add_argument("--config",default="config/topic_modeling.yml"); a=p.parse_args(); cfg=load_config(a.config)
root=Path(cfg["paths"]["output_root"]); out=root/"bertopic"/"metadata_multilingual"/"preferred_solution"
documents=read_csv(root/"corpus"/"modeling_corpus_metadata.csv"); rows=read_csv(out/"document_topics.csv"); topics=read_csv(out/"topics.csv"); words=read_csv(out/"topic_words.csv")
for row in rows: row["is_ambiguous"]=ambiguity_flag(row,cfg)
write_csv(out/"document_topics.csv",rows)
emb,_=load_or_create_metadata_embeddings(documents,cfg); ids=[row["document_id"] for row in documents]
title,_=load_or_create_embeddings(ids,[row.get("title_text") or row.get("title","") for row in documents],cfg)
abstract,_=load_or_create_embeddings(ids,[row.get("abstract_text") or "" for row in documents],cfg)
terms={int(t["topic_id"]):[r["term"] for r in words if r["topic_id"]==t["topic_id"]] for t in topics if t["topic_id"]!="-1"}
export_topic_diagnostics(out,documents,rows,emb,title,abstract,terms,cfg); export_outlier_analysis(out,documents,rows); build_document_hierarchy(out,documents,rows,emb,topics,cfg); export_review_sets(out,rows,int(cfg["validation"].get("representative_documents",10)),int(cfg["project"]["seed"]))
print(f"topics={len(terms)} ambiguous={sum(str(r['is_ambiguous']).lower()=='true' for r in rows)} outliers={sum(r['topic_id']=='-1' for r in rows)}")
