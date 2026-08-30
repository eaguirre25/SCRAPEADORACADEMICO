#!/usr/bin/env python3
"""Servidor RAG Local liviano para conectar la web con Ollama (DeepSeek-R1 / Qwen 2.5)."""
import json, re, urllib.request
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path

KB = []
kb_file = Path('docs/fulltext_knowledge_base.json')
if kb_file.exists():
    with open(kb_file, 'r', encoding='utf-8') as f:
        KB = json.load(f)
print("Base de conocimiento cargada exitosamente.")

class RAGHandler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()

    def do_POST(self):
        length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(length).decode('utf-8')
        try:
            data = json.loads(body)
        except Exception:
            data = {}

        user_prompt = ""
        messages = data.get('messages', [])
        if messages:
            user_prompt = messages[-1].get('content', '')

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
        top = [x[1] for x in scored[:6]]
        
        context_str = "\n\n".join([
            f"[Fuente {i+1}] Título: \"{d.get('title')}\" | Autores: {d.get('authors')} | Año: {d.get('year')}\n"
            f"Texto Extraído: \"{(d.get('paragraphs', [d.get('abstract','')])[0] if d.get('paragraphs') else d.get('abstract',''))[:400]}\""
            for i, d in enumerate(top)
        ])
        
        sys_prompt = f"Sos un experto docente universitario estilo NotebookLM. El usuario pregunta: \"{user_prompt}\".\n\nAnalizá atentamente estos textos de su corpus:\n{context_str}\n\nREGLAS OBLIGATORIAS:\n1. Respondé conversacionalmente en español con una definición extensa y rigurosa.\n2. Explicá cómo aborda el tema cada autor.\n3. Citá frases textuales entre comillas de los textos."

        ollama_payload = {
            "model": "deepseek-r1:1.5b",
            "messages": [{"role": "user", "content": sys_prompt}],
            "stream": False
        }
        
        reply_text = ""
        try:
            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/chat",
                data=json.dumps(ollama_payload).encode('utf-8'),
                headers={'Content-Type': 'application/json'}
            )
            with urllib.request.urlopen(req, timeout=90) as resp:
                res_data = json.loads(resp.read().decode('utf-8'))
                reply_text = res_data['message']['content']
        except Exception as e:
            reply_text = f"Ollama local error: {e}"

        response_payload = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": reply_text
                }
            }]
        }

        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(response_payload).encode('utf-8'))

if __name__ == '__main__':
    server = HTTPServer(('127.0.0.1', 8000), RAGHandler)
    print("Servidor RAG Local escuchando en http://127.0.0.1:8000")
    server.serve_forever()
