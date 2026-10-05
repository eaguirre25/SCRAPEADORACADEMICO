#!/usr/bin/env python3
"""Independent, reviewable Argentina branch of the existing bibliographic workflow."""
import argparse
import csv
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from keyword_network import build_network, read_rules
from topic_modeling.deduplication import audit_and_resolve_duplicates
from topic_modeling.identifiers import stable_document_id, normalize_doi
from topic_modeling.text_cleaning import clean_for_embeddings, clean_for_vectorizer
from apa_citation import build_citation, plain_text, format_author

ROOT = Path('output/argentina')
DOCS = Path('docs')

def model_signature(settings):
    return hashlib.sha256((json.dumps(settings,sort_keys=True)+Path('config/topic_modeling.yml').read_text()).encode()).hexdigest()

def semantic_neighbors(embeddings, document_ids, neighbors=5, minimum=.70):
    """Mutual nearest neighbors with an explicit cosine floor; self-links excluded."""
    import numpy as np
    x=np.asarray(embeddings,dtype=np.float64)
    if len(x)!=len(document_ids) or len(set(document_ids))!=len(document_ids):
        raise ValueError('Embedding/identifier alignment mismatch')
    x=x/np.maximum(np.linalg.norm(x,axis=1,keepdims=True),1e-12)
    similarities=x@x.T;np.fill_diagonal(similarities,-np.inf)
    def edges(k,floor):
        nearest=[set(np.lexsort((np.arange(len(x)),-similarities[i]))[:min(k,len(x)-1)]) for i in range(len(x))]
        return [{'source':document_ids[a],'target':document_ids[b],'weight':round(float(similarities[a,b]),6)}
            for a,items in enumerate(nearest) for b in sorted(items) if a<b and a in nearest[b] and similarities[a,b]>=floor]
    chosen=edges(neighbors,minimum)
    sensitivity=[]
    for k in [3,5,10]:
        for floor in [.60,.70,.80]:
            variant=edges(k,floor);connected={e[end]for e in variant for end in ['source','target']}
            sensitivity.append({'neighbors':k,'min_similarity':floor,'edges':len(variant),'isolated':len(x)-len(connected)})
    return {'kind':'mutual_nearest_neighbors','metric':'cosine_in_original_weighted_embeddings',
        'neighbors':neighbors,'min_similarity':minimum,'edges':chosen,'sensitivity':sensitivity}

def short_citation(row):
    names=[format_author(a.strip(), '').split(',',1)[0] for a in row.get('authors','').split(';') if a.strip()]
    author=names[0]+' et al.' if len(names)>2 else ' & '.join(names)
    return f"{author or 'Sin autor'}, {row.get('publication_year') or 's. f.'}"

def read_csv(path):
    csv.field_size_limit(50_000_000)
    if not Path(path).exists(): return []
    with open(path, encoding='utf-8-sig', newline='') as f: return list(csv.DictReader(f))

def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open('w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields); w.writeheader(); w.writerows(rows)

def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    compact=path.name=='argentina-data.json'
    path.write_text(json.dumps(data, ensure_ascii=False, indent=None if compact else 2,
        separators=(',', ':') if compact else None), encoding='utf-8')

def clean_repository_abstract(row):
    """Misma limpieza de cabeceras de CONICET que usa el modelo global."""
    from topic_modeling.text_cleaning import strip_repository_header
    return strip_repository_header(row.get('abstract', '') or '', row.get('title', '') or '')

def strip_territorial_terms(text, settings):
    """Saca los topónimos del vocabulario de los tópicos (no de los embeddings).

    Todo el corpus se seleccionó por mencionar la Argentina o sus provincias:
    esos términos no distinguen tópicos y dominaban las etiquetas automáticas.
    """
    if not settings.get('exclude_territorial_terms_from_topic_words'):
        return text
    return re.sub(r'\s+', ' ', re.sub(settings['territorial_pattern'], ' ', text, flags=re.I)).strip()

MODEL_OUTPUT = 'argentina_2020_2026'

def search_parameters(config, settings):
    """Elige UMAP y HDBSCAN con el mismo procedimiento que el modelo global.

    Usa topic_modeling.bertopic_search sin cambios: cribado de geometrías UMAP,
    grilla HDBSCAN sobre las tres mejores, reglas de rechazo, puntaje
    multicriterio, cuatro finalistas y estabilidad en cinco semillas (ARI, NMI,
    centroides y palabras). Solo se reemplazan, de forma declarada en
    config/argentina_analysis.json, la grilla de tamaños y los umbrales que
    dependen del tamaño del corpus.
    """
    from topic_modeling.bertopic_search import search_bertopic_parameters, run_bertopic_stability
    config['bertopic']['macro_search'].update(settings['macro_search'])
    search_bertopic_parameters(config, output_name=MODEL_OUTPUT)
    run_bertopic_stability(config, output_name=MODEL_OUTPUT, finalists_only=True)
    out = ROOT/'bertopic'/MODEL_OUTPUT
    selected = json.loads((out/'selected_parameters.json').read_text(encoding='utf-8'))['selected']
    return selected, read_csv(out/'candidate_solutions.csv'), read_csv(out/'stability_runs.csv')

def screening(row, settings, reviews):
    evidence = []
    for field in ('title', 'abstract'):
        value = row.get(field, '')
        for match in re.finditer(settings['territorial_pattern'], value, re.I):
            evidence.append({'field': field, 'term': match.group(), 'excerpt': value[max(0, match.start()-100):match.end()+180]})
    decision = reviews.get(str(row['record_id']), {}).get('decision', 'pending')
    if decision not in {'pending', 'include', 'exclude', 'uncertain'}: raise ValueError('Unknown territorial decision')
    try: period = settings['start_year'] <= int(row['publication_year']) <= settings['end_year']
    except (ValueError, KeyError): period = False
    text = ' '.join(row.get(k, '') for k in ('title', 'abstract', 'keywords'))
    # Puntaje de pertinencia del filtro general: los aceptados solo por la
    # segunda revisión con puntaje <= 0 resultaron ajenos a la gestión escolar
    # (biología, agro, arqueología). Una inclusión manual los recupera.
    try: low_relevance = int(row.get('relevance_score') or '') < settings.get('min_relevance_score', -10**9)
    except ValueError: low_relevance = False
    eligible = period and len(text.strip()) >= 80 and (decision == 'include' or (
        settings['include_unvalidated_candidates'] and bool(evidence) and decision == 'pending' and not low_relevance))
    return {'evidence': evidence, 'decision': decision, 'in_period': period, 'modeled': eligible,
            'low_relevance': low_relevance,
            'notes': reviews.get(str(row['record_id']), {}).get('notes', ''),
            'reason': 'out_of_period' if not period else 'insufficient_metadata' if len(text.strip())<80 else 'human_exclusion' if decision=='exclude' else 'uncertain' if decision=='uncertain' else 'human_inclusion' if decision=='include' else 'low_relevance' if low_relevance and evidence else 'territorial_candidate' if evidence else 'no_territorial_evidence'}

def prepare(settings):
    raw = read_csv('data/master_records.csv')
    canonical, exact, probable, resolution = audit_and_resolve_duplicates(raw)
    reviews = json.loads(Path(settings['review_file']).read_text(encoding='utf-8'))
    if reviews.get('schema_version') != 1 or reviews.get('criterion') != settings['criterion']:
        raise ValueError('Review schema or geographic criterion mismatch')
    known={r['record_id']for r in canonical}
    for key,review in reviews.get('documents',{}).items():
        if key not in known or not isinstance(review.get('notes'),str):
            raise ValueError('Unknown record or invalid review notes: '+key)
    documents = []; corpus = []
    for row in sorted(canonical, key=lambda r:r['record_id']):
        check = screening(row, settings, reviews.get('documents', {}))
        if not check['in_period']: continue
        abstract = clean_repository_abstract(row)
        doc = {**row, **check, 'abstract': abstract, 'document_id': stable_document_id(row)}
        documents.append(doc)
        if not check['modeled']: continue
        text, _ = clean_for_embeddings(' '.join([row.get('title', ''), row.get('keywords', ''), abstract]))
        vector, _ = clean_for_vectorizer(strip_territorial_terms(text, settings))
        corpus.append({'document_id': doc['document_id'], 'publication_document_id': doc['document_id'],
            'record_id':row['record_id'], 'title':row['title'], 'abstract':abstract, 'keywords':row['keywords'],
            'title_text':row['title'], 'abstract_text':abstract, 'keywords_text':row['keywords'],
            'text_for_vectorizer':vector, 'text_for_modeling':text, 'texto_modelado':text,
            'year':row['publication_year'], 'authors':row['authors'], 'doi':normalize_doi(row['doi']),
            'source':row['source'], 'url':row['url'], 'corpus_unit':'metadata', 'language':'und',
            'relevance_status':row.get('relevance_status',''), 'relevance_score':row.get('relevance_score',''),
            'territorial_decision':check['decision']})
    write_csv(ROOT/'corpus/modeling_corpus_metadata.csv', corpus)
    write_csv(ROOT/'duplicate_resolution.csv', resolution)
    write_csv(ROOT/'probable_duplicates.csv', probable)
    fingerprint=hashlib.sha256((ROOT/'corpus/modeling_corpus_metadata.csv').read_bytes()).hexdigest()
    manifest={'criterion':settings['criterion'], 'period':[settings['start_year'],settings['end_year']],
        'master_records':len(raw), 'canonical_publications':len(canonical), 'period_publications':len(documents),
        'modeled_candidates':len(corpus), 'territorial_candidates':sum(bool(d['evidence']) for d in documents),
        'human_included':sum(d['decision']=='include' for d in documents),
        'no_territorial_evidence':sum(not d['evidence'] for d in documents),
        'low_relevance_excluded':sum(bool(d['evidence']) and d['low_relevance'] and d['decision']=='pending' for d in documents),
        'exact_duplicate_groups':len({r.get('duplicate_group_id') for r in exact}), 'probable_duplicate_pairs':len(probable),
        'corpus_hash':fingerprint, 'master_sha256':hashlib.sha256(Path('data/master_records.csv').read_bytes()).hexdigest(),
        'year_counts':dict(sorted(Counter(r['year'] for r in corpus).items())),
        'partial_year':date.today().year if settings['end_year']>=date.today().year else None,
        'settings':settings, 'domain_eligibility':'Accepted master_records from the existing scraping/relevance workflow; no new topic-based domain exclusion.',
        'limitations':['Territorial text matches are candidates, not verified study locations.',
            'Missing territorial evidence does not demonstrate a study took place outside Argentina.',
            'No affiliation country inference from repository or author name.',
            'The year filter uses publication year, not fieldwork year.',
            'Territorial terms remain in the embedding text but are excluded from topic words; geographic clusters still require substantive review.',
            'CONICET repository headers (titles and authors prepended to the abstract) are removed for this analysis only.',
            'Coverage depends on the existing thematic search, providers and available metadata.']}
    write_json(ROOT/'corpus_manifest.json', manifest)
    return documents, corpus, manifest, reviews

def fit(settings):
    from topic_modeling.config import load_config
    from topic_modeling.bertopic_model import run_bertopic
    from topic_modeling.embeddings import load_or_create_metadata_embeddings
    from topic_modeling.language_detection import detect_language
    config=load_config('config/topic_modeling.yml')
    config['paths']['output_root']=str(ROOT)
    config['paths']['human_labels']='config/argentina_topic_labels.csv'
    corpus=read_csv(ROOT/'corpus/modeling_corpus_metadata.csv')
    if len(corpus)<20:
        raise ValueError('Insufficient documents for the configured independent model')
    # El idioma entra en el cribado (NMI idioma-tópico), igual que en el global.
    for row in corpus: row['language']=detect_language(row['texto_modelado'])[0]
    write_csv(ROOT/'corpus/modeling_corpus_metadata.csv',corpus)
    selection_hash=json.loads((ROOT/'corpus_manifest.json').read_text())['corpus_hash']
    embeddings,_=load_or_create_metadata_embeddings(corpus,config)
    selected,candidates,stability_runs=search_parameters(config,settings)
    config['bertopic']['umap'].update({'n_neighbors':int(selected['n_neighbors']),'n_components':int(selected['n_components']),
        'min_dist':float(selected['min_dist'])})
    config['bertopic']['min_topic_size']=int(selected['min_cluster_size'])
    config['bertopic']['min_samples']=int(selected['min_samples'])
    config['bertopic']['reduce_outliers']=False
    config['bertopic']['model_label']='BERTopic-ARGENTINA-2020-2026'
    # Vectorización idéntica a la global (min_df 2, max_df 0,95). Solo si con
    # pocos tópicos no queda vocabulario se relaja, y queda registrado.
    vectorizer_note='Vectorizer identical to the global model (min_df=2, max_df=0.95).'
    try:
        run_bertopic(config, output_name=MODEL_OUTPUT)
    except ValueError as error:
        if 'vocabulary' not in str(error).lower() and 'max_df' not in str(error).lower(): raise
        config['bertopic']['min_df']=1; config['bertopic']['max_df']=1.0
        vectorizer_note='Global vectorizer left no vocabulary for this number of topics; min_df=1/max_df=1.0 used instead.'
        run_bertopic(config, output_name=MODEL_OUTPUT)
    out=ROOT/'bertopic'/MODEL_OUTPUT
    write_json(out/'semantic_network.json',semantic_neighbors(embeddings,[r['record_id']for r in corpus],
        settings['semantic_network']['neighbors'],settings['semantic_network']['min_similarity']))
    solution=selected.get('solution_id','')
    keep=('phase','n_neighbors','n_components','min_dist','min_cluster_size','min_samples','clusters','outlier_share',
        'median_cluster_size','maximum_cluster_share','silhouette','dbcv','topic_diversity','multi_criteria_score',
        'rejection_reasons','solution_status','solution_id','stability_ari_mean','stability_nmi_mean')
    signature=model_signature(json.loads(Path('config/argentina_analysis.json').read_text()))
    write_json(out/'screening_model_manifest.json',{'selection_hash':selection_hash,'model_signature':signature,
        'model_id':hashlib.sha256((selection_hash+signature).encode()).hexdigest(),'criterion':settings['criterion'],
        'status':'exploratory_candidates','procedure':'global_bertopic_search',
        'selected_parameters':{k:selected.get(k) for k in keep},
        'parameter_search':[{k:r.get(k,'') for k in keep} for r in candidates],
        'stability':[r for r in stability_runs if r.get('solution_id')==solution],
        'macro_search':config['bertopic']['macro_search'],
        'parameter_choice':('Parameters chosen with the same procedure as the global model (multi-criteria macro screen over '
            'UMAP geometries and HDBSCAN settings, rejection rules, four finalists, five-seed stability). Only the HDBSCAN size grid '
            'and size-dependent thresholds are scaled to the corpus, as declared in config/argentina_analysis.json. '+vectorizer_note+
            ' Territorial terms are excluded from topic words only. No optimum or substantive validation is claimed.')})

def render(documents, corpus, manifest, reviews):
    out=ROOT/'bertopic/argentina_2020_2026'
    model_manifest=json.loads((out/'screening_model_manifest.json').read_text()) if (out/'screening_model_manifest.json').exists() else {}
    current=model_manifest.get('selection_hash')==manifest['corpus_hash'] and model_manifest.get('model_signature')==model_signature(manifest['settings'])
    if reviews.get('topics') and reviews.get('model_id')!=model_manifest.get('model_id'):
        reviews={**reviews,'topics':{}}
    assignments={r['document_id']:r for r in read_csv(out/'document_topics.csv')} if current else {}
    topics=[r for r in read_csv(out/'topics.csv') if int(r['topic_id'])>=0] if current else []
    subset=[d for d in documents if d['modeled']]
    ids,cleaned,variants,audit=build_network(subset,read_rules())
    by_id={r['record_id']:r for r in subset};palette=['#64d5ff','#c299ff','#ffbb77','#73e5c2','#f995bf','#9db7ff','#e4d885','#8bd5a0']
    nodes=[]
    for key in ids:
        row=by_id[key];a=assignments.get(row['document_id'],{});topic=int(a.get('topic_id',-1));citation=build_citation(row)
        nodes.append({'id':key,'title':row['title'],'authors':row['authors'],'year':row['publication_year'],
            'short_citation':short_citation(row),'reference':plain_text(citation),'url':row['url'],
            'topic':str(topic),'topic_label':'Sin tópico asignado' if topic<0 else next((t['automatic_label']for t in topics if int(t['topic_id'])==topic),''),
            'color':'#7089a3'if topic<0 else palette[topic%len(palette)],'degree':0,
            'keywords':cleaned[key]['keywords'],'keyword_excluded':cleaned[key]['excluded'],
            'keyword_provenance':cleaned[key]['provenance']})
    edges=variants['balanced']
    for edge in edges: nodes[edge['source']]['degree']+=1;nodes[edge['target']]['degree']+=1
    tid={t['topic_id']:i for i,t in enumerate(topics)}
    tedges=[{'source':tid[r['topic_a']],'target':tid[r['topic_b']],'weight':float(r['ctfidf_similarity'])}for r in read_csv(out/'topic_similarity.csv') if current and r['topic_a']in tid and r['topic_b']in tid and float(r['ctfidf_similarity'])>=.35]
    tnodes=[{'id':t['topic_id'],'label':t['automatic_label'],'words':t['top_words'].split(' | '),'size':int(t['document_count']),'color':palette[int(t['topic_id'])%len(palette)]}for t in topics]
    semantic=json.loads((out/'semantic_network.json').read_text()) if current and (out/'semantic_network.json').exists() else {}
    positions={key:i for i,key in enumerate(ids)}
    semantic_edges=[{**e,'source':positions[e['source']],'target':positions[e['target']],
        'relation':'semantic'}for e in semantic.get('edges',[])]
    for d in documents:
        d['assignment']=assignments.get(d['document_id'],{})
        citation=build_citation(d);d['short_citation']=short_citation(d);d['reference']=plain_text(citation)
    display_fields={'low_relevance','relevance_score','record_id','document_id','title','abstract','authors','publication_year','source','url',
        'evidence','decision','modeled','notes','assignment','short_citation','reference'}
    data={'manifest':manifest,'model':model_manifest if current else {},'status':'fitted'if current else 'pending_fit',
        'documents':[{k:v for k,v in d.items()if k in display_fields}for d in documents],
        'topics':topics,'reviews':reviews,'network':{'nodes':nodes,'edges':edges},
        'semantic_network':{'edges':semantic_edges},'semantic_audit':{k:v for k,v in semantic.items()if k!='edges'},
        'topic_network':{'nodes':tnodes,'edges':tedges},'keyword_audit':audit,
        'effective_configuration':json.loads((out/'effective_configuration.json').read_text()) if current else {},
        'outliers':sum(int(r.get('topic_id',-1))==-1 for r in assignments.values())}
    write_json(DOCS/'argentina-data.json',data)
    write_csv(DOCS/'argentina-corpus.csv',[{'record_id':r['record_id'],'document_id':r['document_id'],'year':r['publication_year'],
        'title':r['title'],'source':r['source'],'territorial_decision':r['decision'],
        'territorial_evidence':json.dumps(r['evidence'],ensure_ascii=False),'topic_id':r['assignment'].get('topic_id','')}for r in documents if r['modeled']])
    print(f"Argentina: {len(nodes)} candidates, {len(topics)} topics, {len(edges)} lexical links; {data['status']}")

def main():
    p=argparse.ArgumentParser();p.add_argument('--mode',choices=['render','all'],default='render');args=p.parse_args()
    settings=json.loads(Path('config/argentina_analysis.json').read_text())
    documents,corpus,manifest,reviews=prepare(settings)
    if args.mode=='all':fit(settings)
    render(documents,corpus,manifest,reviews)

if __name__=='__main__': main()
