import json, re

with open('docs/fulltext_knowledge_base.json', encoding='utf-8') as f:
    kb = json.load(f)

prompt = "quiero una definicion del concepto de gubernamentalidad"

clean_prompt = prompt.lower()
tokens = [w for w in re.split(r'\W+', clean_prompt) if len(w) >= 3 and w not in ['quiero', 'una', 'definicion', 'del', 'concepto', 'de']]

matches = []
for doc in kb:
    score = 0
    t = doc.get('title', '').lower()
    a = doc.get('authors', '').lower()
    txt = doc.get('fulltext_sample', doc.get('abstract', '')).lower()
    pars = doc.get('paragraphs', [])
    
    if clean_prompt in t or clean_prompt in txt: score += 20
    for tok in tokens:
        if tok in t: score += 10
        if tok in a: score += 8
        if tok in txt: score += 4
        for p in pars:
            if tok in p.lower(): score += 2
            
    if score > 0:
        matches.append((score, doc))

matches.sort(key=lambda x: x[0], reverse=True)
top = matches[:6]

print(f"Top coincidencia para '{prompt}': {len(top)} documentos encontrados.\n")
for i, (sc, d) in enumerate(top, 1):
    print(f"[{i}] {d.get('title')} ({d.get('year')}) - Score: {sc}")
    print(f"    Autores: {d.get('authors')}")
    print(f"    Muestra: {d.get('fulltext_sample', d.get('abstract', ''))[:200]}...\n")
