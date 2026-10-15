"""STT Info press releases, e.g. https://www.sttinfo.fi/uutishuone/69820130/varsinais-suomen-hyvinvointialue-varha

A fallback for regions whose own publishing system blocks crawlers. Varha's Tweb disallows
all robots, but Varha also sends the unverified minutes of its board to STT Info on the day
of the meeting, as a release with the minutes PDF attached:

  /sitemap.xml -> /sitemap-months/{n}.xml  every release of a month, publisherId in each URL
  /tiedote/{id}/{slug}?publisherId=..       release: title names the body and the date
  /files/{publisher}/{release}/{file}/fi    the attached minutes PDF

The PDF text is parsed in memory; the PDF itself is never stored. Only releases whose title
says they carry minutes ('pöytäkirja') are used: agenda releases only summarise the agenda.
"""

from __future__ import annotations

import html
import io
import logging
import re
import unicodedata
from urllib.parse import urljoin

from ..models import Body, Item, Meeting, MeetingRef, Participant
from ..text import body_type, heading_kind, parse_fi_date, slugify, soup
from .base import Adapter, fill_item_from_text

log = logging.getLogger(__name__)

SITE = "https://www.sttinfo.fi"

# "Varhan aluehallituksen 12.10.2026 kokouksen tarkastamaton pöytäkirja"
_MINUTES_TITLE = re.compile(
    r"\b(?P<body>[a-zåäö-]*(?:hallitu|valtuusto|lautakunna|jaosto)\w*)\b.*?"
    r"(?P<date>\d{1,2}\.\d{1,2}\.\d{4}).*\bpöytäkirja\b"
    r"|(?P<date2>\d{1,2}\.\d{1,2}\.\d{4})\s+(?P<body2>[a-zåäö-]*(?:hallitu|valtuusto|lautakunna|jaosto)\w*)\b.*\bpöytäkirja\b",
    re.IGNORECASE,
)

# Genitive forms used in release titles -> body names as written in the minutes.
_NOMINATIVE = [(r"hallituksen$", "hallitus"), (r"valtuuston$", "valtuusto"),
               (r"lautakunnan$", "lautakunta"), (r"jaoston$", "jaosto")]


def _nominative(word: str) -> str:
    w = word.lower()
    for pat, rep in _NOMINATIVE:
        w = re.sub(pat, rep, w)
    return w[:1].upper() + w[1:]


def parse_release_title(title: str) -> tuple[str, str, str] | None:
    """(body name, ISO date, stage) for a minutes release, None for anything else."""
    m = _MINUTES_TITLE.search(title)
    if not m:
        return None
    body = m.group("body") or m.group("body2")
    date = parse_fi_date(m.group("date") or m.group("date2"))
    if not date:
        return None
    stage = "minutes-unverified" if re.search(r"tarkastamaton", title, re.IGNORECASE) else "minutes"
    return _nominative(body), date, stage


class SttInfoAdapter(Adapter):
    platform = "sttinfo"

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._refs: list[tuple[Body, str, str, str]] | None = None
        self._pages: dict[str, str] = {}

    @property
    def newsroom(self) -> str:
        return self.epoch["newsroom_url"].rstrip("/")

    # ------------------------------------------------------------ listing
    def _releases(self) -> list[tuple[str, str]]:
        """(Finnish title, absolute url) of the publisher's releases that look like minutes, back
        to the region's start date. The newsroom's own JSON listing leaves the minutes releases
        out, so they are found in STT Info's monthly sitemaps (which carry the publisher id in
        each URL) and the title is read from the release page."""
        since = str(self.region.get("since", "2025-06-01"))
        index = self.fetcher.get(f"{SITE}/sitemap.xml").text
        months = re.findall(r"<loc>([^<]*/sitemap-months/\d+\.xml)</loc>\s*<lastmod>([^<]+)</lastmod>", index)
        urls: list[str] = []
        skipped: list[str] = []  # body-related releases without minutes, logged to spot new title patterns
        pid = re.escape(str(self.epoch["publisher_id"]))
        for loc, lastmod in months:
            if lastmod[:10] < since:  # a monthly sitemap is stamped with the end of its month
                continue
            for u in re.findall(r"<loc>([^<]+)</loc>", self.fetcher.get(loc).text):
                u = html.unescape(u)
                if not re.search(rf"[?&]publisherId={pid}&lang=fi$", u) or u in urls:
                    continue
                if "poytakirja" in u:
                    urls.append(u)
                elif re.search(r"hallitu|valtuust|lautakun|jaosto|kokou", u):
                    skipped.append(u.split("/tiedote/")[-1].split("?")[0])
        if skipped:
            log.info("%d body releases without 'pöytäkirja' skipped: %s", len(skipped), skipped[:40])
        out = []
        for u in urls:
            page = self.fetcher.get(u).text
            self._pages[u] = page
            h1 = soup(page).find("h1")
            if h1:
                out.append((unicodedata.normalize("NFC", h1.get_text(" ", strip=True)), u))
        return out

    def _minutes_refs(self) -> list[tuple[Body, str, str, str]]:
        if self._refs is None:
            self._refs = []
            seen = set()
            releases = self._releases()
            for title, url in releases:
                parsed = parse_release_title(title)
                if not parsed:
                    log.warning("minutes release title not understood: %s", ascii(title))
                if not parsed or url in seen:
                    continue
                seen.add(url)
                name, date, stage = parsed
                body = Body(id=slugify(name), name=name, url=self.newsroom, type=body_type(name))
                self._refs.append((body, date, url, stage))
            log.info("%d releases, %d with minutes", len(releases), len(self._refs))
        return self._refs

    def list_bodies(self) -> list[Body]:
        bodies: dict[str, Body] = {}
        for body, *_ in self._minutes_refs():
            bodies.setdefault(body.id, body)
        return list(bodies.values())

    def list_meetings(self, body: Body) -> list[MeetingRef]:
        return [MeetingRef(body=b, date=d, url=u, stage=s)
                for b, d, u, s in self._minutes_refs() if b.id == body.id]

    # ------------------------------------------------------------ meeting
    def fetch_meeting(self, ref: MeetingRef) -> Meeting:
        doc = soup(self._pages.pop(ref.url, None) or self.fetcher.get(ref.url).text)
        pdf_url = None
        for a in doc.find_all("a", href=True):
            if re.match(r"^(?:https://www\.sttinfo\.fi)?/files/", a["href"]) and \
                    re.search(r"pöytäkirja|poytakirja|\.pdf", a.get_text(" ", strip=True), re.IGNORECASE):
                pdf_url = urljoin(SITE, a["href"])
                break
        meeting = Meeting(id="", region=self.region["id"], body_id=ref.body.id, body_name=ref.body.name,
                          date=ref.date, stage=ref.stage, source_url=ref.url, pdf_url=pdf_url,
                          language=self.language)
        if not pdf_url:
            log.warning("no minutes PDF on %s", ref.url)
            return meeting
        text = pdf_text(self.fetcher.get(pdf_url).content)
        parse_minutes(text, meeting)
        return meeting


def pdf_text(data: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


# ---------------------------------------------------------------- PDF text

# Running header on every page:
#   Varsinais-Suomen hyvinvointialue Pöytäkirja
#     Julkinen
#   Aluehallitus 12.10.2026 19/2026
#    7
_HEADER_TOP = re.compile(r"^.{3,80}\s(?:Pöytäkirja|Esityslista)\s*$")
_HEADER_BODY = re.compile(r"^\s*(?P<body>\S.*?)\s+\d{1,2}\.\d{1,2}\.\d{4}\s+\d+/\d{4}\s*$")
_HEADER_NOISE = re.compile(r"^\s*(?:Julkinen|Ei julkinen|Salassa pidettävä|Osittain salassa pidettävä|\d{1,3})?\s*$")
_ITEM = re.compile(r"^§\s*(\d+[a-z]?)\s+(\S.*)$")
_APPEAL = re.compile(r"^\s*(?:Muutoksenhakuohjee?t?|MUUTOKSENHAKUOHJEE?T?|Oikaisuvaatimusohje\b.*|"
                     r"Valitusosoitus\b.*|I{1,3}\s+\S.*(?:oikaisuvaatimus|valitus)ohje)\s*$", re.IGNORECASE)


def _strip_headers(lines: list[str]) -> list[str]:
    """Remove the running page headers and the separators between handlings of an item."""
    out: list[str] = []
    i = 0
    while i < len(lines):
        # '______ / Aluehallitus 8.9.2025' separates an earlier body's handling from this one's.
        if re.fullmatch(r"\s*_{10,}\s*", lines[i]) and i + 1 < len(lines) and \
                re.fullmatch(r"\s*\S.*\s\d{1,2}\.\d{1,2}\.\d{4}\s*", lines[i + 1]):
            i += 2
            continue
        if _HEADER_TOP.match(lines[i]):
            j = i + 1
            # The header is at most four more lines: classification, body/date/number, page.
            while j < len(lines) and j <= i + 5 and (_HEADER_NOISE.match(lines[j]) or _HEADER_BODY.match(lines[j])):
                j += 1
            if any(_HEADER_BODY.match(lines[k]) for k in range(i + 1, j)):
                i = j
                continue
        out.append(lines[i])
        i += 1
    return out


def _blank(line: str) -> bool:
    return not line.strip()


def parse_minutes(text: str, meeting: Meeting) -> Meeting:
    """Fill time, place, participants and items from the text of a Tweb minutes PDF."""
    raw = text.replace("\xa0", " ").split("\n")
    m = next((_HEADER_BODY.match(ln) for ln in raw if _HEADER_BODY.match(ln)), None)
    if m:
        meeting.body_name = m.group("body").strip()
    lines = _strip_headers(raw)

    front_end = next((i for i, ln in enumerate(lines) if _ITEM.match(ln.strip())), len(lines))
    front = lines[:front_end]
    for ln in front:
        mm = re.match(r"^\s*Kokousaika\s+\d{1,2}\.\d{1,2}\.\d{4}\s+klo\s+(\d{1,2}[:.]\d{2}(?:\s*[-–]\s*\d{1,2}[:.]\d{2})?)", ln)
        if mm:
            meeting.time = re.sub(r"\s*[-–]\s*", " - ", mm.group(1).replace(".", ":"))
        mm = re.match(r"^\s*Kokouspaikka\s+(\S.{2,150})$", ln)
        if mm:
            meeting.place = mm.group(1).strip()
    meeting.participants = _participants(front)

    # Items run from "§ n Title" to the next item; the appeal instructions end the last one.
    starts = [i for i in range(front_end, len(lines)) if _ITEM.match(lines[i].strip())]
    end_all = next((i for i in range(starts[-1] if starts else len(lines), len(lines))
                    if _APPEAL.match(lines[i])), len(lines))
    for n, s in enumerate(starts):
        e = starts[n + 1] if n + 1 < len(starts) else end_all
        number, title = _ITEM.match(lines[s].strip()).groups()
        k = s + 1
        while k < e and not _blank(lines[k]):  # titles wrap until the first empty line
            title += " " + lines[k].strip()
            k += 1
        body = "\n".join(ln.strip() for ln in lines[k:e])
        body = re.sub(r"\n{3,}", "\n\n", body).strip()
        item = Item(number=number, title=re.sub(r"\s+", " ", title).strip(),
                    source_url=f"{meeting.source_url}#{number}", pdf_url=meeting.pdf_url)
        if not body:
            item.redacted = True
        fill_item_from_text(item, body)
        prep = next((x.text for x in item.sections if heading_kind(x.heading) == "preparer"), None)
        if prep:  # PDF lines wrap mid-phrase, so the line-per-person reading does not apply
            item.preparer = re.sub(r"\s+", " ", prep).strip()[:300]
        meeting.items.append(item)
    return meeting


_GROUP = [(re.compile(r"^\s*Jäsenet\s*$"), "member"),
          (re.compile(r"^\s*(?:Muut osallistujat|Muut läsnäolijat|Kutsuttuna|Asiantuntijat)\s*$"), "other"),
          (re.compile(r"^\s*Poissa\s*$"), "absent")]
_PERSON = re.compile(r"^([A-ZÅÄÖ][\wåäöé'-]+(?:\s+[A-ZÅÄÖ][\wåäöé'-]+){1,2})(?=,|\s|$)\s*,?\s*(.*)$")
_FRONT_END = re.compile(r"^\s*(?:Pöytäkirjan|Allekirjoitukset|Käsitellyt asiat|Käsiteltävät asiat)\b")


def _participants(front: list[str]) -> list[Participant]:
    out: list[Participant] = []
    group = None
    started = False
    for ln in front:
        s = ln.strip()
        if re.match(r"^Osallistujat\b", s):
            started = True
            continue
        if not started or not s:
            continue
        if _FRONT_END.match(s):
            break
        g = next((grp for pat, grp in _GROUP if pat.match(s)), None)
        if g:
            group = g
            continue
        if group is None:
            continue
        p = _PERSON.match(s)
        if p:
            role = p.group(2).strip(" ,")
            out.append(Participant(name=p.group(1), role=role, group=group))
        elif out:  # a wrapped continuation of the previous person's role
            prev = out[-1]
            prev.role = f"{prev.role} {s}".strip(" ,")
    return out
