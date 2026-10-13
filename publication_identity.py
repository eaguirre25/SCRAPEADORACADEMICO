"""Conservative publication identity checks shared by ingestion and audits."""
import re
from urllib.parse import parse_qsl, urlencode, urlsplit, unquote
from topic_modeling.identifiers import clean_value, first_author, normalize_doi, normalize_text


def canonical_url(value):
    """Ignore transport and tracking, retaining article paths and meaningful query IDs."""
    value = clean_value(value)
    try:
        parts = urlsplit(value)
        if parts.scheme.lower() not in {"http", "https"} or not parts.hostname:
            return ""
        host = parts.hostname.casefold().removeprefix("www.")
        if host == "dx.doi.org":
            host = "doi.org"
        path = unquote(parts.path).rstrip("/")
        query = [(k, v) for k, v in parse_qsl(parts.query, keep_blank_values=True)
                 if not k.casefold().startswith("utm_") and k.casefold() not in {"fbclid", "gclid"}]
        port = parts.port
        authority = host + (f":{port}" if port and port not in {80, 443} else "")
        return authority + path + ("?" + urlencode(sorted(query)) if query else "")
    except ValueError:
        return ""


def authors_compatible(left, right):
    particles = {"de", "del", "da", "do", "dos", "das", "la", "las", "los", "van", "von", "et", "al"}
    a = {t for t in first_author(left).split() if len(t) > 1 and t not in particles}
    b = {t for t in first_author(right).split() if len(t) > 1 and t not in particles}
    return len(a) >= 2 and len(b) >= 2 and (a <= b or b <= a or len(a & b) >= 2)


def conflicting_dois(left, right):
    a, b = normalize_doi(left.get("doi")), normalize_doi(right.get("doi"))
    return bool(a and b and a != b)


def same_publication_url(left, right):
    url = canonical_url(left.get("url"))
    if not url or url != canonical_url(right.get("url")) or conflicting_dois(left, right):
        return False
    # A repository handle/DOI or OJS article page identifies the item even if
    # one source lacks authors. Home pages require stronger evidence.
    item = re.search(r"(?:^doi\.org/10\.|/(?:handle/|article/view/|record/|records/)\S+)", url)
    if item:
        return True
    return authors_compatible(left.get("authors"), right.get("authors")) and bool(urlsplit("https://" + url).path.strip("/"))


def publication_title(value):
    # Repository section labels are catalog annotations, not part of the work.
    title = re.sub(r"\s*\((?:Investigaciones|Artículos|Articles|Research)\)\s*$", "", clean_value(value), flags=re.I)
    return normalize_text(title)
