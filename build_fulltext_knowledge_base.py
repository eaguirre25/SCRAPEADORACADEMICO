#!/usr/bin/env python3
"""Construye docs/fulltext_knowledge_base.json unificando el texto completo de 1.387 artículos + 37 libros teóricos + metadatos."""
import csv, json, re, glob
from pathlib import Path

DATA = Path('data')
DOCS = Path('docs')
CORPUS = DATA / 'corpus.csv'
MASTER = DATA / 'master_records.csv'
TEORICOS = DATA / 'teoricos_articles.json'
OUT = DOCS / 'fulltext_knowledge_base.json'

csv.field_size_limit(150_000_000)

print('Indexando texto completo de todas las fuentes...')

# 1. Cargar master_records para metadatos
master_map = {}
if MASTER.exists():
    with MASTER.open(encoding='utf-8-sig', errors='replace') as f:
        for r in csv.DictReader(f):
            doi = (r.get('doi') or '').strip().lower()
            rec_id = (r.get('record_id') or doi or r.get('title') or '').strip()
            if rec_id:
                master_map[rec_id] = r
            if doi:
                master_map[doi] = r

# 2. Cargar textos completos de corpus.csv
corpus_texts = {}
if CORPUS.exists():
    with CORPUS.open(encoding='utf-8-sig', errors='replace') as f:
        for r in csv.DictReader(f):
            doi = (r.get('doi') or '').strip().lower()
            fn = (r.get('filename') or '').strip()
            txt = (r.get('texto') or '').strip()
            if txt:
                if doi: corpus_texts[doi] = txt
                if fn: corpus_texts[fn] = txt

# 3. Cargar textos individuales de docs/textos/*.txt
txt_files = glob.glob(str(DOCS / 'textos' / '*.txt'))
for tf in txt_files:
    fname = Path(tf).name
    if fname not in corpus_texts:
        try:
            content = Path(tf).read_text(encoding='utf-8', errors='replace').strip()
            if content:
                corpus_texts[fname] = content
        except Exception:
            pass

print(f'Textos completos cargados: {len(corpus_texts)} archivos/registros.')

knowledge_base = []

# Indexar artículos del corpus
if MASTER.exists():
    with MASTER.open(encoding='utf-8-sig', errors='replace') as f:
        for r in csv.DictReader(f):
            doi = (r.get('doi') or '').strip().lower()
            rec_id = (r.get('record_id') or doi or r.get('title') or '').strip()
            fn = (r.get('filename') or '').strip()
            
            full_txt = corpus_texts.get(doi) or corpus_texts.get(fn) or r.get('abstract') or ''
            
            # Fragmentar en párrafos con contexto
            paragraphs = [p.strip() for p in re.split(r'\n\s*\n|\r\n\r\n', full_txt) if len(p.strip()) >= 50]
            if not paragraphs and full_txt:
                paragraphs = [full_txt[:1000]]
                
            knowledge_base.append({
                'record_id': rec_id,
                'title': (r.get('title') or '').strip(),
                'authors': (r.get('authors') or '').strip(),
                'year': (r.get('publication_year') or '').strip(),
                'source': (r.get('origin') or r.get('source') or '').strip(),
                'doi': doi,
                'url': (r.get('url') or '').strip(),
                'abstract': (r.get('abstract') or '').strip()[:500],
                'fulltext_sample': full_txt[:3000], # Muestra ampliada de texto completo
                'paragraphs': paragraphs[:20],      # Párrafos para extracción de citas literales
                'has_fulltext': bool(corpus_texts.get(doi) or corpus_texts.get(fn)),
                'collection': 'corpus'
            })

# Indexar textos teóricos de Drive
if TEORICOS.exists():
    teoricos_list = json.loads(TEORICOS.read_text(encoding='utf-8'))
    for t in teoricos_list:
        knowledge_base.append({
            'record_id': t.get('record_id'),
            'title': t.get('title', ''),
            'authors': t.get('authors', ''),
            'year': t.get('year', ''),
            'source': t.get('source', 'Textos Teóricos (Drive)'),
            'drive_file_id': t.get('drive_file_id', ''),
            'drive_preview_url': t.get('drive_preview_url', ''),
            'abstract': f"Texto teórico de la carpeta Google Drive: {t.get('title', '')} por {t.get('authors', '')}.",
            'fulltext_sample': f"{t.get('title', '')} por {t.get('authors', '')}. Documento teórico de Google Drive.",
            'paragraphs': [f"Obra: {t.get('title', '')}. Autor/es: {t.get('authors', '')}. {t.get('drive_filename', '')}"],
            'has_fulltext': True,
            'collection': 'teoricos'
        })

print(f'Total de registros en la Base de Conocimiento Completa: {len(knowledge_base)}')

OUT.write_text(json.dumps(knowledge_base, ensure_ascii=False), encoding='utf-8')
print(f'Guardado docs/fulltext_knowledge_base.json ({OUT.stat().st_size / 1_024_1024:.2f} MB)!')
