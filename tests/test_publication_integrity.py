import csv
from copy import deepcopy
from pathlib import Path

from publication_identity import canonical_url, same_publication_url
from dashboard_integrity import model_fingerprint, proposal_matches, publication_audit
from relevance_filter import deduplicate
from topic_modeling.deduplication import audit_and_resolve_duplicates


def pair():
    return [
        dict(record_id='a', title='Ethopolitics of school leadership', authors='Elías Gonzalo Aguirre; Eduardo Langer', publication_year='2025', doi='', url='http://hdl.handle.net/11336/290548', source='OpenAlex', origin='CONICET', keywords='Work (physics)'),
        dict(record_id='b', title='Ethopolítica de la dirección escolar', authors='Aguirre, Elías Gonzalo; Langer, Eduardo', publication_year='2025', doi='', url='https://hdl.handle.net/11336/290548?utm_source=web', source='CONICET Digital', origin='Revista', keywords='dirección escolar'),
    ]


def test_transport_and_tracking_dont_split_a_publication():
    assert canonical_url('http://www.rev.org/article/view/12/?utm_source=x#abstract') == canonical_url('https://rev.org/article/view/12')
    assert canonical_url('https://rev.org/article?id=12') != canonical_url('https://rev.org/article?id=13')
    assert canonical_url('') == canonical_url('nan') == canonical_url('javascript:alert(1)') == ''


def test_translations_are_merged_in_both_pipelines_and_provenance_survives():
    kept, removed = deduplicate(pair())
    assert len(kept) == len(removed) == 1
    assert set(kept[0]['source'].split(' | ')) == {'OpenAlex', 'CONICET Digital'}
    assert set(kept[0]['origin'].split(' | ')) == {'CONICET', 'Revista'}
    assert removed[0]['title'] == pair()[1]['title']
    assert not deduplicate(kept)[1]
    canonical, exact, _, resolutions = audit_and_resolve_duplicates(pair())
    assert len(canonical) == 1
    assert {r['rule'] for r in exact} == {'canonical_publication_url'}
    assert len(resolutions) == 2


def test_homonyms_distinct_dois_and_shared_home_pages_are_kept():
    rows = pair()
    for row in rows:
        row['title'] = 'School leadership'
        row['url'] = 'https://journal.org/'
    rows[1]['authors'] = 'Otra Autora'
    assert len(deduplicate(deepcopy(rows))[0]) == 2
    rows[1]['authors'] = rows[0]['authors']
    rows[0]['doi'], rows[1]['doi'] = '10.1234/a', '10.1234/b'
    assert len(deduplicate(deepcopy(rows))[0]) == 2
    assert len(audit_and_resolve_duplicates(rows)[0]) == 2


def test_doi_less_bridge_cannot_merge_two_distinct_dois():
    rows = pair()
    rows[0]['doi'] = '10.1234/a'
    rows += [{**rows[0], 'record_id': 'c', 'doi': '10.1234/b'}]
    assert len(deduplicate(deepcopy(rows))[0]) == 2
    assert len(audit_and_resolve_duplicates(rows)[0]) == 2


def test_labels_must_match_current_partition_not_just_topic_number():
    topic = dict(topic_id='3', automatic_label='covid-19 · pandemic', document_count='271')
    old = dict(descriptor_automatic='rural · escuelas', document_count='78')
    assert not proposal_matches(old, topic)
    assert proposal_matches(dict(descriptor_automatic='covid-19 · pandemic', document_count='271'), topic)
    fingerprint = model_fingerprint([topic], [dict(document_id='a', topic_id='3')])
    changed = model_fingerprint([topic], [dict(document_id='a', topic_id='4')])
    assert fingerprint != changed
    assert not proposal_matches(dict(model_fingerprint=fingerprint), topic, changed)


def test_audit_detects_translations_without_flagging_title_homonyms():
    audit = publication_audit(pair())
    assert len(audit['duplicate_publication_urls']) == 1
    assert audit['duplicate_identifiers'] == {'doi': 0, 'record_id': 0}


def test_scraper_preserves_enriched_metadata_on_schema_migration(tmp_path, monkeypatch):
    import main
    target = tmp_path / 'master.csv'
    target.write_text('record_id,title,relevance_status,custom_metadata\na,Dirección escolar,alta,conservar\n', encoding='utf-8')
    monkeypatch.setattr(main, 'MASTER_CSV', target)
    monkeypatch.setattr(main, 'CSV_FIELDS', list(main.CSV_FIELDS))
    main.migrate_master_csv_schema()
    rows = list(csv.DictReader(target.open()))
    assert rows[0]['relevance_status'] == 'alta'
    assert rows[0]['custom_metadata'] == 'conservar'
    main.append_master_records([dict(record_id='b', title='Otro trabajo')])
    assert list(csv.DictReader(target.open()))[0]['custom_metadata'] == 'conservar'


def test_ingestion_fuzzy_match_keeps_conflicting_dois_and_homonyms():
    from main import find_fuzzy_duplicate_target, normalize_text, get_first_author
    rows = pair()
    rows[1]['title'] = rows[0]['title']
    rows[1]['authors'] = 'Otra Autora'
    assert find_fuzzy_duplicate_target(rows[0], {'2025': [rows[1]]}) is None
    rows[1]['authors'] = rows[0]['authors']
    rows[0]['doi'], rows[1]['doi'] = '10.1234/a', '10.1234/b'
    assert find_fuzzy_duplicate_target(rows[0], {'2025': [rows[1]]}) is None


def test_pdf_version_wins_over_a_doi_only_record():
    rows = pair()
    rows[0]["doi"] = "10.1234/a"
    rows[0]["pdf_url"] = "https://doi.org/10.1234/a"
    rows[1]["pdf_url"] = "https://repository.org/article.pdf"
    kept, removed = deduplicate(rows)
    assert kept[0]["record_id"] == "b"
    assert kept[0]["doi"] == "10.1234/a"
    assert kept[0]["pdf_url"].endswith("article.pdf")


def test_translated_abstract_merges_but_different_chapters_survive():
    rows = pair()
    rows[1]["url"] = "https://repository.org/article/2"
    for row in rows:
        row["abstract"] = "This research examines school leadership practices and teacher collaboration. " * 8
        row["document_type"] = "article"
    assert len(deduplicate(deepcopy(rows))[0]) == 1
    rows[1]["document_type"] = "book-chapter"
    assert len(deduplicate(rows)[0]) == 2


def test_shared_name_particles_do_not_identify_an_author():
    from publication_identity import authors_compatible
    assert not authors_compatible("Rita de Cássia Rosa da Silva", "Andressa Bernardo da Silva")


def test_download_rejects_html_even_with_pdf_filename_and_mime(tmp_path, monkeypatch):
    import main
    class Response:
        headers = {'content-type': 'application/pdf'}
        def raise_for_status(self): pass
        def iter_content(self, size): yield b'<!doctype html><h1>Access denied</h1>'
    monkeypatch.setattr(main, 'PDFS_DIR', tmp_path)
    monkeypatch.setattr(main.requests, 'get', lambda *a, **k: Response())
    assert main.download_pdf({'title': 'Test', 'pdf_url': 'https://example.org/test.pdf'}) is None
    assert not list(tmp_path.iterdir())


def test_download_rejects_empty_responses(tmp_path, monkeypatch):
    import main
    class Response:
        headers = {'content-type': 'application/pdf'}
        def raise_for_status(self): pass
        def iter_content(self, size): return iter([])
    monkeypatch.setattr(main, 'PDFS_DIR', tmp_path)
    monkeypatch.setattr(main.requests, 'get', lambda *a, **k: Response())
    assert main.download_pdf({'title': 'Test', 'pdf_url': 'https://example.org/test.pdf'}) is None
    assert not list(tmp_path.iterdir())
