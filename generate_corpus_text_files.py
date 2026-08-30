#!/usr/bin/env python3
"""Publica el texto extraído del corpus como archivos individuales y vincula library_articles.json."""
from pathlib import Path
import csv, json, hashlib, re

CORPUS=Path('data/corpus.csv'); LIB=Path('docs/library_articles.json'); OUT=Path('docs/textos')
OUT.mkdir(parents=True, exist_ok=True)

def normdoi(v):
    return str(v or '').strip().lower().replace('https://doi.org/','').replace('http://doi.org/','')

def slug(doi, filename):
    base=normdoi(doi) or str(filename or '')
    return hashlib.sha1(base.encode('utf-8','ignore')).hexdigest()+'.txt'

if not CORPUS.exists() or not LIB.exists():
    raise SystemExit('Falta data/corpus.csv o docs/library_articles.json')

csv.field_size_limit(250_000_000)
idx={}
with CORPUS.open(encoding='utf-8-sig', newline='', errors='replace') as f:
    for r in csv.DictReader(f):
        doi=normdoi(r.get('doi'))
        text=str(r.get('texto') or '').strip()
        status=str(r.get('status') or '').strip().lower()
        if not doi or status!='ok' or len(text)<120:
            continue
        name=slug(doi,r.get('filename'))
        (OUT/name).write_text(text,encoding='utf-8')
        idx[doi]={'text_file':'textos/'+name,'text_chars':len(text),'text_pages':str(r.get('paginas') or '')}

arts=json.loads(LIB.read_text(encoding='utf-8'))
count=0
for a in arts:
    x=idx.get(normdoi(a.get('doi')))
    if x:
        a.update(x); count+=1
LIB.write_text(json.dumps(arts,ensure_ascii=False),encoding='utf-8')
print(f'Textos publicados: {count}')
