#!/usr/bin/env python3
"""Actualiza en docs/asistente_ia.html las cifras de obras conectadas.

La página trae los totales escritos en el HTML («2.124 obras», «2.087 artículos»,
«37 libros»). Se recalculan desde docs/fulltext_knowledge_base.json para que no
queden números de una versión anterior del corpus. Es idempotente.
"""
import json
import re
from pathlib import Path

KB = Path("docs/fulltext_knowledge_base.json")
PAGE = Path("docs/asistente_ia.html")


def fmt(n: int) -> str:
    return f"{n:,}".replace(",", ".")


def update(html: str, corpus: int, teoricos: int) -> str:
    total = corpus + teoricos
    html = re.sub(r"\b\d{1,3}(?:\.\d{3})*(?=\s*(?:Obras|obras|FUENTES|fuentes|materiales)\b)", fmt(total), html)
    html = re.sub(r"(<b>)\d{1,3}(?:\.\d{3})*(</b>\s*Artículos)", rf"\g<1>{fmt(corpus)}\g<2>", html)
    html = re.sub(r"(<b>)\d{1,3}(?:\.\d{3})*(</b>\s*Libros)", rf"\g<1>{fmt(teoricos)}\g<2>", html)
    return html


def main() -> None:
    kb = json.loads(KB.read_text(encoding="utf-8"))
    corpus = sum(1 for r in kb if r.get("collection") == "corpus")
    teoricos = sum(1 for r in kb if r.get("collection") == "teoricos")
    html = PAGE.read_text(encoding="utf-8")
    new = update(html, corpus, teoricos)
    PAGE.write_text(new, encoding="utf-8")
    print(f"Asistente IA: {fmt(corpus)} artículos + {fmt(teoricos)} textos teóricos = {fmt(corpus + teoricos)} obras")


if __name__ == "__main__":
    main()
