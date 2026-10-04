import json
from pathlib import Path

import inject_pwa

ROOT = Path(__file__).resolve().parents[1]


def test_inject_is_idempotent_and_marks_page(tmp_path):
    page = tmp_path / "biblioteca.html"
    page.write_text('<!doctype html>\n<html lang="es"><head><title>x</title></head><body></body></html>', encoding="utf-8")

    assert inject_pwa.inject(page)
    first = page.read_text(encoding="utf-8")
    assert inject_pwa.inject(page)
    second = page.read_text(encoding="utf-8")

    assert first == second
    assert second.count("<!-- pwa:start -->") == 1
    assert '<link rel="manifest" href="manifest.webmanifest">' in second
    assert second.count('data-page="biblioteca"') == 1


def test_page_without_head_is_left_untouched(tmp_path):
    page = tmp_path / "fragmento.html"
    page.write_text("<p>sin cabecera</p>", encoding="utf-8")
    assert not inject_pwa.inject(page)
    assert page.read_text(encoding="utf-8") == "<p>sin cabecera</p>"


def test_manifest_references_existing_icons():
    manifest = json.loads((ROOT / "docs" / "manifest.webmanifest").read_text(encoding="utf-8"))
    assert manifest["display"] == "standalone"
    for icon in manifest["icons"]:
        assert (ROOT / "docs" / icon["src"]).is_file()
    for asset in ("sw.js", "pwa.js", "mobile.css", "icons/apple-touch-icon.png"):
        assert (ROOT / "docs" / asset).is_file()
