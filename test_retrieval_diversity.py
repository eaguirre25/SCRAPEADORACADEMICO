import json, re

with open('docs/fulltext_knowledge_base.json', encoding='utf-8') as f:
    kb = json.load(f)

queries = [
    "liderazgo directivo",
    "inclusion escolar",
    "evaluacion y acreditacion",
    "emociones y afectos en directores",
    "escuela secundaria y gestion",
    "politica educativa"
]

for q in queries:
    tokens = [w for w in re.split(r'\W+', q.lower()) if len(w) >= 3]
    cnt = 0
    sample_titles = []
    for doc in kb:
        t = doc.get('title', '').lower()
        txt = doc.get('fulltext_sample', doc.get('abstract', '')).lower()
        if any(tok in t or tok in txt for tok in tokens):
            cnt += 1
            if len(sample_titles) < 3:
                sample_titles.append(f"{doc.get('title')[:60]}... ({doc.get('year')})")
    print(f"Query '{q}': {cnt} obras coincidentes.")
    for st in sample_titles:
        print(f"   -> {st}")
    print()
