import argparse
import csv
import importlib.util
from pathlib import Path

import apa_citation

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("enrich_metadata", ROOT / "scripts" / "enrich_metadata.py")
em = importlib.util.module_from_spec(spec)
spec.loader.exec_module(em)

RECORD = {
    "record_id": "conicet:abp en la escuela secundaria::2022", "source": "CONICET Digital",
    "origin": "CONICET Digital", "document_type": "", "authors": "Berardi, Emanuel Angel; Corica, Ana Rosa",
    "title": "ABP en la escuela secundaria: análisis de la gestión de un proyecto",
    "abstract": "resumen", "keywords": "", "publication_year": "2022",
    "publication_date": "2022-08-04T18:08:32Z", "doi": "", "url": "http://hdl.handle.net/11336/164268",
    "openalex_id": "", "is_oa": "True", "pdf_url": "",
}


def openalex_work(title, authors, year, doi="https://doi.org/10.1234/abc"):
    return {
        "display_name": title, "publication_year": year, "publication_date": f"{year}-05-01", "doi": doi,
        "authorships": [{"author": {"display_name": a}} for a in authors], "type": "article",
        "primary_location": {"source": {"display_name": "Revista Educación", "type": "journal"}},
        "biblio": {"volume": "12", "issue": "3", "first_page": "45", "last_page": "67"},
        "keywords": [{"display_name": "Gestión escolar"}], "open_access": {"is_oa": True, "oa_url": ""},
        "id": "https://openalex.org/W1",
    }


class Resp:
    def __init__(self, payload, status=200, content=b"{}"):
        self.payload, self.status_code, self.content = payload, status, content

    def json(self):
        return self.payload


class FakeHttp:
    email = "test@example.com"
    failures = {}

    def __init__(self, works, crossref=None):
        self.works, self.crossref, self.calls = works, crossref or [], []

    def get(self, url, params=None, timeout=30):
        self.calls.append(url)
        if "conicet" in url:
            return None  # repositorio caído
        if "openalex" in url:
            return Resp({"results": self.works})
        if url.endswith("/works"):
            return Resp({"message": {"items": self.crossref}})
        return Resp({}, status=404)


def test_matching_rules():
    good = {"match_title": "ABP en la escuela secundaria: análisis de la gestión de un proyecto",
            "authors_list": ["Emanuel A. Berardi"], "found_year": "2021"}
    assert em.evaluate(RECORD, good)["status"] == "aceptado"
    assert em.evaluate(RECORD, {**good, "authors_list": ["Otra Persona"]})["status"] == "revisar"
    assert em.evaluate(RECORD, {**good, "found_year": "2024"})["status"] == "revisar"
    assert em.evaluate(RECORD, {**good, "match_title": "Liderazgo en hospitales"})["status"] == "descartado"


def test_apply_fills_only_missing_fields_and_fixes_year():
    row = dict(RECORD)
    result = {"doi": "10.1234/abc", "journal": "Revista Educación", "document_type": "article",
              "keywords": "Gestión escolar", "found_year": "2021", "found_date": "2021-05-01", "is_oa": "True"}
    changed = em.apply_to_row(row, result)
    assert row["doi"] == "10.1234/abc" and row["origin"] == "Revista Educación"
    assert row["publication_year"] == "2021" and row["title"] == RECORD["title"]
    assert row["authors"] == RECORD["authors"] and row["abstract"] == "resumen"
    assert set(changed) >= {"doi", "origin", "document_type", "keywords", "publication_year"}
    assert em.apply_to_row(row, result) == []  # idempotente


def run_with(tmp_path, monkeypatch, http, overrides=""):
    master = tmp_path / "master.csv"
    other = {**RECORD, "record_id": "10.9/x", "source": "OpenAlex", "title": "Otro"}
    em.write_csv(master, list(RECORD), [RECORD, other])
    monkeypatch.setattr(em, "MASTER", master)
    monkeypatch.setattr(em, "ENRICHMENT", tmp_path / "enrichment.csv")
    monkeypatch.setattr(em, "REPORT", tmp_path / "report.json")
    (tmp_path / "overrides.csv").write_text("record_id,decision,nota\n" + overrides, encoding="utf-8")
    monkeypatch.setattr(em, "OVERRIDES", tmp_path / "overrides.csv")
    args = argparse.Namespace(apply=True, retry_missing=False, offline=False, limit=0, pause=0, email="t@e.com")
    report = em.run(args, http_factory=lambda: http)
    with master.open(encoding="utf-8") as fh:
        rows = {r["record_id"]: r for r in csv.DictReader(fh)}
    return report, rows


def test_run_recovers_from_openalex_when_conicet_is_down(tmp_path, monkeypatch):
    http = FakeHttp([openalex_work(RECORD["title"], ["Emanuel Angel Berardi", "Ana Rosa Corica"], 2021)])
    report, rows = run_with(tmp_path, monkeypatch, http)
    row = rows[RECORD["record_id"]]
    assert report["targets"] == 1 and report["applied_records"] == 1 and not report["conicet_oai_available"]
    assert row["doi"] == "10.1234/abc" and row["origin"] == "Revista Educación" and row["publication_year"] == "2021"
    assert rows["10.9/x"]["doi"] == ""  # solo se tocan registros de CONICET
    with (tmp_path / "enrichment.csv").open(encoding="utf-8") as fh:
        entry = next(csv.DictReader(fh))
    assert entry["original_year"] == "2022" and entry["volume"] == "12" and entry["applied"] == "si"

    # Segunda corrida: usa la caché, no consulta y no cambia nada.
    http2 = FakeHttp([])
    report2, rows2 = run_with_existing(tmp_path, monkeypatch, http2)
    assert report2["queried_this_run"] == 0 and not http2.calls


def run_with_existing(tmp_path, monkeypatch, http):
    args = argparse.Namespace(apply=True, retry_missing=False, offline=False, limit=0, pause=0, email="t@e.com")
    return em.run(args, http_factory=lambda: http), None


def test_wrong_author_goes_to_review_and_override_accepts(tmp_path, monkeypatch):
    work = openalex_work(RECORD["title"], ["Persona Distinta"], 2021)
    report, rows = run_with(tmp_path, monkeypatch, FakeHttp([work]))
    assert report["status_counts"] == {"revisar": 1} and rows[RECORD["record_id"]]["doi"] == ""

    (tmp_path / "overrides.csv").write_text(
        f"record_id,decision,nota\n\"{RECORD['record_id']}\",aceptar,verificado a mano\n", encoding="utf-8")
    args = argparse.Namespace(apply=True, retry_missing=False, offline=True, limit=0, pause=0, email="t@e.com")
    em.run(args)
    with em.MASTER.open(encoding="utf-8") as fh:
        assert next(csv.DictReader(fh))["doi"] == "10.1234/abc"


def test_citation_uses_recovered_volume_issue_pages(tmp_path, monkeypatch):
    path = tmp_path / "enrichment.csv"
    em.write_csv(path, em.ENRICHMENT_FIELDS, [{"record_id": "r1", "applied": "si", "volume": "12", "issue": "", "pages": "45-67"}])
    monkeypatch.setattr(apa_citation, "ENRICHMENT_CSV", path)
    apa_citation._enriched_details.cache_clear()
    try:
        record = {"record_id": "r1", "authors": "Ana Pérez", "title": "Un estudio", "publication_year": "2021",
                  "origin": "Revista Educación", "document_type": "article"}
        citation = apa_citation.build_citation(record, "es")
        assert "*Revista Educación*, 12, 45–67." in citation.text
        assert "volumen" not in citation.missing and "paginas" not in citation.missing
        bare = apa_citation.build_citation({**record, "record_id": "otro"}, "es")
        assert "[vol]([num]), [pp.]" in bare.text
    finally:
        apa_citation._enriched_details.cache_clear()


class DownHttp(FakeHttp):
    def get(self, url, params=None, timeout=30):
        self.calls.append(url)
        return None


def test_network_failure_is_retried_not_cached_as_missing(tmp_path, monkeypatch):
    report, rows = run_with(tmp_path, monkeypatch, DownHttp([]))
    assert report["status_counts"] == {"error": 1} and rows[RECORD["record_id"]]["doi"] == ""
    http = FakeHttp([openalex_work(RECORD["title"], ["Emanuel Angel Berardi"], 2021)])
    report2, _ = run_with_existing(tmp_path, monkeypatch, http)
    assert report2["queried_this_run"] == 1 and report2["applied_records"] == 1
