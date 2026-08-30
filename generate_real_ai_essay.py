import json, re, urllib.request

with open('docs/fulltext_knowledge_base.json', encoding='utf-8') as f:
    kb = json.load(f)

prompt = "quiero una definicion elaborada del concepto de gubernamentalidad"

clean_prompt = prompt.lower()
tokens = [w for w in re.split(r'\W+', clean_prompt) if len(w) >= 3 and w not in ['quiero', 'una', 'definicion', 'elaborada', 'del', 'concepto', 'de']]

scored = []
for doc in kb:
    score = 0
    t = doc.get('title', '').lower()
    a = doc.get('authors', '').lower()
    txt = doc.get('fulltext_sample', doc.get('abstract', '')).lower()
    pars = doc.get('paragraphs', [])
    
    for tok in tokens:
        if tok in t: score += 8
        if tok in a: score += 6
        if tok in txt: score += 3
        for p in pars:
            if tok in p.lower(): score += 2
            
    if score > 0:
        scored.append((score, doc))

scored.sort(key=lambda x: x[0], reverse=True)
top = [x[1] for x in scored[:6]]

print(f"Buscando en {len(kb)} obras... Encontradas {len(top)} obras principales.")

context = ""
for i, d in enumerate(top, 1):
    sample = (d.get('paragraphs', [d.get('abstract','')])[0] if d.get('paragraphs') else d.get('abstract',''))[:500]
    context += f"[Obra {i}] Título: {d.get('title')} | Autores: {d.get('authors')} ({d.get('year')})\nPasaje Extraído: \"{sample}\"\n\n"

print("\n=== CONTEXTO EXTRAÍDO DE LOS 2.124 MATERIALES ===")
print(context[:600])
