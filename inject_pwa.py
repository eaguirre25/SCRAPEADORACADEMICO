#!/usr/bin/env python3
"""Convierte el sitio de docs/ en una app instalable en el celular (PWA).

Agrega a cada página HTML el manifiesto, los íconos, la hoja de estilos móvil
y el registro del service worker. Es idempotente: se puede ejecutar después de
cada regeneración del dashboard sin duplicar etiquetas.
"""
import re
from pathlib import Path

DOCS = Path('docs')
MARKER = '<!-- pwa:start -->'
HEAD = """<!-- pwa:start -->
<link rel="manifest" href="manifest.webmanifest">
<meta name="theme-color" content="#0D1117">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Dirección Escolar">
<link rel="icon" type="image/png" sizes="192x192" href="icons/icon-192.png">
<link rel="apple-touch-icon" href="icons/apple-touch-icon.png">
<link rel="stylesheet" href="mobile.css">
<script src="pwa.js" defer></script>
<!-- pwa:end -->
"""
BLOCK = re.compile(r'<!-- pwa:start -->.*?<!-- pwa:end -->\n?', re.S)


def inject(path: Path) -> bool:
    html = path.read_text(encoding='utf-8')
    original = html
    html = BLOCK.sub('', html)
    if '</head>' not in html:
        return False
    html = html.replace('</head>', HEAD + '</head>', 1)
    page = path.stem
    html, n = re.subn(r'<html\b([^>]*?)\sdata-page="[^"]*"', r'<html\1', html, count=1)
    html = re.sub(r'<html\b', f'<html data-page="{page}"', html, count=1)
    if html != original:
        path.write_text(html, encoding='utf-8')
    return True


def main() -> None:
    if not DOCS.exists():
        raise SystemExit('docs/ no existe')
    done = [p.name for p in sorted(DOCS.glob('*.html')) if inject(p)]
    print('App móvil (PWA) incorporada en: ' + ', '.join(done))


if __name__ == '__main__':
    main()
