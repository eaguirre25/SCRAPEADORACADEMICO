#!/usr/bin/env python3
"""Construye citas en normas APA 7 a partir de los registros del scraper.

Los registros de `data/master_records.csv` no traen volumen, numero, paginas ni
editorial, asi que la cita se emite con marcadores visibles (`[vol]`, `[num]`,
`[pp.]`, `[Editorial]`) para que el dato faltante se note al pegarla.

La inversion del nombre de autor depende del idioma del registro: en espanol y
portugues se asumen dos apellidos cuando el nombre lo permite, en ingles uno
solo. El idioma se toma de las salidas de modelado cuando existe y, si no, se
infiere con palabras funcionales del titulo y el resumen.
"""
from __future__ import annotations

import html as html_lib
import re
import unicodedata
from dataclasses import dataclass, field

# ── Nombres de pila frecuentes en el corpus ──────────────────────────────────
# Solo se usan para resolver el caso ambiguo de tres palabras: "Ramona Isabel
# Ferreira" (dos nombres + un apellido) frente a "Humberto Garcia Caucha" (un
# nombre + dos apellidos). Sin esta lista el segundo token se leeria siempre
# como apellido y la mayoria de las citas femeninas quedarian mal invertidas.
GIVEN_NAMES = {
    "abel", "abigail", "adan", "adela", "adolfo", "adrian", "adriana", "agustin",
    "agustina", "aida", "alba", "alberto", "alcides", "aldo", "alejandra",
    "alejandro", "alexander", "alexandra", "alexis", "alfonso", "alfredo",
    "alicia", "alma", "alonso", "amalia", "amanda", "amelia", "ana", "anabel",
    "anahi", "andrea", "andres", "angel", "angela", "angeles", "angelica",
    "anibal", "antonia", "antonio", "araceli", "ariadna", "ariel", "arturo",
    "asuncion", "aurelio", "aurora", "barbara", "beatriz", "belen", "benjamin",
    "bernardo", "berta", "betsabe", "blanca", "bruno", "camila", "camilo",
    "carla", "carlos", "carmen", "carolina", "catalina", "cecilia", "celia",
    "cesar", "cintia", "clara", "claudia", "claudio", "clemente", "concepcion",
    "consuelo", "cristian", "cristina", "cristobal", "dalia", "damian", "daniel",
    "daniela", "dario", "david", "debora", "delia", "diana", "diego", "dolores",
    "domingo", "dora", "doris", "edgar", "edgardo", "edith", "edmundo", "eduardo",
    "edwin", "efrain", "elena", "eliana", "elias", "elisa", "elizabeth", "eloisa",
    "elsa", "elvira", "emilia", "emiliano", "emilio", "emma", "enrique",
    "erica", "erika", "ernesto", "esteban", "estela", "ester", "esther",
    "eugenia", "eugenio", "eusebia", "eva", "evelyn", "ezequiel", "fabian",
    "fabiana", "fabio", "fabiola", "federico", "felipe", "felix", "fernanda",
    "fernando", "fidel", "flavia", "flor", "flora", "florencia", "francisca",
    "francisco", "franco", "gabriel", "gabriela", "gaston", "genoveva",
    "geraldine", "gerardo", "german", "gilberto", "gina", "gisela", "gladys",
    "gloria", "gonzalo", "graciela", "gregorio", "guadalupe", "guillermo",
    "gustavo", "hector", "helena", "heriberto", "hernan", "hilda", "horacio",
    "hugo", "humberto", "ignacio", "ines", "irene", "iris", "irma", "isaac",
    "isabel", "isabela", "ismael", "israel", "ivan", "ivonne", "jacinto",
    "jaime", "javier", "jazmin", "jeanette", "jenny", "jesica", "jessica",
    "jesus", "joaquin", "joel", "jonathan", "jorge", "jose", "josefa",
    "josefina", "joselyn", "juan", "juana", "judith", "julia", "julian",
    "juliana", "julieta", "julio", "karen", "karina", "karla", "katherine",
    "kevin", "laura", "lautaro", "lazaro", "leandro", "leonardo", "leonor",
    "leticia", "lidia", "liliana", "lorena", "lorenzo", "lourdes", "lucas",
    "lucia", "luciana", "luciano", "lucila", "lucrecia", "luis", "luisa",
    "luz", "magdalena", "manuel", "manuela", "marcela", "marcelo", "marcia",
    "marco", "marcos", "margarita", "maria", "mariana", "mariano", "maribel",
    "maricela", "mariela", "marina", "mario", "marisa", "marisol", "marta",
    "martha", "martin", "mateo", "matias", "mauricio", "mauro", "maximiliano",
    "mayra", "melania", "melissa", "mercedes", "micaela", "miguel", "milagros",
    "mirta", "moises", "monica", "myriam", "nadia", "nancy", "natalia",
    "nataly", "nelida", "nelson", "nestor", "nicolas", "nidia", "nilda",
    "noelia", "noemi", "norberto", "norma", "nubia", "nuria", "octavio",
    "olga", "olivia", "omar", "orlando", "oscar", "osvaldo", "pablo", "pamela",
    "paola", "pastor", "patricia", "patricio", "paula", "paulina", "paulo",
    "pedro", "pilar", "priscila", "rafael", "ramiro", "ramon", "ramona",
    "raquel", "raul", "rebeca", "regina", "reina", "renata", "rene", "reyna",
    "ricardo", "rita", "roberto", "rocio", "rodolfo", "rodrigo", "rogelio",
    "rolando", "romina", "ronald", "rosa", "rosalia", "rosana", "rosario",
    "roxana", "ruben", "rufino", "ruth", "sabrina", "salvador", "samuel",
    "sandra", "santiago", "sara", "saul", "sebastian", "selena", "sergio",
    "silvana", "silvia", "silvina", "simon", "sofia", "sol", "soledad",
    "sonia", "stella", "susana", "tamara", "tania", "teresa", "tomas",
    "valentina", "valeria", "vanesa", "vanessa", "veronica", "vicente",
    "victor", "victoria", "vilma", "violeta", "virginia", "vivian", "viviana",
    "walter", "wendoly", "wilfredo", "william", "wilson", "wilma", "ximena",
    "yamila", "yanina", "yazmin", "yesenia", "yolanda", "yuliana", "zulema",
    # Portugues
    "ana", "antonio", "bruna", "caio", "carla", "cristiane", "danilo",
    "eduarda", "fabricio", "geraldo", "helio", "joao", "joana", "juliana",
    "leticia", "luciana", "luiz", "marcia", "mauricio", "nara", "paulo",
    "renata", "rosangela", "sandro", "tatiana", "thiago", "vera", "vinicius",
}

# Particulas que forman parte del apellido y deben viajar con el.
PARTICLES = {
    "de", "del", "la", "las", "los", "da", "das", "do", "dos", "di", "du",
    "van", "von", "der", "den", "le", "san", "santa", "y", "e",
}

# Palabras funcionales para inferir idioma cuando el modelado no lo informa.
LANGUAGE_MARKERS = {
    "es": {"de", "la", "el", "en", "los", "las", "una", "con", "para", "por",
           "que", "del", "escolar", "gestion", "educativa", "directivo"},
    "pt": {"da", "do", "das", "dos", "uma", "com", "para", "por", "que", "nao",
           "sao", "escolar", "gestao", "educacao", "professores"},
    "en": {"the", "of", "and", "in", "for", "with", "on", "school", "management",
           "leadership", "teachers", "principals"},
}

# `origin` a veces trae el repositorio en lugar de la revista.
REPOSITORY_MARKERS = (
    "conicet", "openalex", "la referencia", "zenodo", "sedici", "unsam",
    "repositorio", "repositor", "digital library", "dspace", "redalyc",
    "core.ac.uk", "figshare", "ssrn", "researchgate",
)

JOURNAL_TYPES = {"article", "review", "editorial", "letter", "paratext",
                 "reference-entry", "preprint", "info:eu-repo/semantics/article"}

PLACEHOLDER_VOLUME = "[vol]"
PLACEHOLDER_ISSUE = "[num]"
PLACEHOLDER_PAGES = "[pp.]"
PLACEHOLDER_PUBLISHER = "[Editorial]"
PLACEHOLDER_INSTITUTION = "[Institucion]"
PLACEHOLDER_JOURNAL = "[Revista]"
PLACEHOLDER_EDITOR = "[Editor/a]"
PLACEHOLDER_BOOK = "[Titulo del libro]"


@dataclass
class Citation:
    """Cita APA lista para copiar, con el tramo en cursiva identificado."""

    text: str
    italic: str = ""
    missing: list[str] = field(default_factory=list)
    kind: str = "generico"

    @property
    def is_complete(self) -> bool:
        return not self.missing


def s(value: object) -> str:
    """Normaliza a texto y deshace las entidades HTML que llegan de OpenAlex."""
    text = str(value or "").strip()
    if "&" in text:
        # Titulos como "Politicas de &lt;i&gt;accountability&lt;/i&gt;" llegan
        # con marcado escapado; se limpia antes de construir la referencia.
        text = html_lib.unescape(text)
        text = re.sub(r"<[^>]+>", "", text).strip()
    return text


def strip_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def detect_language(record: dict, known: str = "") -> str:
    """Devuelve es, pt o en. `known` viene de las salidas de modelado."""
    known = s(known).lower()[:2]
    if known in LANGUAGE_MARKERS:
        return known
    sample = strip_accents(f'{s(record.get("title"))} {s(record.get("abstract"))}'.lower())
    words = set(re.findall(r"[a-z]{2,}", sample))
    scores = {code: len(words & markers) for code, markers in LANGUAGE_MARKERS.items()}
    best = max(scores, key=lambda code: scores[code])
    return best if scores[best] else "es"


def split_authors(raw: object) -> list[str]:
    """Separa la lista de autores respetando el formato del scraper."""
    text = s(raw)
    if not text:
        return []
    parts = [part.strip(" .,;") for part in text.split(";")]
    return [part for part in parts if part]


def _initials(tokens: list[str]) -> str:
    initials = []
    for token in tokens:
        for chunk in re.split(r"[-]", token):
            chunk = chunk.strip()
            if chunk:
                initials.append(f"{chunk[0].upper()}.")
    return " ".join(initials)


def format_author(name: str, language: str = "es") -> str:
    """Invierte un nombre al formato APA: `Apellido Apellido, N. N.`"""
    name = s(name)
    if not name:
        return ""

    # Formato ya invertido por la fuente: "Palomino Huapaya, Juan Alberto".
    if "," in name:
        surname, _, given = name.partition(",")
        surname, given = surname.strip(), given.strip()
        if not surname:
            return given
        if not given:
            return surname
        return f"{surname}, {_initials(given.split())}"

    tokens = name.split()
    if len(tokens) == 1:
        return tokens[0]

    if language == "en":
        surname_start = len(tokens) - 1
    else:
        # El primer token siempre es nombre de pila. Se avanza mientras los
        # siguientes sigan siendo nombres conocidos; lo que resta son apellidos,
        # con tope de dos para no arrastrar nombres compuestos no listados.
        surname_start = 1
        while surname_start < len(tokens) - 1 and strip_accents(
            tokens[surname_start].lower()
        ) in GIVEN_NAMES:
            surname_start += 1
        surname_start = max(surname_start, len(tokens) - 2)

    # Las particulas viajan con el apellido: "Maria de la Cruz Perez".
    while surname_start > 1 and strip_accents(tokens[surname_start - 1].lower()) in PARTICLES:
        surname_start -= 1

    surname = " ".join(tokens[surname_start:])
    given = tokens[:surname_start]
    return f"{surname}, {_initials(given)}" if given else surname


def format_author_list(names: list[str], language: str = "es") -> str:
    """Aplica las reglas APA 7 de 1, 2-20 y 21 o mas autores."""
    formatted = [format_author(name, language) for name in names]
    formatted = [name for name in formatted if name]
    if not formatted:
        return ""
    if len(formatted) == 1:
        listed = formatted[0]
    elif len(formatted) <= 20:
        listed = ", ".join(formatted[:-1]) + f", & {formatted[-1]}"
    else:
        # 21 o mas: primeros 19, puntos suspensivos y el ultimo.
        listed = ", ".join(formatted[:19]) + f", ... {formatted[-1]}"
    # La particula inicial se capitaliza al abrir la referencia: "De la Serna".
    return listed[:1].upper() + listed[1:]


def sentence_case(title: str) -> str:
    """APA pide caso oracion; muchos titulos del corpus vienen en mayusculas."""
    title = s(title)
    letters = [char for char in title if char.isalpha()]
    if not letters:
        return title
    upper_ratio = sum(char.isupper() for char in letters) / len(letters)
    if upper_ratio < 0.7:
        return title
    lowered = title.lower()
    result = []
    capitalize_next = True
    for char in lowered:
        if capitalize_next and char.isalpha():
            result.append(char.upper())
            capitalize_next = False
        else:
            result.append(char)
        if char in ".:?!":
            capitalize_next = True
    return "".join(result)


def _is_repository(origin: str) -> bool:
    normalized = strip_accents(origin.lower())
    return any(marker in normalized for marker in REPOSITORY_MARKERS)


def _locator(record: dict) -> str:
    doi = s(record.get("doi"))
    if doi:
        clean = re.sub(r"^https?://(dx\.)?doi\.org/", "", doi, flags=re.I)
        return f"https://doi.org/{clean}"
    return s(record.get("url"))


def build_citation(record: dict, language: str = "") -> Citation:
    """Arma la referencia APA 7 del registro segun su tipo documental."""
    language = detect_language(record, language)
    authors = format_author_list(split_authors(record.get("authors")), language)
    year = s(record.get("publication_year")) or "s. f."
    title = sentence_case(record.get("title")) or "[Titulo no disponible]"
    # Algunos nombres de revista llegan con punto final y duplicarian la
    # puntuacion al encadenar el volumen.
    origin = s(record.get("origin")).rstrip(" .,;")
    doc_type = s(record.get("document_type")).lower()
    locator = _locator(record)
    missing: list[str] = []

    if not authors:
        # Sin autoria APA mueve el titulo a la posicion de autor.
        separator = "" if title.endswith((".", "?", "!")) else "."
        head = f"{title}{separator} ({year})."
        title_in_head = True
    else:
        head = f"{authors} ({year})."
        title_in_head = False

    def close(body: str, italic: str, kind: str) -> Citation:
        tail = f" {locator}" if locator else ""
        return Citation(text=f"{head} {body}".strip() + tail, italic=italic, missing=missing, kind=kind)

    if doc_type == "dissertation":
        institution = origin if origin and not _is_repository(origin) else PLACEHOLDER_INSTITUTION
        if institution == PLACEHOLDER_INSTITUTION:
            missing.append("institucion")
        body = "" if title_in_head else f"*{title}*"
        detail = f"[Tesis, {institution}]."
        repository = f" {origin}." if origin and _is_repository(origin) else ""
        return close(f"{body} {detail}{repository}".strip(), title, "tesis")

    if doc_type == "book":
        publisher = origin if origin and not _is_repository(origin) else PLACEHOLDER_PUBLISHER
        if publisher == PLACEHOLDER_PUBLISHER:
            missing.append("editorial")
        body = "" if title_in_head else f"*{title}*."
        return close(f"{body} {publisher}.".strip(), title, "libro")

    if doc_type == "book-chapter":
        publisher = origin if origin and not _is_repository(origin) else PLACEHOLDER_PUBLISHER
        if publisher == PLACEHOLDER_PUBLISHER:
            missing.append("editorial")
        missing.extend(["editor del libro", "titulo del libro", "paginas"])
        body = "" if title_in_head else f"{title}."
        container = (
            f" En {PLACEHOLDER_EDITOR} (Ed.), *{PLACEHOLDER_BOOK}* "
            f"({PLACEHOLDER_PAGES}). {publisher}."
        )
        return close(f"{body}{container}".strip(), PLACEHOLDER_BOOK, "capitulo")

    if doc_type == "report":
        institution = origin if origin and not _is_repository(origin) else PLACEHOLDER_INSTITUTION
        if institution == PLACEHOLDER_INSTITUTION:
            missing.append("institucion")
        body = "" if title_in_head else f"*{title}*."
        return close(f"{body} {institution}.".strip(), title, "informe")

    if doc_type == "conference-paper":
        missing.append("congreso y lugar")
        body = "" if title_in_head else f"*{title}*"
        venue = origin or "[Congreso]"
        return close(f"{body} [Ponencia]. {venue}.".strip(), title, "ponencia")

    if doc_type in JOURNAL_TYPES or (doc_type == "" and origin and not _is_repository(origin)):
        journal = origin if origin and not _is_repository(origin) else PLACEHOLDER_JOURNAL
        if journal == PLACEHOLDER_JOURNAL:
            missing.append("revista")
        missing.extend(["volumen", "numero", "paginas"])
        body = "" if title_in_head else f"{title}."
        reference = (
            f" *{journal}*, {PLACEHOLDER_VOLUME}({PLACEHOLDER_ISSUE}), {PLACEHOLDER_PAGES}."
        )
        return close(f"{body}{reference}".strip(), journal, "articulo")

    # Documento de repositorio o tipo no declarado.
    body = "" if title_in_head else f"*{title}*."
    container = f" {origin}." if origin else ""
    if not origin:
        missing.append("fuente")
    missing.append("tipo documental")
    return close(f"{body}{container}".strip(), title, "documento")


def citation_html(citation: Citation) -> str:
    """Version con cursiva para copiar al portapapeles como texto enriquecido."""
    import html as html_lib

    escaped = html_lib.escape(citation.text.replace("*", ""))
    if not citation.italic:
        return escaped
    target = html_lib.escape(citation.italic)
    return escaped.replace(target, f"<em>{target}</em>", 1)


def plain_text(citation: Citation) -> str:
    return citation.text.replace("*", "")
