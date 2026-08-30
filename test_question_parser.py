import re

def extract_clean_concept(text):
    clean = text.strip()
    # Remover prefijos de preguntas conversacionales comunes en español
    patterns = [
        r'^(a\s+que\s+se\s+llama|a\s+que\s+se\s+refiere|que\s+es|que\s+significa|que\s+se\s+entiende\s+por|como\s+se\s+define|definicion\s+de|definir|explicar|quiero\s+una\s+definicion\s+de|dame\s+una\s+definicion\s+de)\s+',
        r'^(a\s+que\s+llamamos|a\s+que\s+se\s+denomina|que\s+implica)\s+'
    ]
    for pat in patterns:
        clean = re.sub(pat, '', clean, flags=re.IGNORECASE)
    
    # Capitalizar apropiadamente
    clean = clean.strip(' ?!.;:')
    return clean.title() if clean else text

test_queries = [
    "A QUE SE LLAMA POLITICA EDUCATIVA",
    "que es la gubernamentalidad",
    "a que se refiere la gestion escolar",
    "quiero una definicion de liderazgo directivo",
    "definir inclusion digital"
]

print("=== PRUEBA DE PARSER DE PREGUNTAS ===")
for q in test_queries:
    concept = extract_clean_concept(q)
    print(f"Original: '{q}'  -->  Concepto Extraído: '{concept}'")
