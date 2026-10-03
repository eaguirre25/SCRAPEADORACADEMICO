"""Inspectable lexical document network; no model fitting or publication deletion."""
import csv
import hashlib
import itertools
import math
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

PROFILES = {
    'exploratory': {'label': 'Exploratoria · ≥ 0,10', 'threshold': .10, 'min_shared': 2},
    'balanced': {'label': 'Intermedia · ≥ 0,20', 'threshold': .20, 'min_shared': 2},
    'strict': {'label': 'Estricta · ≥ 0,30', 'threshold': .30, 'min_shared': 2},
}
DEFAULT_PROFILE = 'balanced'

def normalize_label(value):
    return ' '.join(unicodedata.normalize('NFKC',str(value or '')).casefold().replace('–','-').replace('—','-').split())

def read_rules(path='config/keyword_thesaurus.csv'):
    rules={}
    with open(path,encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            key=normalize_label(row['alias'])
            if not key or row['action'] not in {'merge','exclude'}:
                raise ValueError('Invalid thesaurus rule')
            if key in rules and rules[key] != row:
                raise ValueError('Duplicated thesaurus alias: '+key)
            rules[key]=row
    return rules

def clean_keywords(raw,rules):
    retained=set();excluded=[];changes=[]
    for original in str(raw or '').split(';'):
        key=normalize_label(original)
        if not key:continue
        rule=rules.get(key)
        if rule and rule['action']=='exclude':
            excluded.append({'original':original.strip(),'reason':rule['reason']});continue
        canonical=normalize_label(rule['canonical']) if rule else key
        retained.add(canonical)
        if canonical!=key:changes.append({'original':original.strip(),'canonical':canonical})
    return sorted(retained),excluded,changes

def provenance(row):
    explicit=str(row.get('keyword_provenance') or '').strip()
    if explicit:return {'label':explicit,'status':'recorded'}
    if not str(row.get('keywords') or '').strip():return {'label':'Sin etiquetas en el registro','status':'missing'}
    source=str(row.get('source') or '')
    if '|' in source:return {'label':'Fuentes combinadas; origen del campo sin trazabilidad','status':'unknown'}
    if source=='OpenAlex':return {'label':'OpenAlex · etiquetas de indexación; campo original no conservado','status':'inferred'}
    return {'label':'Metadatos del proveedor; autoría de las palabras no comprobada','status':'unknown'}

def build_network(records,rules):
    ids=[str(r.get('record_id') or f'record-{i}') for i,r in enumerate(records)]
    if len(ids)!=len(set(ids)):raise ValueError('Document identifiers must be unique')
    order=sorted(range(len(records)),key=lambda i:ids[i]);ordered=[records[i]for i in order];ids=[ids[i]for i in order]
    cleaned={};stats=Counter();provenance_counts=Counter();source_stats={};raw_counts=Counter();clean_counts=Counter();exclusions=Counter();changes=Counter()
    for key,row in zip(ids,ordered):
        kws,excluded,merged=clean_keywords(row.get('keywords'),rules);p=provenance(row)
        cleaned[key]={'keywords':kws,'excluded':excluded,'changes':merged,'provenance':p}
        stats['records']+=1;stats['with_raw_keywords']+=bool(str(row.get('keywords')or'').strip());stats['with_clean_keywords']+=bool(kws)
        provenance_counts[p['label']]+=1
        source=row.get('source')or'Sin fuente';ss=source_stats.setdefault(source,{'records':0,'with_raw_keywords':0,'with_clean_keywords':0});ss['records']+=1;ss['with_raw_keywords']+=bool(str(row.get('keywords')or'').strip());ss['with_clean_keywords']+=bool(kws)
        raw_counts.update(set(normalize_label(t)for t in str(row.get('keywords')or'').split(';')if normalize_label(t)));clean_counts.update(kws)
        exclusions.update(sorted(set(x['original']for x in excluded)));changes.update(sorted(set((x['original'],x['canonical'])for x in merged)))
    n=stats['with_clean_keywords'];idf={kw:math.log((n+1)/(df+1))+1 for kw,df in clean_counts.items()}
    sets=[set(cleaned[key]['keywords'])for key in ids];totals=[sum(idf[t]for t in sorted(kws))for kws in sets]
    inverted=defaultdict(list)
    for i,kws in enumerate(sets):
        for kw in sorted(kws):inverted[kw].append(i)
    shared_counts=Counter();shared_weights=defaultdict(float)
    for kw,items in sorted(inverted.items()):
        for pair in itertools.combinations(items,2):shared_counts[pair]+=1;shared_weights[pair]+=idf[kw]
    candidates=[]
    for (a,b),shared in sorted(shared_counts.items()):
        if shared<2:continue
        intersection=shared_weights[a,b];den=totals[a]+totals[b]-intersection
        score=intersection/den if den else 0;jaccard=shared/(len(sets[a])+len(sets[b])-shared)
        if score>=.10 or jaccard>=.10:
            candidates.append({'source':a,'target':b,'weight':round(score,6),'shared_count':shared,'shared_keywords':sorted(sets[a]&sets[b]),'jaccard':round(jaccard,6)})
    variants={}
    profiles={**PROFILES,'jaccard_control':{'label':'Jaccard simple · ≥ 0,20','threshold':.20,'min_shared':2}}
    for profile,p in profiles.items():
        metric='jaccard'if profile=='jaccard_control'else'weight'
        # Use the original score for threshold comparisons (not its rounded export).
        edges=[]
        for e in candidates:
            a,b=e['source'],e['target'];inter=shared_weights[a,b]
            score=e['shared_count']/(len(sets[a])+len(sets[b])-e['shared_count']) if metric=='jaccard'else inter/(totals[a]+totals[b]-inter)
            if score+1e-12>=p['threshold']:edges.append({**e,'weight':round(score,6)})
        variants[profile]=edges
    audit={'schema':'keyword-network-v1','default_profile':DEFAULT_PROFILE,'profiles':profiles,'coverage':dict(stats),'by_source':source_stats,'provenance':dict(provenance_counts),'limitations':['La procedencia exacta de las etiquetas históricas no quedó registrada; la fuente del registro solo permite una inferencia.','Las equivalencias y exclusiones del diccionario son propuestas revisables, no validaciones humanas.','Las distancias D3 son geométricas; los grupos STM/BERTopic son una capa independiente.','La falta de etiquetas limita la cobertura y puede producir sesgos por fuente e idioma.'],
        'method':{'name':'Jaccard ponderado por IDF','formula':'sum(IDF de términos compartidos) / sum(IDF de términos de la unión)','idf':'log((N con etiquetas limpias + 1) / (frecuencia documental + 1)) + 1','min_shared':2,'keyword_limit':None,'frequency_cutoff':None,'dictionary_sha256':hashlib.sha256(Path('config/keyword_thesaurus.csv').read_bytes()).hexdigest()},
        'excluded_terms':[{'term':k,'documents':v}for k,v in exclusions.most_common()],
        'merged_terms':[{'original':a,'canonical':b,'documents':v}for(a,b),v in changes.most_common()],
        'top_clean_terms':[{'term':k,'documents':v,'idf':round(idf[k],6)}for k,v in clean_counts.most_common(40)],'sensitivity':{}}
    for key,edges in variants.items():
        parent=list(range(len(ids)));sizes=[1]*len(ids);degrees=Counter()
        def find(i):
            while parent[i]!=i:parent[i]=parent[parent[i]];i=parent[i]
            return i
        for e in edges:
            a,b=e['source'],e['target'];degrees[a]+=1;degrees[b]+=1;x,y=find(a),find(b)
            if x!=y:parent[y]=x;sizes[x]+=sizes[y]
        components=Counter(find(i)for i in range(len(ids)));components_linked=sum(1 for c,s in components.items()if s>1)
        audit['sensitivity'][key]={'label':profiles[key]['label'],'edges':len(edges),'connected_records':len(degrees),'isolated_records':len(ids)-len(degrees),'components_with_links':components_linked,'largest_component':max(components.values(),default=0),'density':len(edges)/(len(ids)*(len(ids)-1)/2)if len(ids)>1 else 0}
    return ids,cleaned,variants,audit

def topic_agreement(ids,edges,assignments):
    eligible={i:assignments[key]for i,key in enumerate(ids)if assignments.get(key)not in {None,'','-1'}}
    pairs=[e for e in edges if e['source']in eligible and e['target']in eligible];same=sum(eligible[e['source']]==eligible[e['target']]for e in pairs)
    counts=Counter(eligible.values());n=len(eligible);baseline=sum(v*(v-1)for v in counts.values())/(n*(n-1))if n>1 else None
    return {'eligible_edges':len(pairs),'same_topic_edges':same,'same_topic_share':same/len(pairs)if pairs else None,'all_assigned_pair_same_topic_share':baseline,'note':'Comparación descriptiva; universos distintos y datos relacionados. No es prueba de validez ni causalidad.'}
