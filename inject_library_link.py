#!/usr/bin/env python3
"""Inserta un acceso visible a la biblioteca en el dashboard generado."""
from pathlib import Path

INDEX = Path("docs/index.html")

if not INDEX.exists():
    raise SystemExit("No existe docs/index.html")

html = INDEX.read_text(encoding="utf-8")

if 'href="biblioteca.html"' not in html:
    # Admite el texto actual y el anterior (sin tildes) del enlace a la tabla.
    old = next((c for c in ('<a href="articulos.html">Trabajar con la tabla de artículos</a>',
                            '<a href="articulos.html">Trabajar con tabla de articulos</a>') if c in html),
               '<a href="articulos.html">Trabajar con la tabla de artículos</a>')
    new = (
        old +
        ' &middot; '
        '<a href="biblioteca.html" style="display:inline-block;padding:7px 12px;'
        'border:1px solid #58a6ff;border-radius:8px;background:#1f6feb;color:#fff;'
        'font-weight:700;text-decoration:none;margin-left:4px">'
        '📚 Biblioteca y fichado</a>'
    )
    if old not in html:
        raise SystemExit("No se encontró el enlace de tabla esperado en el encabezado")
    html = html.replace(old, new, 1)
    INDEX.write_text(html, encoding="utf-8")
    print("Acceso a biblioteca insertado en dashboard")
else:
    print("El dashboard ya contiene acceso a biblioteca")
