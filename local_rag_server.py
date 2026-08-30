#!/usr/bin/env python3
"""Servidor Local RAG & Asistente IA para Scraping Académico.
Conecta la web de la Biblioteca directamente con Ollama (Qwen 2.5 7B / DeepSeek-R1) resolviendo problemas de CORS e HTTPS.
"""
import json, re, urllib.request
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

@app.route('/v1/chat/completions', methods=['POST', 'OPTIONS'])
def chat_completions():
    if request.method == 'OPTIONS':
        return jsonify({'status': 'ok'})

    data = request.get_json(force=True) or {}
    messages = data.get('messages', [])
    user_prompt = messages[-1]['content'] if messages else ""
    target_model = data.get('model', 'qwen2.5:7b')
    
    # 1. Recuperar los textos más relevantes de las 2.124 obras
    clean_prompt = user_prompt.lower()
    tokens = [w for w in re.split(r'\W+', clean_prompt) if len(w) >= 3]
    
    scored = []
    for doc in KB:
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
    top = [x[1] for x in scored[:7]]
    
    context_str = "\n\n".join([
        f"[Fuente {i+1}] Título: \"{d.get('title')}\" | Autores: {d.get('authors')} | Año: {d.get('year')}\n"
        f"Texto Extraído: \"{(d.get('paragraphs', [d.get('abstract','')])[0] if d.get('paragraphs') else d.get('abstract',''))[:450]}\""
        for i, d in enumerate(top)
    ])
    
    sys_prompt = f"Sos un experto docente universitario estilo NotebookLM. El usuario pregunta: \"{user_prompt}\".\n\nAnalizá atentamente estos textos de su corpus:\n{context_str}\n\nREGLAS OBLIGATORIAS:\n1. Respondé conversacionalmente en español con una definición extensa y rigurosa.\n2. Explicá cómo aborda el tema cada autor.\n3. Citá frases textuales entre comillas de los textos."

    # 2. Consultar a Ollama local (qwen2.5:7b o deepseek-r1:1.5b)
    ollama_payload = {
        "model": "qwen2.5:7b" if "qwen" in target_model else "deepseek-r1:1.5b",
        "messages": [{"role": "user", "content": sys_prompt}],
        "stream": False
    }
    
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:11434/v1/chat/completions",
            data=json.dumps(ollama_payload).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            res_data = json.loads(resp.read().decode('utf-8'))
            reply_text = res_data['choices'][0]['message']['content']
            return jsonify({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": reply_text
                    }
                }]
            })
    except Exception as e:
        print("Error consultando a Ollama:", e)
        return jsonify({
            "error": "Ollama local no respondió. Verificá que Ollama esté ejecutándose.",
            "details": str(e)
        }), 500

if __name__ == '__main__':
    print("="*60)
    print("🚀 Servidor RAG Local para Asistente IA iniciado en http://127.0.0.1:8000")
    print("Conecta la web con Ollama (Qwen 2.5 7B / DeepSeek-R1)")
    print("="*60)
    app.run(host='127.0.0.1', port=8000)
