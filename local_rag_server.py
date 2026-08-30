# Servidor Local RAG & Asistente IA para Scraping Académico
# Ejecuta un endpoint local compatible con OpenAI en http://localhost:8000/v1/chat/completions

import json, re, glob
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

print("Cargando Base de Conocimiento de Texto Completo...")
KB = []
kb_file = Path('docs/fulltext_knowledge_base.json')
if kb_file.exists():
    KB = json.loads(kb_file.read_text(encoding='utf-8'))
print(f"Base de conocimiento cargada: {len(KB)} obras.")

@app.route('/v1/chat/completions', methods=['POST'])
def chat_completions():
    data = request.get_json(force=True)
    messages = data.get('messages', [])
    user_prompt = messages[-1]['content'] if messages else ""
    
    # RAG Search
    clean_prompt = user_prompt.lower()
    tokens = [w for w in re.split(r'\W+', clean_prompt) if len(w) >= 3]
    
    results = []
    for doc in KB:
        score = 0
        t = doc.get('title', '').lower()
        a = doc.get('authors', '').lower()
        txt = doc.get('fulltext_sample', doc.get('abstract', '')).lower()
        
        for tok in tokens:
            if tok in t: score += 5
            if tok in a: score += 5
            if tok in txt: score += 2
            
        if score > 0:
            results.append((score, doc))
            
    results.sort(key=lambda x: x[0], reverse=True)
    top = results[:6]
    
    response_text = f"⚡ ANÁLISIS IA RAG LOCAL SOBRE TU CORPUS ({len(KB)} OBRAS)\n\n"
    response_text += f"Pregunta: \"{user_prompt}\"\n\n"
    
    if top:
        response_text += "Basado estrictamente en las fuentes de tu investigación:\n\n"
        for i, (score, d) in enumerate(top, 1):
            response_text += f"[{i}] {d.get('title')} ({d.get('year')}) - Autor/es: {d.get('authors')}\n"
            sample = d.get('fulltext_sample', d.get('abstract', ''))[:300]
            response_text += f"    Fragmento Literal: \"{sample}...\"\n\n"
    else:
        response_text += "No se hallaron pasajes exactos para esta consulta en las obras indexadas."
        
    return jsonify({
        "choices": [{
            "message": {
                "role": "assistant",
                "content": response_text
            }
        }]
    })

if __name__ == '__main__':
    print("Servidor RAG Local escuchando en http://localhost:8000/v1...")
    app.run(host='0.0.0.0', port=8000)
