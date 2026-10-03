import math
from keyword_network import build_network, clean_keywords, read_rules, provenance, topic_agreement

def test_document_similarity_is_weighted_and_requires_two_terms():
    records=[{'record_id':'a','keywords':'alpha;beta;gamma'},{'record_id':'b','keywords':'alpha;beta'},{'record_id':'c','keywords':'alpha;delta'},{'record_id':'d','keywords':''}]
    ids,cleaned,variants,audit=build_network(records,read_rules())
    edge=variants['balanced'][0]
    expected=(1+(math.log(4/3)+1))/(1+(math.log(4/3)+1)+(math.log(4/2)+1))
    assert abs(edge['weight']-expected)<1e-6
    assert edge['shared_keywords']==['alpha','beta']
    assert len(variants['balanced'])==1
    assert audit['coverage']['records']==4
    assert audit['sensitivity']['balanced']['isolated_records']==2
    assert topic_agreement(ids,variants['balanced'],{'a':'0','b':'0','c':'1'})['same_topic_share']==1

def test_dictionary_preserves_conceptual_distinctions_and_missingness():
    rules=read_rules()
    terms,excluded,changes=clean_keywords('School leadership; gestión escolar; Dirección escolar; Instructional leadership; Pedagogical leadership; Work (physics); SCHOOL LEADERSHIP',rules)
    assert len(terms)==5
    assert set(terms)=={'liderazgo escolar','gestión escolar','dirección escolar','liderazgo instruccional','liderazgo pedagógico'}
    assert excluded[0]['original']=='Work (physics)'
    assert clean_keywords('',rules)==([],[],[])
    assert provenance({'source':'OpenAlex','keywords':'x'})['status']=='inferred'
    assert provenance({'source':'OpenAlex | CONICET Digital','keywords':'x'})['status']=='unknown'

def test_no_frequency_or_node_or_keyword_cap():
    records=[{'record_id':f'p{i:02}','keywords':'alpha;beta'}for i in range(42)]
    ids,_,variants,_=build_network(records,read_rules())
    assert len(ids)==42
    assert len(variants['strict'])==861
    assert all(e['weight']==1 for e in variants['strict'])
    assert len(clean_keywords(';'.join('term'+str(i)for i in range(20)),{})[0])==20
