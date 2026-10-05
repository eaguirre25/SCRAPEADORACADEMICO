#!/usr/bin/env python3
"""Publica el texto extraído del corpus como archivos individuales y vincula library_articles.json."""
from pathlib import Path
import csv, gzip, json, hashlib, re

CORPUS=Path('data/corpus.csv.gz'); LIB=Path('docs/library_articles.json'); OUT=Path('docs/textos')
OUT.mkdir(parents=True, exist_ok=True)

def normdoi(v):
    return str(v or '').strip().lower().replace('https://doi.org/','').replace('http://doi.org/','')

def slug(doi, filename):
    base=normdoi(doi) or str(filename or '')
    return hashlib.sha1(base.encode('utf-8','ignore')).hexdigest()+'.txt'

if not CORPUS.exists() or not LIB.exists():
    raise SystemExit('Falta data/corpus.csv.gz o docs/library_articles.json')

csv.field_size_limit(250_000_000)
arts=json.loads(LIB.read_text(encoding='utf-8'))
# Solo se publican textos de trabajos que siguen en la biblioteca (maestro
# vigente); los de registros descartados o unificados no deben quedar en línea.
wanted={normdoi(a.get('doi')) for a in arts if normdoi(a.get('doi'))}
idx={}
with gzip.open(CORPUS, 'rt', encoding='utf-8-sig', newline='', errors='replace') as f:
    for r in csv.DictReader(f):
        doi=normdoi(r.get('doi'))
        text=str(r.get('texto') or '').strip()
        status=str(r.get('status') or '').strip().lower()
        if not doi or doi not in wanted or status!='ok' or len(text)<120:
            continue
        name=slug(doi,r.get('filename'))
        (OUT/name).write_text(text,encoding='utf-8')
        idx[doi]={'text_file':'textos/'+name,'text_chars':len(text),'text_pages':str(r.get('paginas') or '')}

current={x['text_file'].split('/',1)[1] for x in idx.values()}
stale=[p for p in OUT.glob('*.txt') if p.name not in current]
for p in stale:
    p.unlink()

count=0
for a in arts:
    x=idx.get(normdoi(a.get('doi')))
    if x:
        a.update(x); count+=1
LIB.write_text(json.dumps(arts,ensure_ascii=False),encoding='utf-8')
print(f'Textos publicados: {count}; archivos viejos eliminados: {len(stale)}')
