import csv
import os
from pathlib import Path

import pytest

pytest.importorskip("openpyxl")
import relevance_filter as rf


def status(title, abstract="", source="OpenAlex", keywords=""):
    row = {"title": title, "abstract": abstract, "source": source, "keywords": keywords}
    st, score, reason, evidence = rf.classify_relevance(row)
    if st == "revisar":
        second = rf.second_review(row)[0]
        st = {"promover": "alta", "descartar": "rechazada"}.get(second, "revisar")
    return st


def test_spanish_adjective_principal_is_not_a_school_principal():
    abstract = ("El objetivo principal es analizar el vínculo entre intelectuales y el peronismo. "
                "Se discuten escuelas de pensamiento marxistas.")
    assert status("Peronismo, marxismo e intelectuales de izquierda", abstract, "CONICET Digital") == "rechazada"
    assert status("Obesity medication", "aging rewires a principal brain pathway; school") == "rechazada"


def test_english_school_principal_is_a_role():
    assert status("Teacher retention", "We surveyed school principals and teachers in 40 schools.") == "alta"
    assert status("Novice leaders", "The principal of each school was interviewed by teachers.") == "alta"


def test_management_must_be_near_school_not_anywhere():
    far = ("Se estudia la gestión integrada de cuencas hidrográficas y sus indicadores de calidad ambiental "
           "en diversas regiones productivas del país durante varias décadas, con datos satelitales y de campo. "
           "Como actividad de extensión se visitó una escuela rural.")
    assert status("Calidad del agua en cuencas pampeanas", far, "CONICET Digital") == "rechazada"
    near = "Analizamos cómo la gestión de la escuela secundaria organiza el trabajo de los docentes."
    assert status("Organización institucional en secundarias", near) == "alta"


def test_repositories_need_a_directive_role_next_to_the_school():
    general = "Analizamos la gestión de la escuela secundaria y las trayectorias de los estudiantes."
    assert status("Trayectorias en la secundaria", general, "CONICET Digital") == "rechazada"
    role = "Entrevistamos a los directivos de escuelas secundarias sobre sus decisiones curriculares."
    assert status("Decisiones curriculares", role, "CONICET Digital") == "alta"
    assert status("La dirección escolar en Argentina: aproximación al estado del arte", "", "CONICET Digital") == "alta"


def test_school_ownership_type_is_not_school_management():
    abstract = "Comparamos trayectorias de estudiantes en escuelas de gestión estatal y de gestión privada."
    assert status("Trayectorias en la secundaria", abstract, "CONICET Digital") == "rechazada"


def test_resource_management_in_schools_is_not_school_management():
    abstract = "Se analiza la gestión del agua en las escuelas rurales del partido de Tandil."
    assert status("Aguas subterráneas en la llanura", abstract, "CONICET Digital") == "rechazada"


def test_field_names_in_title_are_kept_unless_higher_education():
    assert status("Methodological Individualism and Educational Leadership") == "alta"
    assert status("Women in Educational Administration") == "alta"
    assert status("Gestión educativa y desempeño docente en una universidad privada de Lima") == "rechazada"


def test_portuguese_and_title_roles():
    assert status("GESTÃO DEMOCRÁTICA ESCOLAR E PROJETO POLÍTICO-PEDAGÓGICO") == "alta"
    assert status("El director como un líder transformador", "Estudio en instituciones educativas.") == "alta"


def test_conicet_header_is_ignored():
    row = {"title": "Historia de la paleobotánica",
           "abstract": "Historia de la paleobotánica; History of paleobotany\nOttone, Eduardo\nLos jesuitas describieron plantas fósiles."}
    assert "ottone" not in rf.row_text(row)[1]


def test_rejected_records_are_reevaluated_and_overrides_win(tmp_path, monkeypatch):
    fields = rf.CSV_FIELDS
    good = {f: "" for f in fields}
    good.update(record_id="r-good", title="School leadership and teacher retention", source="OpenAlex")
    bad = {f: "" for f in fields}
    bad.update(record_id="r-bad", title="Sharks along the coast", source="CONICET Digital")
    forced = {f: "" for f in fields}
    forced.update(record_id="r-forced", title="Una historia de la educación", source="CONICET Digital")
    (tmp_path / "data").mkdir()
    (tmp_path / "config").mkdir()
    rf.write_csv(tmp_path / "data" / "master_records.csv", fields, [bad])
    rf.write_csv(tmp_path / "data" / "rejected_records.csv", fields, [good, forced])
    (tmp_path / "config" / "relevance_overrides.csv").write_text(
        "record_id,decision,nota\nr-forced,incluir,revisado a mano\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    rf.main()
    with open("data/master_records.csv", encoding="utf-8") as fh:
        kept = {r["record_id"]: r for r in csv.DictReader(fh)}
    assert set(kept) == {"r-good", "r-forced"}
    assert kept["r-forced"]["relevance_reason"].startswith("decisión manual")
    with open("data/rejected_records.csv", encoding="utf-8") as fh:
        assert [r["record_id"] for r in csv.DictReader(fh)] == ["r-bad"]


def test_pandemic_context_does_not_discard_school_management():
    abstract = "During the COVID-19 pandemic, private schools' management adopted new strategies."
    assert status("COVID-19 and private schools' management strategies during lockdown in Nigeria", abstract) == "alta"


def test_library_guides_are_not_academic_works():
    assert status("LibGuides: Educational Leadership: Books") == "rechazada"
    assert status("Research Guides: EDLEAD 6206 - Orientation to School Management: Home") == "rechazada"


def test_field_title_survives_incidental_noise():
    abstract = "Women's status, health and empowerment shape access to educational leadership positions."
    assert status("Status and empowerment of women for educational leadership in India", abstract) == "alta"


def test_thesis_or_project_director_is_not_a_directive_role():
    thesis = "Trabajo dirigido por el director de tesis; se tomaron muestras de suelo cerca de una escuela rural."
    assert status("Propiedades de suelos pampeanos", thesis, "CONICET Digital") == "rechazada"


def test_deduplicate_merges_same_work_but_keeps_homonyms():
    base = {f: "" for f in rf.CSV_FIELDS}
    a = {**base, "record_id": "10.1/x", "doi": "10.1/x", "title": "La dirección escolar en la normativa vigente de Córdoba",
         "authors": "Carolina Yelicich", "publication_year": "2021", "source": "OpenAlex"}
    b = {**base, "record_id": "conicet:x", "title": "La dirección escolar en la normativa vigente de Córdoba",
         "authors": "Yelicich, Carolina", "publication_year": "2023", "source": "CONICET Digital", "keywords": "dirección"}
    c = {**base, "record_id": "W1", "title": "La dirección escolar en España", "authors": "Antonia López Martínez",
         "publication_year": "2021", "source": "OpenAlex"}
    d = {**base, "record_id": "W2", "title": "La dirección escolar en España", "authors": "Manuel Álvarez Fernández",
         "publication_year": "2020", "source": "OpenAlex"}
    e = {**base, "record_id": "W3", "title": "Política y gestión educativa en el Perú contemporáneo", "authors": "Rosana Meleán",
         "publication_year": "2022", "source": "OpenAlex", "doi": "10.2/y"}
    f = {**base, "record_id": "W4", "title": "Política y gestión educativa en el Perú contemporáneo", "authors": "",
         "publication_year": "2023", "source": "OpenAlex"}
    kept, removed = rf.deduplicate([a, b, c, d, e, f])
    ids = {r["record_id"] for r in kept}
    assert ids == {"10.1/x", "W1", "W2", "W3"}
    merged = next(r for r in kept if r["record_id"] == "10.1/x")
    assert merged["keywords"] == "dirección" and "CONICET Digital" in merged["source"]
    assert {r["duplicate_of"] for r in removed} == {"10.1/x", "W3"}
    assert rf.classify_relevance({"title": "", "abstract": "gestión escolar"})[0] == "rechazada"


def test_deduplicate_compound_surname():
    from relevance_filter import deduplicate
    title = "Problemas de práctica de directores de escuelas vulnerables: oportunidades para el desarrollo"
    rows = [
        {"title": title, "authors": "Luis De la Vega", "doi": "10.15517/rge.v10i1.56232", "source": "OpenAlex"},
        {"title": title, "authors": "Luis Felipe de la Vega Rodríguez", "doi": "", "source": "OpenAlex"},
    ]
    kept, removed = deduplicate(rows)
    assert len(kept) == 1 and len(removed) == 1
