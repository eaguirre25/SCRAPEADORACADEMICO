import importlib.util
import json
from pathlib import Path

spec=importlib.util.spec_from_file_location('argentina',Path(__file__).resolve().parents[1]/'scripts/run_argentina_analysis.py')
argentina=importlib.util.module_from_spec(spec);spec.loader.exec_module(argentina)
settings=json.loads((Path(__file__).resolve().parents[1]/'config/argentina_analysis.json').read_text())

def record(title='Estudio de escuelas en Argentina'):
    return {'record_id':'test-1','title':title,'abstract':'Trabajo de campo sobre dirección escolar y organización de escuelas secundarias.','publication_year':'2024'}

def test_year_and_geographic_decisions_are_separate():
    r=record();check=argentina.screening(r,settings,{})
    assert check['modeled'] and check['decision']=='pending'
    assert check['evidence'][0]['field']=='title'
    r['publication_year']='2019'
    assert not argentina.screening(r,settings,{'test-1':{'decision':'include'}})['modeled']
    r['publication_year']='2026'
    assert argentina.screening(r,settings,{})['modeled']
    r['publication_year']='2027'
    assert not argentina.screening(r,settings,{})['modeled']

def test_repository_is_not_study_country_and_missing_is_reviewable():
    r=record('Gestión de escuelas y sus directores');r['source']='CONICET'
    assert not argentina.screening(r,settings,{})['modeled']
    assert argentina.screening(r,settings,{'test-1':{'decision':'include'}})['modeled']
    assert not argentina.screening(record(),settings,{'test-1':{'decision':'exclude'}})['modeled']
    assert not argentina.screening(record(),settings,{'test-1':{'decision':'uncertain'}})['modeled']

def test_exported_network_and_model_account_for_every_candidate():
    path=Path('docs/argentina-data.json')
    if not path.exists(): return
    data=json.loads(path.read_text());candidates=[d for d in data['documents']if d['modeled']]
    assert len(candidates)==data['manifest']['modeled_candidates']==len(data['network']['nodes'])
    assert len({d['document_id']for d in candidates})==len(candidates)
    assert all(2020<=int(d['publication_year'])<=2026 for d in candidates)
    if data['status']=='fitted':
        assert sum(int(t['document_count'])for t in data['topics'])+data['outliers']==len(candidates)
        assert all(d['assignment'].get('model')=='BERTopic-ARGENTINA-2020-2026' for d in candidates)
        assert len(data['model']['stability'])==5
        assert len(data['model']['sensitivity'])==4
    for edge in data['network']['edges']:
        assert 0<=edge['source']<len(candidates) and 0<=edge['target']<len(candidates)
        assert edge['shared_count']>=2 and edge['weight']>=.199999
    ids=set(range(len(data['topic_network']['nodes'])))
    assert all(e['source']in ids and e['target']in ids and e['weight']>=.35 for e in data['topic_network']['edges'])

def test_semantic_links_require_reciprocal_neighbors_and_no_self_links():
    import numpy as np
    # A/B are mutual closest; C's closest is B, whose closest is A.
    x=np.array([[1.,0.],[.99,.1],[.8,.6]])
    result=argentina.semantic_neighbors(x,['A','B','C'],neighbors=1,minimum=.7)
    assert [(e['source'],e['target'])for e in result['edges']]==[('A','B')]
    assert len(result['sensitivity'])==9
