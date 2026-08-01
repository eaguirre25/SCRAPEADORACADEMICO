#!/usr/bin/env python3
import argparse, shutil, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from topic_modeling.config import load_config
from topic_modeling.corpus_builder import build_corpora, export_corpora
p=argparse.ArgumentParser(); p.add_argument("--config",default="config/topic_modeling.yml"); p.add_argument("--invalidate-embeddings",action="store_true"); a=p.parse_args(); cfg=load_config(a.config)
if a.invalidate_embeddings:
    cache=(Path(cfg["paths"]["cache_root"])/"embeddings").resolve(); allowed=Path(cfg["paths"]["cache_root"]).resolve()
    if cache.exists():
        if allowed not in cache.parents: raise RuntimeError(f"Unsafe cache target: {cache}")
        archive=allowed/"archive"/"pre_unicode_fix"/"embeddings"
        suffix=1
        while archive.exists():
            suffix+=1; archive=allowed/"archive"/"pre_unicode_fix"/f"embeddings_{suffix}"
        archive.parent.mkdir(parents=True,exist_ok=True); shutil.move(str(cache),str(archive))
result=build_corpora(cfg); export_corpora(cfg,result)
print(f"metadata={len(result.metadata)} fulltext={len(result.fulltext)} publications={len(result.publications)}")
