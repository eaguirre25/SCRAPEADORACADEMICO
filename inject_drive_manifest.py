#!/usr/bin/env python3
"""Enriquece docs/library_articles.json con PDFs de Google Drive.

Regla de seguridad bibliográfica:
1) DOI real exacto.
2) Si no hay DOI utilizable, coincidencia ESTRICTA por título + año + autor.
3) Si la coincidencia es ambigua, NO se vincula ningún PDF.

Es preferible mostrar "PDF sin vincular" antes que abrir un trabajo incorrecto.
"""
import csv, json, re, unicodedata
from difflib import SequenceMatcher
from pathlib import Path

ART=Path('docs/library_articles.json')
MAN=Path('data/drive_manifest.csv')
if not ART.exists():
    raise SystemExit('Falta docs/library_articles.json')
articles=json.loads(ART.read_text(encoding='utf-8'))

STOP={'para','sobre','entre','desde','hacia','como','with','from','into','and','the','of','del','las','los','una','uno','unos','unas','por','con','sin','que','sus','this','that'}

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

def meaningful_tokens(v, minlen=4):
    return [t for t in norm(v).split() if len(t)>=minlen and t not in STOP and not t.isdigit()]

def author_tokens(v):
    """Tokens distintivos de autor. Se usan solo como condición obligatoria de refuerzo."""
    toks=meaningful_tokens(v,5)
    # conservar hasta 8: apellidos compuestos y varios autores, sin convertir el autor en criterio laxo
    return toks[:8]

rows=[]; by_doi={}
if MAN.exists():
    with MAN.open(encoding='utf-8-sig',newline='',errors='replace') as f:
        for r in csv.DictReader(f):
            r['_hay']=norm(' '.join([r.get('filename',''),r.get('doi','')]))
            d=doi_norm(r.get('doi'))
            if d: by_doi[d]=r
            rows.append(r)

def strict_score(a,r):
    """Devuelve score solo si pasan simultáneamente título, año y autor."""
    title=norm(a.get('title'))
    hay=r.get('_hay','')
    if not title or not hay: return 0.0

    # 1. Año obligatorio cuando está disponible en el registro.
    year=norm(a.get('year'))
    if year and year not in hay:
        return 0.0

    # 2. Autor obligatorio: al menos un token distintivo de autor debe figurar en filename/slug.
    at=author_tokens(a.get('authors'))
    if at and not any(t in hay for t in at):
        return 0.0

    # 3. Título: cobertura alta de tokens distintivos + similitud de secuencia.
    tt=meaningful_tokens(title,4)
    if not tt: return 0.0
    overlap=sum(1 for t in tt if t in hay)/len(tt)
    seq=SequenceMatcher(None,title,hay).ratio()

    # Si el título entero está contenido, es una coincidencia muy fuerte.
    if title in hay:
        title_score=1.0
    else:
        # Los nombres de Drive pueden truncar títulos largos, pero no aceptamos coincidencias vagas.
        # Exigimos al menos 78% de los tokens del título; para títulos cortos, 90%.
        min_overlap=0.90 if len(tt)<=6 else 0.78
        if overlap < min_overlap:
            return 0.0
        # La similitud global no puede ser demasiado baja aun con tokens coincidentes.
        if seq < 0.58:
            return 0.0
        title_score=0.72*overlap + 0.28*seq

    # refuerzo de autor: cuantos más tokens coinciden, mejor, pero no rescata un título insuficiente
    auth_overlap=(sum(1 for t in at if t in hay)/len(at)) if at else 0.0
    return min(1.0, 0.88*title_score + 0.12*auth_overlap)

linked=0; strict_linked=0; ambiguous=0; unmatched=0
for a in articles:
    # limpiar cualquier vínculo heredado de builds previos antes de recalcular
    for k in ('drive_file_id','drive_preview_url','drive_open_url','drive_filename','drive_match_method','drive_match_score'):
        a.pop(k,None)

    m=None; method=''; score=0.0
    d=doi_norm(a.get('doi'))
    if d and d in by_doi:
        m=by_doi[d]; method='doi_exact'; score=1.0
    elif rows:
        candidates=[]
        for r in rows:
            sc=strict_score(a,r)
            if sc>0: candidates.append((sc,r))
        candidates.sort(key=lambda x:x[0], reverse=True)
        if candidates:
            best_s,best=candidates[0]
            second_s=candidates[1][0] if len(candidates)>1 else 0.0
            # Umbral alto + margen de unicidad. Si dos archivos son parecidos, no adivinar.
            if best_s>=0.84 and (best_s-second_s>=0.07 or second_s==0):
                m=best; method='strict_title_author_year'; score=best_s; strict_linked+=1
            else:
                ambiguous+=1

    if m:
        fid=m.get('drive_file_id','')
        a['drive_file_id']=fid
        a['drive_preview_url']=m.get('preview_url','') or (f'https://drive.google.com/file/d/{fid}/preview' if fid else '')
        a['drive_open_url']=m.get('open_url','') or m.get('web_view_link','')
        a['drive_filename']=m.get('filename','')
        a['drive_match_method']=method
        a['drive_match_score']=round(score,3)
        linked+=1
    else:
        unmatched+=1

ART.write_text(json.dumps(articles,ensure_ascii=False),encoding='utf-8')
print(f'PDFs Drive vinculados: {linked}; estrictos título+autor+año: {strict_linked}; ambiguos rechazados: {ambiguous}; sin vínculo: {unmatched}')
