from __future__ import annotations

from typing import Any


STOPWORDS_ES = {
    "a", "al", "algo", "ante", "como", "con", "contra", "cual", "cuando", "de", "del", "desde",
    "donde", "el", "ella", "en", "entre", "era", "es", "esta", "este", "fue", "ha", "hacia", "hasta",
    "la", "las", "lo", "los", "más", "muy", "no", "o", "para", "pero", "por", "que", "se", "sin",
    "sobre", "son", "su", "sus", "también", "un", "una", "uno", "y", "ya",
}
STOPWORDS_EN = {
    "a", "an", "and", "are", "as", "at", "be", "been", "being", "by", "during", "for", "from", "had",
    "has", "have", "in", "into", "is", "it", "its", "of", "on", "or", "our", "that", "the", "their",
    "these", "this", "those", "to", "was", "were", "with", "within", "without",
}
STOPWORDS_PT = {
    "a", "ao", "aos", "as", "com", "como", "da", "das", "de", "do", "dos", "e", "em", "entre", "é",
    "foi", "mais", "na", "nas", "não", "no", "nos", "o", "os", "ou", "para", "pela", "pelo", "por",
    "que", "se", "sem", "sobre", "sua", "suas", "um", "uma",
}
STOPWORDS_ID = {
    "adalah", "akan", "atau", "dalam", "dan", "dari", "dengan", "di", "ini", "itu", "ke", "oleh", "pada",
    "sebagai", "untuk", "yang",
}
STOPWORDS_EDITORIAL = {
    "article", "articles", "author", "authors", "copyright", "creative", "commons", "doi", "editor", "issue",
    "journal", "number", "publication", "published", "publisher", "received", "references", "review", "volume", "vol",
    "et", "et al", "issn", "isbn",
}
STOPWORDS_ARTIFACTS = {"amp", "nbsp", "x0d", "http", "https", "www", "xx", "rs", "mg", "cep", "ptsmc"}


def multilingual_stopwords() -> list[str]:
    return sorted(STOPWORDS_ES | STOPWORDS_EN | STOPWORDS_PT | STOPWORDS_ID | STOPWORDS_EDITORIAL | STOPWORDS_ARTIFACTS)


def build_vectorizer(config: dict[str, Any]):
    from sklearn.feature_extraction.text import CountVectorizer

    cfg = config["bertopic"]
    return CountVectorizer(
        ngram_range=(int(cfg.get("ngram_min", 1)), int(cfg.get("ngram_max", 3))),
        min_df=int(cfg.get("min_df", 2)), max_df=float(cfg.get("max_df", 0.95)),
        max_features=int(cfg.get("max_features", 50000)), stop_words=multilingual_stopwords(),
        lowercase=True, strip_accents=None,
        token_pattern=cfg.get("token_pattern", r"(?u)\b[^\W\d_](?:[\wÀ-ÖØ-öø-ÿ-]*[^\W_])?\b"),
    )


def effective_vectorizer_parameters(vectorizer) -> dict[str, Any]:
    params = vectorizer.get_params(deep=False)
    for key, value in list(params.items()):
        if isinstance(value, (set, tuple)):
            params[key] = list(value)
    params["stop_words_count"] = len(vectorizer.stop_words or [])
    params["stopword_groups"] = {
        "es": len(STOPWORDS_ES), "en": len(STOPWORDS_EN), "pt": len(STOPWORDS_PT), "id": len(STOPWORDS_ID),
        "editorial": len(STOPWORDS_EDITORIAL), "artifacts": len(STOPWORDS_ARTIFACTS),
    }
    if isinstance(params.get("stop_words"), list):
        params["stop_words_sha256_input"] = "\n".join(params["stop_words"])
    return params
