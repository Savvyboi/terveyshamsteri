"""Text helpers shared by all adapters: slugs, dates, body types, privacy scrubbing,
section splitting and rule-based vote extraction."""

from __future__ import annotations

import re
import unicodedata
from datetime import date

from bs4 import BeautifulSoup, Comment, NavigableString, Tag

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

_EMAIL = re.compile(r"[\w.+-]+(?:@|\s?\((?:at|ät|a)\)\s?)[\w-]+(?:\.[\w-]+)+")
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
    text = re.sub(r"[, \t]*\b(?:puh|p|tel)\.?[ \t]*(?=,|\n|$)", "", text)  # label left behind
    text = re.sub(r"[ \t]+,", ",", text)
    text = re.sub(r",(?:[ \t]*,)+", ",", text)
    text = re.sub(r",[ \t]*(?=\n|$)", "", text)
    text = re.sub(r"[ \t]{2,}", " ", text)
    return text.strip()


# ---------------------------------------------------------------- html -> text

_BLOCK = {"p", "div", "br", "li", "tr", "h1", "h2", "h3", "h4", "h5", "h6", "table", "ul", "ol",
          "section", "article", "blockquote", "pre", "dd", "dt"}


def html_text(node: Tag | NavigableString) -> str:
    """Text with paragraph breaks preserved (BeautifulSoup's get_text flattens them)."""
    out: list[str] = []

    def walk(n):
        if isinstance(n, Comment):
            return
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
    "proposal": [r"päätösehdotus", r"ehdotus", r"esitys", r"förslag", r"beslutsförslag",
                 r"[\wåäö-]+n (?:päätös)?ehdotus", r"esittelijän ehdotus", r"päätösesitys",
                 r"[\wåäö-]+n päätösesitys"],
    "decision": [r"päätös", r"beslut"],
    "discussion": [r"kokouskäsittely", r"käsittely", r"behandling", r"behandling under mötet"],
    "preparer": [r"valmistelija(?:t)?", r"valmistelija(?:t)? ja lisätietojen antaja(?:t)?", r"beredning", r"beredare", r"lisätiedot"],
    "presenter": [r"esittelijä", r"föredragande"],
    "attachments": [r"liitteet", r"bilagor", r"oheismateriaali", r"oheisaineisto"],
    "appeal": [r"muutoksenhaku", r"muutoksenhakuohje", r"sökande av ändring", r"besvärsanvisning"],
    "basis": [r"perustelut", r"asian tausta", r"motivering", r"toimivalta", r"selostus asiasta", r"selostus",
              r"ärendebeskrivning", r"redogörelse"],
    "other": [r"tiedoksi", r"toimenpiteet", r"täytäntöönpano", r"för kännedom",
              r"verkställighet"],
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


def _label_lines(text: str) -> list[str]:
    """Lines with labels normalised: 'Päätösehdotus: Aluehallitus ...' becomes two lines, and a
    label wrapped over two lines ('Toimialajohtajan' / 'päätösesitys') becomes one."""
    lines = text.split("\n")
    out: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        j = i + 1
        if j < len(lines) and not lines[j].strip():
            j += 1  # paragraphs are separated by a blank line
        nxt = lines[j].strip() if j < len(lines) else ""
        if re.fullmatch(r"[A-ZÅÄÖ][\wåäö-]+n", line) and nxt and heading_kind(f"{line} {nxt}"):
            out.append(f"{line} {nxt}")
            i = j + 1
            continue
        m = re.match(r"([A-ZÅÄÖ][\wåäö -]{2,38}?)\s*:\s+(\S.*)$", line)
        if m and heading_kind(m.group(1)) and heading_kind(m.group(1)) not in ("preparer", "presenter"):
            out.extend([m.group(1), m.group(2)])
        else:
            out.append(lines[i])
        i += 1
    return out


def split_sections(text: str) -> list[Section]:
    """Split item text on lines that are just a known heading ('Päätös', 'Kokouskäsittely'...).
    Text before the first heading goes into a section with an empty heading."""
    sections: list[Section] = []
    heading, buf = "", []
    for line in _label_lines(text):
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


def current_of(sections: list[Section], kind: str, newest_first: bool = False) -> str | None:
    """The section of a kind that belongs to the meeting being read. Minutes repeat
    proposal/decision for every body that handled the case, usually oldest first, so the
    last one is current. Some sites list the handlings newest first instead."""
    for s in (sections if newest_first else reversed(sections)):
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
# "47 personer JA", "4 personer röstade blankt"
_PAIR_NUM_FIRST = re.compile(
    r"(\d{1,3})\s*(?:kpl\s*|(?:personer|ledamöter)\s+(?:röstade\s+)?)?(" + "|".join(_LABELS.values()) + r")"
    r"(?:\s*-?\s*ään\w*|\s*-?\s*röst\w*)?\b",
    re.IGNORECASE,
)
# "JAA 42", "JAA ääniä oli 8"
_PAIR_LABEL_FIRST = re.compile(
    r"\b(" + "|".join(_LABELS.values()) + r")(?:\s*-?\s*ään\w*|\s*-?\s*röst\w*)?\s*(?:oli\s*)?[:=]?\s*(\d{1,3})\b",
    re.IGNORECASE,
)
_VOTE_CUE = re.compile(r"äänest|omröst|röstning|JAA|NEJ", re.IGNORECASE)


def _label_key(lbl: str) -> str | None:
    lbl = lbl.lower()
    for key, pat in _LABELS.items():
        if re.fullmatch(pat, lbl):
            return key
    return None


_ZW = re.compile(r"[\u200b\u200c\u200d\u2060\ufeff]")

_NUMBER_WORDS = {
    "nolla": 0, "yksi": 1, "yhden": 1, "kaksi": 2, "kolme": 3, "neljä": 4, "viisi": 5, "kuusi": 6,
    "seitsemän": 7, "kahdeksan": 8, "yhdeksän": 9, "kymmenen": 10, "yksitoista": 11, "kaksitoista": 12,
    "kolmetoista": 13, "neljätoista": 14, "viisitoista": 15, "kuusitoista": 16, "seitsemäntoista": 17,
    "kahdeksantoista": 18, "yhdeksäntoista": 19, "kaksikymmentä": 20,
}
_NW = "|".join(sorted(_NUMBER_WORDS, key=len, reverse=True))
# "Seitsemän (7) Jaa-ääntä" -> "7 Jaa-ääntä"
_WORD_AND_DIGITS = re.compile(r"\b(?:" + _NW + r")\s*\((\d{1,3})\)", re.IGNORECASE)
# "kuusi jaa-ääntä", "Jaa: kahdeksan ääntä"
_WORD_BEFORE = re.compile(r"\b(" + _NW + r")(?=\s+(?:jaa|ei|tyhj|ään))", re.IGNORECASE)
_WORD_AFTER = re.compile(r"(\b(?:jaa|ei|tyhjää?)(?:\s*-?\s*ään\w*)?\s*[:,]?\s*)(" + _NW + r")\b", re.IGNORECASE)


def _digits(text: str) -> str:
    """Write vote counts given in words as digits."""
    text = _WORD_AND_DIGITS.sub(r"\1", text)
    text = _WORD_BEFORE.sub(lambda m: str(_NUMBER_WORDS[m.group(1).lower()]), text)
    return _WORD_AFTER.sub(lambda m: m.group(1) + str(_NUMBER_WORDS[m.group(2).lower()]), text)

# One line of a roll-call result: "JAA 13 ääntä (Name, Name)", "EI (Liedes) 5 ääntä: Name, Name",
# "Tyhjää 1", "JA-röster 30 (…)". Each count is on its own line in many minutes.
_LINE = re.compile(
    r"^[ \t]*[”\"'“]?(?P<lbl>JAA|EI|TYHJÄÄ?|TYHJIÄ|POISSA|JA|NEJ|BLANKA|BLANKT|BLANK|FRÅNVARANDE)[”\"'“]?"
    r"(?P<suffix>[ \t]*-[ \t]*(?:ään|röst)\w*|(?:ään|röst)\w*|[ \t]+(?:ään|röst)\w*)?\b(?:[ \t]+oli)?"
    r"(?:[ \t]*\([^)\n]{0,80}\))?[ \t]*[:=,–-]?[ \t]*(?P<n>\d{1,3}\b|[-–](?=[ \t]*$))"
    r"[ \t]*(?P<unit>kpl\.?|ään\w*|röst\w*|st\.?)?\.?"
    r"[ \t]*(?:\((?P<names>[^)\n]*)\)|:[ \t]*(?P<names2>[^\n]+))?",
    re.IGNORECASE | re.MULTILINE,
)
# "… voitti äänin 7 (Baumgartner, …) – 6 (Edgren, …)" or "”Jaa” voitti äänin 54-5".
_WON = re.compile(
    r"(?P<who>[^.,;\n]{1,80}?)\s+(?:voitti|vann)\s+(?:ää/?nin|rösterna|med rösterna)\s+"
    r"(?P<a>\d{1,3})\s*(?:\((?P<an>[^)\n]*)\))?\s*[–—-]\s*(?P<b>\d{1,3})\s*(?:\((?P<bn>[^)\n]*)\))?",
    re.IGNORECASE,
)
_SIDE = re.compile(r"(?P<who>[^.,;\n]{1,120}?)\s+(?:kannattavat|kannattaneet|som understöder|som stöder)\s+(?:äänestivät|äänestävät|röstade|röstar)\s+[”\"'“]?(?P<lbl>jaa|ei|ja|nej)\b",
                   re.IGNORECASE)


def _names(raw: str | None) -> list[str]:
    if not raw:
        return []
    parts = re.split(r",|;|\s+(?:ja|och)\s+", raw)
    return [p.strip(" .") for p in parts if p.strip(" .") and not p.strip(" .").isdigit()]


def _line_votes(text: str, covered: set[str]) -> list[Vote]:
    """Votes written one count per line, possibly with the voters' names. Adds the lines it
    used to `covered`, so the paragraph fallback does not count the same vote again."""
    lines = text.split("\n")
    votes: list[Vote] = []
    block: dict[str, int] = {}
    names: dict[str, list[str]] = {}
    first = last = -10

    def flush():
        if "jaa" in block and "ei" in block:
            covered.update(l.strip() for l in lines[first:last + 1] if l.strip())
            ctx = "\n".join(l for l in lines[max(0, first - 2):last + 1] if l.strip())
            votes.append(Vote(counts=dict(block), context=ctx[:600], names={k: v for k, v in names.items() if v}))
        block.clear()
        names.clear()

    for i, line in enumerate(lines):
        m = _LINE.match(line)
        if not m:
            continue
        lbl = m.group("lbl")
        key = _label_key(lbl)
        # Yes/no words in lower case are too common in prose; they count only with a unit.
        # "Jaa: 8" at the start of a line is a count too.
        if key in ("jaa", "ei") and not (lbl.isupper() or lbl.istitle()) and not (m.group("suffix") or m.group("unit")):
            continue
        if not key:
            continue
        if i - last > 3 or key in block:
            flush()
            first = i
        block[key] = 0 if m.group("n") in "-–" else int(m.group("n"))
        names[key] = _names(m.group("names") or m.group("names2"))
        last = i
    flush()
    return votes


def _won_votes(text: str, covered: set[str]) -> list[Vote]:
    """'X voitti äänin 7 – 6': the winner's side is worked out from the voting proposal."""
    votes = []
    for para in text.split("\n"):
        for m in _WON.finditer(para):
            who = m.group("who").lower()
            side = None
            lbl = re.search(r"[”\"'“](jaa|ei|ja|nej)[”\"'“]|^(jaa|ei|ja|nej)$", who.strip())
            if lbl:
                side = _label_key(lbl.group(1) or lbl.group(2))
            else:
                stem = re.findall(r"\w{4,}", who)
                for s in _SIDE.finditer(para):
                    if stem and any(w[:5] in s.group("who").lower() for w in stem[-2:]):
                        side = _label_key(s.group("lbl"))
                        break
            if side not in ("jaa", "ei"):
                continue
            other = "ei" if side == "jaa" else "jaa"
            counts = {side: int(m.group("a")), other: int(m.group("b"))}
            names = {side: _names(m.group("an")), other: _names(m.group("bn"))}
            votes.append(Vote(counts={k: counts[k] for k in ("jaa", "ei")}, context=para.strip()[:600],
                              names={k: v for k, v in names.items() if v}))
            covered.add(para.strip())
    return votes


def extract_votes(text: str | None) -> list[Vote]:
    """Find roll-call results in minutes prose. A vote needs at least a JAA and an EI count
    close together, so stray words like 'ei' do not produce votes."""
    if not text:
        return []
    text = _ZW.sub("", text)
    if not _VOTE_CUE.search(text):
        return []
    text = _digits(text)
    covered: set[str] = set()
    votes = _line_votes(text, covered) + _won_votes(text, covered)
    for para in re.split(r"\n\s*\n|\n(?=\S)", text):
        if not _VOTE_CUE.search(para) or any(l.strip() in covered for l in para.split("\n")):
            continue
        counts: dict[str, int] = {}
        for rx, num_first in ((_PAIR_NUM_FIRST, True), (_PAIR_LABEL_FIRST, False)):
            for m in rx.finditer(para):
                num, lbl = (m.group(1), m.group(2)) if num_first else (m.group(2), m.group(1))
                key = _label_key(lbl)
                if key in ("jaa", "ei") and lbl.islower() and \
                        not re.search(r"ään|röst", m.group(0), re.IGNORECASE):
                    continue
                if key and key not in counts:
                    counts[key] = int(num)
        if "jaa" in counts and "ei" in counts:
            votes.append(Vote(counts=counts, context=para.strip()[:600]))
    return votes
