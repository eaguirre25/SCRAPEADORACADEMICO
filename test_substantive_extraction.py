import json, re

with open('docs/fulltext_knowledge_base.json', encoding='utf-8') as f:
    kb = json.load(f)

def clean_substantive_paragraphs(doc):
    substantive = []
    t_clean = doc.get('title', '').strip().lower()
    
    for p in doc.get('paragraphs', []):
        p_strip = p.strip()
        p_low = p_strip.lower()
        
        # Skip if too short
        if len(p_strip) < 120:
            continue
            
        # Skip if it's just title repetition or metadata header
        if p_low.startswith('doi') or p_low.startswith('issn') or p_low.startswith('vol.') or p_low.startswith('http'):
            continue
        if 'resumo:' in p_low or 'abstract:' in p_low:
            # Clean abstract prefix
            p_strip = re.sub(r'^(resumen|resumo|abstract)\s*:\s*', '', p_strip, flags=re.IGNORECASE)
            
        # Check if it has actual sentences
        if '.' in p_strip and len(p_strip.split()) > 20:
            substantive.append(p_strip)
            
    if not substantive and doc.get('abstract'):
        substantive.append(doc.get('abstract'))
    return substantive

print("=== PROBANDO EXTRACCIÓN SUSTANTIVA LIMPIA ===")
test_docs = [d for d in kb if 'politica' in d.get('title', '').lower()][:5]
for d in test_docs:
    print("TITULO:", d.get('title'))
    pars = clean_substantive_paragraphs(d)
    print(f"Párrafos sustantivos válidos: {len(pars)}")
    if pars:
        print("MUESTRA SUSTANTIVA (200 chars):", pars[0][:200])
    print("-" * 50)
