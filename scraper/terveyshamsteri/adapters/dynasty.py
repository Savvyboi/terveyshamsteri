"""Dynasty 10 tietopalvelu (Innofactor), e.g. https://hyvaks-d10julk.oncloudos.com

  /cgi/DREQUEST.PHP?page=meeting_handlers          bodies, latest meeting each
  /cgi/DREQUEST.PHP?page=meetings&id={body}        all meetings of a body, grouped by year
  /cgi/DREQUEST.PHP?page=meeting&id={meeting}      items, participants, minutes PDF
  /cgi/DREQUEST.PHP?page=meetingitem&id={m}-{n}    one item; attachments at /kokous/{m}-{n}-{k}.PDF
"""

from __future__ import annotations

import re
from urllib.parse import parse_qs, urljoin, urlsplit

from ..models import Attachment, Body, Item, Meeting, MeetingRef, Participant
from ..text import body_type, html_text, parse_fi_date, slugify, soup
from .base import Adapter, content_after, cut_navigation, fill_item_from_text, role_group


def _q(href: str, key: str) -> str | None:
    v = parse_qs(urlsplit(href).query).get(key)
    return v[0] if v else None


def _stage(text: str) -> str:
    t = text.lower()
    if "esityslista" in t or "föredragningslista" in t:
        return "agenda"
    return "minutes"


class DynastyAdapter(Adapter):
    platform = "dynasty"

    def url(self, page: str, id_: str | int = "") -> str:
        return f"{self.base}/cgi/DREQUEST.PHP?page={page}&id={id_}"

    # ------------------------------------------------------------ bodies
    def list_bodies(self) -> list[Body]:
        page = self.url("meeting_handlers")
        doc = soup(self.fetcher.get(page).text)
        bodies: dict[str, Body] = {}
        for a in doc.find_all("a", href=True):
            href = a["href"]
            if _q(href, "page") != "meetings":
                continue
            name = a.get_text(" ", strip=True)
            bid = _q(href, "id")
            if not name or not bid:
                continue
            bodies.setdefault(bid, Body(id=slugify(name), name=name,
                                        url=urljoin(page, href), type=body_type(name)))
        return list(bodies.values())

    # ------------------------------------------------------------ meetings
    def list_meetings(self, body: Body) -> list[MeetingRef]:
        doc = soup(self.fetcher.get(body.url).text)
        refs: list[MeetingRef] = []
        seen: set[str] = set()
        for a in doc.find_all("a", href=True):
            href = a["href"]
            if _q(href, "page") != "meeting":
                continue
            mid = _q(href, "id")
            if not mid or mid in seen:
                continue
            row = a.find_parent("tr") or a.parent
            date = parse_fi_date(row.get_text(" ", strip=True)) if row else None
            if not date:
                continue
            seen.add(mid)
            refs.append(MeetingRef(body=body, date=date, url=urljoin(body.url, href),
                                   stage=_stage(a.get_text(" ", strip=True))))
        return refs

    def fetch_meeting(self, ref: MeetingRef) -> Meeting:
        r = self.fetcher.get(ref.url)
        doc = soup(r.text)
        mid = _q(ref.url, "id") or ""
        h1 = doc.find("h1")
        heading = h1.get_text(" ", strip=True) if h1 else ""
        m = re.search(r"klo\s*([\d.:]+\s*-\s*[\d.:]+|[\d.:]+)", heading)
        meeting = Meeting(
            id="", region=self.region["id"], body_id=ref.body.id, body_name=ref.body.name,
            date=parse_fi_date(heading) or ref.date, stage=_stage(heading or ref.stage),
            source_url=ref.url, time=m.group(1).replace(".", ":") if m else None,
            language=self.language,
        )
        for a in doc.find_all("a", href=True):
            if re.search(rf"/kokous/{re.escape(mid)}\.pdf$", a["href"], re.IGNORECASE):
                meeting.pdf_url = urljoin(ref.url, a["href"])
                break

        # Agenda items: number in the first cell, title link to page=meetingitem
        for a in doc.find_all("a", href=True):
            if _q(a["href"], "page") != "meetingitem":
                continue
            row = a.find_parent("tr")
            number = ""
            if row:
                first = row.find(["td", "th"])
                number = first.get_text(" ", strip=True) if first else ""
            url = urljoin(ref.url, a["href"])
            if any(it.source_url == url for it in meeting.items):
                continue
            meeting.items.append(Item(number=number, title=a.get_text(" ", strip=True), source_url=url))

        meeting.participants = self._participants(doc)
        for item in meeting.items:
            self._fetch_item(item)
        return meeting

    def _participants(self, doc) -> list[Participant]:
        out: list[Participant] = []
        for table in doc.find_all("table"):
            head = table.get_text(" ", strip=True)[:80].lower()
            if not (head.startswith("osallistuja") or head.startswith("deltagare")):
                continue
            for tr in table.find_all("tr"):
                cells = [c.get_text(" ", strip=True) for c in tr.find_all(["td"])]
                if len(cells) >= 2 and cells[0] and not cells[0].lower().startswith(("osallistuja", "deltagare")):
                    role = cells[1]
                    out.append(Participant(name=cells[0], role=role, group=role_group(role)))
        return out

    def _fetch_item(self, item: Item) -> None:
        doc = soup(self.fetcher.get(item.source_url).text)
        iid = _q(item.source_url, "id") or ""
        for a in doc.find_all("a", href=True):
            href = urljoin(item.source_url, a["href"])
            path = urlsplit(href).path
            mm = re.search(r"/kokous/([\w-]+)\.pdf$", path, re.IGNORECASE)
            if not mm:
                continue
            fid = mm.group(1)
            if fid == iid:
                item.pdf_url = href
            elif fid == f"{iid}-0":
                continue  # muutoksenhakuohje (appeal instructions), same for every item
            elif fid.startswith(iid + "-"):
                title = a.get_text(" ", strip=True) or fid
                if not any(x.url == href for x in item.attachments):
                    item.attachments.append(Attachment(title=title, url=href))
        # The PDF links (appeal instructions, item PDF, attachments) are listed separately;
        # drop them so their link texts do not read as section headings.
        for a in doc.find_all("a", href=True):
            if re.search(r"/kokous/[\w-]+\.pdf$", a["href"], re.IGNORECASE):
                a.decompose()
        text, diary = _item_text(doc)
        item.diary_number = item.diary_number or diary
        if not text.strip():
            item.redacted = True
        fill_item_from_text(item, text)



_SDT_HEADER = re.compile(r"Dynasty_(?:Title|Board|Date|Paragraph|Publicity|SecrecyBasis|CaseNumber)")
_TAB = re.compile(r"display:\s*inline-block")


def _item_text(doc) -> tuple[str, str | None]:
    """Item text and diary number.

    Dynasty pages hold the navigation and attachment tables and then the item itself as a
    Word export in div.htmCnt. Its header fields are tagged (-aw-sdt-tag:'Dynasty_Board',
    'Dynasty_CaseNumber'...), and every section starts with a hanging-indent paragraph:
    the label ('Valmistelija', 'Päätösehdotus'), a tab span, then the text."""
    # Older Dynasty 10.5 builds use div.htmCnt, newer ones div.data-part-block-htm.
    cnt = doc.select_one("div.htmCnt") or doc.select_one("div.data-part-block-htm")
    if cnt is None:
        h1 = doc.find("h1")
        text = content_after(h1) if h1 else html_text(doc.body or doc)
        return cut_navigation(re.sub(r"\n©\s*$", "", text.strip())).strip(), None
    case = cnt.find(style=re.compile(r"Dynasty_CaseNumber"))
    diary = case.get_text(" ", strip=True).replace("\xa0", " ").strip() or None if case else None
    for el in cnt.find_all(style=_SDT_HEADER):
        el.decompose()
    for el in cnt.find_all(["svg", "img"]):
        el.decompose()
    for par in cnt.find_all("p"):
        tab = par.find("span", style=_TAB, recursive=False)
        if tab is None:
            continue
        label = "".join(t.get_text() for t in tab.find_previous_siblings()).replace("\xa0", " ").strip()
        if label and len(label) < 60:
            tab.replace_with("\n")
    return html_text(cnt).strip(), diary
