#!/usr/bin/env python3
"""Enriquece docs/library_articles.json con IDs y URLs de Google Drive."""
import csv, json
from pathlib import Path

ART=Path('docs/library_articles.json')
MAN=Path('data/drive_manifest.csv')
if not ART.exists(): raise SystemExit('Falta docs/library_articles.json')
articles=json.loads(ART.read_text(encoding='utf-8'))
manifest={}
if MAN.exists():
    with MAN.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            doi=(r.get('doi') or '').strip().lower().replace('https://doi.org/','')
            if doi: manifest[doi]=r
for a in articles:
    doi=(a.get('doi') or '').strip().lower().replace('https://doi.org/','')
    m=manifest.get(doi,{})
    if m:
        a['drive_file_id']=m.get('drive_file_id','')
        a['drive_preview_url']=m.get('preview_url','')
        a['drive_open_url']=m.get('open_url','') or m.get('web_view_link','')
ART.write_text(json.dumps(articles,ensure_ascii=False),encoding='utf-8')
print(f'Artículos enriquecidos con Drive: {sum(1 for a in articles if a.get("drive_file_id"))}')
