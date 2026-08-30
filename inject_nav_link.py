#!/usr/bin/env python3
"""Añade el enlace al Asistente IA Conversacional en la cabecera de docs/biblioteca.html."""
from pathlib import Path

p = Path('docs/biblioteca.html')
if not p.exists(): raise SystemExit('docs/biblioteca.html no existe')
html = p.read_text(encoding='utf-8')

# Actualizar el header de navegación en biblioteca.html
nav_link = '<a href="asistente_ia.html" style="background:#8957e5;color:#fff;padding:6px 12px;border-radius:6px;font-weight:700;margin-right:8px">💬 Asistente IA Conversacional</a>'

if 'href="asistente_ia.html"' not in html:
    html = html.replace('<a href="index.html">Dashboard</a>', '<a href="index.html">Dashboard</a>\n      ' + nav_link)

p.write_text(html, encoding='utf-8')
print('Enlace a asistente_ia.html agregado en la cabecera de docs/biblioteca.html.')
