import json, re

with open('docs/fulltext_knowledge_base.json', encoding='utf-8') as f:
    kb = json.load(f)

def dynamic_notebook_synthesis(query):
    clean = query.lower()
    tokens = [w for w in re.split(r'\W+', clean) if len(w) >= 3 and w not in ['que', 'por', 'del', 'los', 'las', 'una', 'uno', 'para', 'con', 'como', 'entiende', 'llama', 'significa']]
    
    matches = []
    for doc in kb:
        score = 0
        t = doc.get('title', '')
        a = doc.get('authors', '')
        abs_text = doc.get('abstract', '')
        pars = doc.get('paragraphs', [])
        all_text = ' '.join(pars) if pars else abs_text
        
        t_low = t.lower()
        all_low = all_text.lower()
        
        # Check whole phrase
        if clean in t_low or clean in all_low:
            score += 30
            
        for tok in tokens:
            if tok in t_low: score += 10
            if tok in a.lower(): score += 5
            count_in_text = all_low.count(tok)
            score += min(count_in_text * 2, 20)
            
        if score > 0:
            # Find best matching paragraph
            best_p = ""
            best_p_score = 0
            for p in (pars if pars else [abs_text]):
                p_low = p.lower()
                p_sc = sum(1 for tok in tokens if tok in p_low)
                if p_sc > best_p_score:
                    best_p_score = p_sc
                    best_p = p
            
            matches.append({
                'doc': doc,
                'score': score,
                'excerpt': best_p or abs_text or t
            })
            
    matches.sort(key=lambda x: x['score'], reverse=True)
    top = matches[:8]
    
    print(f"Consulta: '{query}' -> {len(matches)} obras encontradas en total. Top {len(top)} diversas:")
    for i, m in enumerate(top, 1):
        d = m['doc']
        print(f"[{i}] {d.get('title')} ({d.get('year')}) - {d.get('authors')}")
        print(f"    Cita literal extraída: {m['excerpt'][:180]}...\n")

dynamic_notebook_synthesis("que se entiende por gubernamentalidad")
