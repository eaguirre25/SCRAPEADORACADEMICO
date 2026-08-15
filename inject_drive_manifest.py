#!/usr/bin/env python3
"""Enriquece docs/library_articles.json con IDs y URLs de Google Drive.

Empareja primero por DOI real y, si falta, por título/año/autores contra el nombre
normalizado del PDF en Drive. Esto evita perder vínculos cuando el manifiesto no
puede reconstruir el DOI desde el filename.
"""
import csv, json, re, unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ART=Path('docs/library_articles.json')
MAN=Path('data/drive_manifest.csv')
if not ART.exists():
    raise SystemExit('Falta docs/library_articles.json')
articles=json.loads(ART.read_text(encoding='utf-8'))


def norm(v):
    v=str(v or '').lower().strip()
    v=v.replace('https://doi.org/','').replace('http://doi.org/','')
    v=''.join(c for c in unicodedata.normalize('NFD',v) if unicodedata.category(c)!='Mn')
    v=re.sub(r'\.pdf$','',v)
    v=re.sub(r'[^a-z0-9]+',' ',v)
    return re.sub(r'\s+',' ',v).strip()


def doi_norm(v):
    v=str(v or '').lower().strip().replace('https://doi.org/','').replace('http://doi.org/','')
    return v if v.startswith('10.') and '/' in v else ''

rows=[]
by_doi={}
if MAN.exists():
    with MAN.open(encoding='utf-8-sig',newline='',errors='replace') as f:
        for r in csv.DictReader(f):
            r['_name']=norm(r.get('filename'))
            r['_slug']=norm(r.get('doi'))  # histórico: a veces esta columna contiene slug, no DOI
            d=doi_norm(r.get('doi'))
            if d:
                by_doi[d]=r
            rows.append(r)


def score_article_file(a,r):
    title=norm(a.get('title'))
    if not title:
        return 0.0
    hay=' '.join([r.get('_name',''),r.get('_slug','')]).strip()
    if not hay:
        return 0.0
    # similitud base por título
    s=SequenceMatcher(None,title,hay).ratio()
    # coincidencia fuerte si el título aparece casi literal en el filename/slug
    if title in hay:
        s=max(s,0.96)
    # tokens informativos del título
    toks=[t for t in title.split() if len(t)>=5]
    if toks:
        overlap=sum(1 for t in toks if t in hay)/len(toks)
        s=max(s,0.55+0.4*overlap)
    year=norm(a.get('year'))
    if year and year in hay:
        s+=0.04
    # apellido/autor como refuerzo, nunca como criterio único
    authors=norm(a.get('authors'))
    auth_toks=[t for t in authors.split() if len(t)>=5][:4]
    if auth_toks and any(t in hay for t in auth_toks):
        s+=0.03
    return min(s,1.0)

linked=0
fuzzy=0
for a in articles:
    m=None
    d=doi_norm(a.get('doi'))
    if d:
        m=by_doi.get(d)
    if not m and rows:
        best=None; best_s=0.0
        for r in rows:
            sc=score_article_file(a,r)
            if sc>best_s:
                best_s=sc; best=r
        # umbral conservador para evitar asociar un PDF equivocado
        if best is not None and best_s>=0.82:
            m=best; fuzzy+=1
    if m:
        a['drive_file_id']=m.get('drive_file_id','')
        a['drive_preview_url']=m.get('preview_url','') or (f"https://drive.google.com/file/d/{m.get('drive_file_id','')}/preview" if m.get('drive_file_id') else '')
        a['drive_open_url']=m.get('open_url','') or m.get('web_view_link','')
        a['drive_filename']=m.get('filename','')
        linked+=1

ART.write_text(json.dumps(articles,ensure_ascii=False),encoding='utf-8')
print(f'Artículos enriquecidos con Drive: {linked} (por coincidencia de título/año/autor: {fuzzy})')
