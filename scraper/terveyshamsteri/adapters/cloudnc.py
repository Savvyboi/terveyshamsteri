"""CloudNC (CaseM styling), e.g. https://pirha.cloudnc.fi

  /fi-FI/Toimielimet                               bodies
  /fi-FI/Toimielimet/{Body}                        all meetings of a body, grouped by year
  /fi-FI/Toimielimet/{Body}/Kokous_{dmyyyy}        items, participants, minutes PDF
  /fi-FI/content/{item}/{meeting}                  one item; files at /download/noname/{guid}/{n}
"""

from __future__ import annotations

import logging
import re
from urllib.parse import unquote, urljoin, urlsplit

from ..models import Attachment, Body, Item, Meeting, MeetingRef, Participant
from ..text import body_type, heading_kind, html_text, parse_fi_date, slugify, soup
from .base import Adapter, content_after, fill_item_from_text

log = logging.getLogger(__name__)


def _stage(text: str) -> str:
    t = text.lower()
    if "esityslista" in t or "föredragningslista" in t:
        return "agenda"
    return "minutes"


class CloudNCAdapter(Adapter):
    platform = "cloudnc"

    @property
    def locale(self) -> str:
        return self.epoch.get("locale", "sv-FI" if self.language == "sv" else "fi-FI")

    def _abs(self, href: str, page: str | None = None) -> str:
        # Links on CloudNC pages are often relative to the current page.
        return urljoin(page or self.base + "/", href)

    def _path(self, href: str, page: str | None = None) -> list[str]:
        return [unquote(p) for p in urlsplit(self._abs(href, page)).path.strip("/").split("/")]

    @property
    def bodies_segment(self) -> str:
        return self.epoch.get("bodies_path", "Toimielimet" if self.language == "fi" else "Organ")

    # ------------------------------------------------------------ bodies
    def list_bodies(self) -> list[Body]:
        page = f"{self.base}/{self.locale}/{self.bodies_segment}"
        doc = soup(self.fetcher.get(page).text)
        bodies: dict[str, Body] = {}
        for a in doc.find_all("a", href=True):
            p = self._path(a["href"], page)
            if len(p) == 3 and p[0].lower() == self.locale.lower() and p[1].lower() == self.bodies_segment.lower():
                name = a.get_text(" ", strip=True)
                if name:
                    bodies.setdefault(p[2], Body(id=slugify(name), name=name,
                                                 url=self._abs(a["href"], page), type=body_type(name)))
        if not bodies:
            log.warning("no bodies found on %s; first links: %s", page,
                        [a["href"] for a in doc.find_all("a", href=True)][:40])
        return list(bodies.values())

    # ------------------------------------------------------------ meetings
    def list_meetings(self, body: Body) -> list[MeetingRef]:
        doc = soup(self.fetcher.get(body.url).text)
        body_path = self._path(body.url)
        refs: list[MeetingRef] = []
        seen: set[str] = set()
        for a in doc.find_all("a", href=True):
            p = self._path(a["href"], body.url)
            if len(p) != 4 or [x.lower() for x in p[:3]] != [x.lower() for x in body_path[:3]] \
                    or not re.match(r"(Kokous|Möte)_", p[3]):
                continue
            url = self._abs(a["href"], body.url)
            text = a.get_text(" ", strip=True)
            date = parse_fi_date(text)
            if not date or url in seen:
                continue
            seen.add(url)
            refs.append(MeetingRef(body=body, date=date, url=url, stage=_stage(text)))
        return refs

    def fetch_meeting(self, ref: MeetingRef) -> Meeting:
        doc = soup(self.fetcher.get(ref.url).text)
        h1 = doc.find("h1")
        heading = h1.get_text(" ", strip=True) if h1 else ""
        page_text = html_text(doc.body or doc)
        meeting = Meeting(
            id="", region=self.region["id"], body_id=ref.body.id, body_name=ref.body.name,
            date=parse_fi_date(heading) or ref.date, stage=ref.stage, source_url=ref.url,
            language=self.language,
        )
        m = re.search(r"\b(?:klo|kl\.?)\s*(\d{1,2}[.:]\d{2}(?:\s*[-–]\s*\d{1,2}[.:]\d{2})?)", page_text)
        if m:
            meeting.time = m.group(1).replace(".", ":")
        m = re.search(r"\n(?:Paikka|Kokouspaikka|Plats)\s*:?\s*\n?([^\n]{3,150})", page_text)
        if m:
            meeting.place = m.group(1).strip()

        for a in doc.find_all("a", href=True):
            href = self._abs(a["href"], ref.url)
            p = self._path(a["href"], ref.url)
            if "/download/" in href and meeting.pdf_url is None and not meeting.items:
                # The first download link before any item is the minutes/agenda document.
                meeting.pdf_url = href
            elif len(p) == 4 and p[0].lower() == self.locale.lower() and p[1].lower() == "content":
                text = a.get_text(" ", strip=True)
                mm = re.match(r"§\s*(\d+[a-z]?)\s*(.*)", text)
                number, title = (mm.group(1), mm.group(2)) if mm else ("", text)
                if not any(it.source_url == href for it in meeting.items):
                    meeting.items.append(Item(number=number, title=title.strip(), source_url=href))

        meeting.participants = _participants(page_text)
        for item in meeting.items:
            self._fetch_item(item)
        return meeting

    def _fetch_item(self, item: Item) -> None:
        doc = soup(self.fetcher.get(item.source_url).text)
        for a in doc.find_all("a", href=True):
            href = self._abs(a["href"], item.source_url)
            if "/download/" in href:
                title = a.get_text(" ", strip=True) or "Liite"
                if not any(x.url == href for x in item.attachments):
                    item.attachments.append(Attachment(title=title, url=href))
        h1 = doc.find("h1")
        text = content_after(h1) if h1 else html_text(doc.body or doc)
        text = self._strip_intro(item, text)
        if not text.strip():
            item.redacted = True
        fill_item_from_text(item, text, self.epoch.get("newest_first", False))
        if item.attachments:  # the 'Liitteet' block only repeats the file names and sizes
            item.sections = [x for x in item.sections if heading_kind(x.heading) != "attachments"]

    @staticmethod
    def _strip_intro(item: Item, text: str) -> str:
        """Item pages open with the minutes status, '§', the number, the title and a bare
        diary number ('16442/2026' or 'PIRHA 8590/2024'). Keep the diary number, drop the rest."""
        lines = text.split("\n")
        out, i = [], 0
        while i < len(lines) and i < 12:
            ln = lines[i].strip()
            if not ln or ln in (item.number, item.title) or re.fullmatch(r"§\s*\d*[a-z]?", ln) or re.match(
                    r"^(Pöytäkirja|Esityslista|Protokoll|Föredragningslista)\b.*(tarkastettu|justerat|$)", ln):
                i += 1
                continue
            m = re.fullmatch(r"(?:[A-ZÅÄÖ]{2,}\s*)?\d{1,7}/\d{2}\.\d{2}\.\d{2}/\d{4}|(?:[A-ZÅÄÖ]{2,}\s*)?\d{1,7}/\d{4}", ln)
            if m and not item.diary_number:
                item.diary_number = ln
                i += 1
                continue
            break
        return "\n".join(lines[i:])


_GROUP = re.compile(
    r"^(Paikalla olleet jäsenet|Muut paikalla olleet|Poissa olleet jäsenet|Poissa|Jäsenet|"
    r"Närvarande ledamöter|Övriga närvarande|Frånvarande ledamöter|Frånvarande)\s*:?\s*(.*)$",
    re.IGNORECASE,
)


def _participants(page_text: str) -> list[Participant]:
    """Parse the 'Kokouksen osallistujat' block: group labels followed by
    'Firstname Lastname (role)' entries, separated by commas or line breaks."""
    idx = re.search(r"(Kokouksen osallistujat|Mötesdeltagare|Deltagare)", page_text)
    if not idx:
        return []
    block = page_text[idx.end():idx.end() + 8000]
    out: list[Participant] = []
    group: str | None = None
    for line in block.split("\n"):
        line = line.strip()
        if not line:
            continue
        g = _GROUP.match(line)
        if g:
            label = g.group(1).lower()
            group = "absent" if ("poissa" in label or "frånvarande" in label) else (
                "member" if ("jäsen" in label or "ledamöter" in label) else "other")
            line = g.group(2).strip()
            if not line:
                continue
        elif group is None:
            continue
        if re.match(r"^(Pöytäkirja|Esityslista|Protokoll|©|Muutoksenhaku)", line):
            break
        for entry in _split_people(line):
            mm = re.match(r"(.+?)\s*\((.*)\)\s*$", entry) or re.match(r"(.+?)\s+[-–]\s+(.+)$", entry)
            name, role = (mm.group(1), mm.group(2)) if mm else (entry, "")
            name = name.strip(" ,")
            if 3 <= len(name) <= 80 and not re.search(r"\d", name):
                out.append(Participant(name=name, role=role.strip(), group=group))
    return out


def _split_people(line: str) -> list[str]:
    """Split on commas that are not inside parentheses."""
    parts, depth, cur = [], 0, ""
    for ch in line:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        if ch == "," and depth == 0:
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    return [p.strip() for p in parts if p.strip()]
