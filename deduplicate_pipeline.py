"""Compatibility entry point; uses the conservative operational deduplicator."""
from relevance_filter import deduplicate, deduplicate_master
from topic_modeling.identifiers import normalize_doi as clean_doi, normalize_text as clean_title


def deduplicate_dataframe(df, title_col="titulo", doi_col="url"):
    rows = df.to_dict("records")
    adapted = [dict(row, title=row.get(title_col, ""), doi=row.get(doi_col, "") if doi_col != "url" else row.get("doi", "")) for row in rows]
    kept, removed = deduplicate(adapted)
    return type(df)(kept)


if __name__ == "__main__":
    deduplicate_master()
