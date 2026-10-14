"""Text helpers shared by all adapters: slugs, dates, body types, privacy scrubbing,
section splitting and rule-based vote extraction."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from bs4 import BeautifulSoup, NavigableString, Tag

from .models import Section, Vote

# ---------------------------------------------------------------- slugs & dates

_TRANSLIT = str.maketrans({"ä": "a", "ö": "o", "å": "a", "Ä": "a", "Ö": "o", "Å": "a"})


def slugify(s: str) -> str:
    s = s.translate(_TRANSLIT).lower()
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s or "x"


_DATE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")


def parse_fi_date(s: str) -> str | None:
    """'5.10.2026' or '05.10.2026' -> '2026-10-05'."""
    m = _DATE.search(s or "")
    if not m:
        return None
    d, mo, y = (int(x) for x in m.groups())
    try:
        return date(y, mo, d).isoformat()
    except ValueError:
        return None


# ---------------------------------------------------------------- bodies

# Order matters: the first match wins.
_BODY_TYPES = [
    ("council", r"valtuusto$|fullmäktige"),
    ("board", r"aluehallitus|hallitus$|styrelse"),
    ("section", r"jaosto|sektion"),
    ("committee", r"lautakunta|valiokunta|nämnd|utskott"),
    ("advisory", r"neuvosto|vaikuttamistoimielin|neuvottelukunta|råd"),
]


def body_type(name: str) -> str:
    n = name.lower()
    if "nuorisovaltuusto" in n or "ungdomsfullmäktige" in n:
        return "advisory"
    for t, pat in _BODY_TYPES:
        if re.search(pat, n):
            return t
    return "other"


# Bodies we never index: individual-case and personnel sections (personal data),
# employer/employee bodies and test bodies. Regions can add their own patterns.
DEFAULT_EXCLUDE_BODIES = [
    r"yksilö",                 # yksilöasioiden jaosto / yksilöasiainjaosto
    r"henkilöstöjaosto",
    r"individ",                # sv: individsektion
    r"personalsektion",
    r"testi",
    r"työsuojelu",
    r"yhteistoiminta",
]


def excluded(name: str, extra: list[str] | None = None) -> bool:
    n = name.lower()
    return any(re.search(p, n) for p in DEFAULT_EXCLUDE_BODIES + list(extra or []))


# ---------------------------------------------------------------- privacy

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
_PHONE = re.compile(r"(?<!\d)(?:\+358\s?|0)\d{1,3}[\s-]?\d{3,4}[\s-]?\d{3,4}(?!\d)")
_HETU = re.compile(r"\b\d{6}[-+AaBCDEFYXWVU]\d{3}[0-9A-Ya-y]\b")


def scrub(text: str | None) -> str | None:
    """Remove contact details and personal identity codes. Names of people acting in
    a public role are kept; minutes of individual-case bodies are never fetched."""
    if text is None:
        return None
    text = _HETU.sub("[poistettu]", text)
    text = _EMAIL.sub("", text)
    text = _PHONE.sub("", text)
    text = re.sub(r"[ \t]+,", ",", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------- html -> text

_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol",
          "section", "article", "blockquote", "pre", "dd", "dt"}


def html_text(node: Tag | NavigableString) -> str:
    """Text with paragraph breaks preserved (BeautifulSoup's get_text flattens them)."""
    out: list[str] = []

    def walk(n):
        if isinstance(n, NavigableString):
            out.append(str(n))
            return
        if not isinstance(n, Tag) or n.name in ("script", "style", "noscript"):
            return
        block = n.name in _BLOCK
        if block:
            out.append("\n")
        if n.name in ("td", "th"):
            out.append(" ")
        for c in n.children:
            walk(c)
        if block:
            out.append("\n")

    walk(node)
    text = "".join(out).replace("\xa0", " ")
    text = re.sub(r"[ \t\r\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def soup(html: str) -> BeautifulSoup:
    return BeautifulSoup(html, "lxml")


# ---------------------------------------------------------------- sections

# Headings used in Finnish and Swedish minutes. Matched against whole lines.
SECTION_HEADINGS = {
    "proposal": [r"päätösehdotus", r"ehdotus", r"esitys", r"förslag", r"beslutsförslag"],
    "decision": [r"päätös", r"beslut"],
    "discussion": [r"kokouskäsittely", r"käsittely", r"behandling", r"behandling under mötet"],
    "preparer": [r"valmistelija(?:t)?", r"beredning", r"beredare", r"lisätiedot"],
    "presenter": [r"esittelijä", r"föredragande"],
    "attachments": [r"liitteet", r"bilagor", r"oheismateriaali", r"oheisaineisto"],
    "appeal": [r"muutoksenhaku", r"muutoksenhakuohje", r"sökande av ändring", r"besvärsanvisning"],
    "basis": [r"perustelut", r"asian tausta", r"motivering", r"toimivalta"],
}

_HEADING_LINE = re.compile(
    r"^(" + "|".join(p for ps in SECTION_HEADINGS.values() for p in ps) + r")\s*:?\s*$",
    re.IGNORECASE,
)


def heading_kind(line: str) -> str | None:
    line = line.strip().rstrip(":").strip().lower()
    for kind, pats in SECTION_HEADINGS.items():
        if any(re.fullmatch(p, line) for p in pats):
            return kind
    return None


def split_sections(text: str) -> list[Section]:
    """Split item text on lines that are just a known heading ('Päätös', 'Kokouskäsittely'...).
    Text before the first heading goes into a section with an empty heading."""
    sections: list[Section] = []
    heading, buf = "", []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and len(stripped) < 40 and _HEADING_LINE.match(stripped):
            if heading or "".join(buf).strip():
                sections.append(Section(heading, "\n".join(buf).strip()))
            heading, buf = stripped.rstrip(":").strip(), []
        else:
            buf.append(line)
    if heading or "".join(buf).strip():
        sections.append(Section(heading, "\n".join(buf).strip()))
    return sections


def last_of(sections: list[Section], kind: str) -> str | None:
    """The last section of a kind. Minutes repeat proposal/decision for every body that
    handled the case, so the last one belongs to the meeting being read."""
    for s in reversed(sections):
        if heading_kind(s.heading) == kind and s.text:
            return s.text
    return None


# ---------------------------------------------------------------- diary numbers

_DNO = re.compile(
    r"\b(?:Dno|DNo|Dnro|Dnr|Diaarinumero|Asianumero)\.?\s*:?\s*([A-ZÅÄÖ0-9][\w/.\-]*\d[\w/.\-]*)",
    re.IGNORECASE,
)


def diary_number(text: str) -> str | None:
    m = _DNO.search(text or "")
    return m.group(1).rstrip(".,") if m else None


# ---------------------------------------------------------------- votes

_LABELS = {
    "jaa": r"jaa|ja",
    "ei": r"ei|nej",
    "tyhja": r"tyhjää?|tyhjiä|blank(?:a|t)?",
    "poissa": r"poissa|frånvarande",
}
# "42 JAA-ääntä", "16 ei-ääntä", "1 tyhjä", "JAA 42", "JAA-ääniä 42 kpl", "JA 30"
_PAIR_NUM_FIRST = re.compile(
    r"(\d{1,3})\s*(?:kpl\s*)?(" + "|".join(_LABELS.values()) + r")(?:-?\s*ään\w*|-?\s*röst\w*)?\b",
    re.IGNORECASE,
)
_PAIR_LABEL_FIRST = re.compile(
    r"\b(" + "|".join(_LABELS.values()) + r")(?:-?\s*ään\w*|-?\s*röst\w*)?\s*[:=]?\s*(\d{1,3})\b",
    re.IGNORECASE,
)
_VOTE_CUE = re.compile(r"äänest|omröst|röstning|JAA|NEJ", re.IGNORECASE)


def _label_key(lbl: str) -> str | None:
    lbl = lbl.lower()
    for key, pat in _LABELS.items():
        if re.fullmatch(pat, lbl):
            return key
    return None


def extract_votes(text: str | None) -> list[Vote]:
    """Find roll-call results in minutes prose. Requires at least JAA and EI counts in the
    same paragraph, so stray words like 'ei' do not produce votes."""
    if not text or not _VOTE_CUE.search(text):
        return []
    votes: list[Vote] = []
    for para in re.split(r"\n\s*\n|\n(?=\S)", text):
        if not _VOTE_CUE.search(para):
            continue
        counts: dict[str, int] = {}
        for rx, num_first in ((_PAIR_NUM_FIRST, True), (_PAIR_LABEL_FIRST, False)):
            for m in rx.finditer(para):
                num, lbl = (m.group(1), m.group(2)) if num_first else (m.group(2), m.group(1))
                key = _label_key(lbl)
                # Lower-case yes/no words are too common in prose ("ei", "ja"); they count
                # only in upper case or as "jaa-ääntä"/"ja-röster".
                if key in ("jaa", "ei") and lbl.islower() and \
                        not re.search(r"ään|röst", m.group(0), re.IGNORECASE):
                    continue
                if key and key not in counts:
                    counts[key] = int(num)
        if "jaa" in counts and "ei" in counts:
            votes.append(Vote(counts=counts, context=para.strip()[:600]))
    return votes
