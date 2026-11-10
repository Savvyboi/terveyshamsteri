"""M-Files meeting publishing (Kokoukset), e.g. https://mfiles.ekhva.fi/Kokoukset/ekhva/

  /Kokoukset/{site}/                                     bodies, latest meeting each
  /Kokoukset/{site}/{body}                               all meetings of a body by year: date,
                                                         agenda or minutes link, attachments
  /Kokoukset/{site}/{body}/{meeting}                     items ('§21 Title' or '1 Title') with
                                                         their attachments, whole-meeting PDF
  /Kokoukset/{site}/{body}/{meeting}/{case}/download/{doc}   one item or attachment as PDF

The item pages only show the PDF converted to positioned HTML, so the item text is read from
its PDF, in memory; the PDF itself is never stored. Etelä-Karjala's host disallows crawlers in
robots.txt, so the region config marks it `gentle` and every request is slow (see http.py).
"""

from __future__ import annotations

import logging
import re
from urllib.parse import urljoin, urlsplit

from ..http import HostBackedOff
from ..models import Attachment, Body, Item, Meeting, MeetingRef, Participant
from ..text import body_type, parse_fi_date, slugify, soup
from .base import Adapter, fill_item_from_text, role_group
from .sttinfo import pdf_text

log = logging.getLogger(__name__)


def _stage(text: str) -> str:
    t = text.lower()
    if "esityslista" in t or "föredragningslista" in t:
        return "agenda"
    return "minutes"


class MFilesAdapter(Adapter):
    platform = "mfiles"

    @property
    def root(self) -> str:
        """https://host/Kokoukset/{site} (links on the site use this capitalisation)."""
        entry = self.epoch.get("entry_url", self.base + "/Kokoukset/")
        parts = urlsplit(entry)
        segs = [s for s in parts.path.split("/") if s]
        site = segs[1] if len(segs) > 1 else self.epoch.get("site", "")
        return f"{parts.scheme}://{parts.netloc}/Kokoukset/{site}"

    def _segments(self, href: str, page: str) -> list[str]:
        path = urlsplit(urljoin(page, href)).path
        root = urlsplit(self.root).path
        if not path.lower().startswith(root.lower() + "/"):
            return []
        return [s for s in path[len(root) + 1:].split("/") if s]

    # ------------------------------------------------------------ bodies
    def list_bodies(self) -> list[Body]:
        page = self.root + "/"
        doc = soup(self.fetcher.get(page).text)
        bodies: dict[str, Body] = {}
        for a in doc.find_all("a", href=True):
            segs = self._segments(a["href"], page)
            if len(segs) == 1 and segs[0].isdigit():
                name = a.get_text(" ", strip=True)
                if name:
                    bodies.setdefault(segs[0], Body(id=slugify(name), name=name,
                                                    url=urljoin(page, a["href"]), type=body_type(name)))
        if not bodies:
            log.warning("no bodies found on %s", page)
        return list(bodies.values())

    # ------------------------------------------------------------ meetings
    def list_meetings(self, body: Body) -> list[MeetingRef]:
        doc = soup(self.fetcher.get(body.url).text)
        refs: list[MeetingRef] = []
        seen: set[str] = set()
        for tr in doc.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            date = parse_fi_date(cells[0].get_text(" ", strip=True))
            a = cells[1].find("a", href=True)
            if not date or not a:
                continue
            if len(self._segments(a["href"], body.url)) != 2:
                continue
            url = urljoin(body.url, a["href"])
            if url in seen:
                continue
            seen.add(url)
            refs.append(MeetingRef(body=body, date=date, url=url, stage=_stage(a.get_text(" ", strip=True))))
        return refs

    def fetch_meeting(self, ref: MeetingRef) -> Meeting:
        doc = soup(self.fetcher.get(ref.url).text)
        meeting = Meeting(id="", region=self.region["id"], body_id=ref.body.id, body_name=ref.body.name,
                          date=ref.date, stage=ref.stage, source_url=ref.url, language=self.language)
        h3 = doc.find(["h3", "h1", "h2"])
        if h3:
            meeting.date = parse_fi_date(h3.get_text(" ", strip=True)) or ref.date
        for a in doc.find_all("a", href=True):
            segs = self._segments(a["href"], ref.url)
            if len(segs) == 5 and segs[2] == "0" and segs[3] == "download":
                meeting.pdf_url = urljoin(ref.url, a["href"])

        for tr in doc.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) < 2:
                continue
            link = cells[0].find("a", href=True)
            if not link or len(self._segments(link["href"], ref.url)) != 5:
                continue
            text = link.get_text(" ", strip=True)
            mm = re.match(r"^§?\s*(\d+[a-z]?)\.?\s+(.*)$", text)
            number, title = (mm.group(1), mm.group(2)) if mm else ("", text)
            view = urljoin(ref.url, link["href"])
            item = Item(number=number, title=title.strip(), source_url=view, pdf_url=_download(view))
            for att in cells[1].find_all("a", href=True):
                if len(self._segments(att["href"], ref.url)) == 5:
                    item.attachments.append(Attachment(title=att.get_text(" ", strip=True),
                                                       url=_download(urljoin(ref.url, att["href"]))))
            meeting.items.append(item)

        for item in meeting.items:
            if re.search(r"muutoksenhaku|besvärsanvisning", item.title, re.IGNORECASE):
                continue  # boilerplate appeal instructions, not a decision
            try:
                text = item_text(pdf_text(self.fetcher.get(item.pdf_url).content), item)
            except HostBackedOff:
                raise
            except Exception as e:  # noqa: BLE001 - keep the meeting when one PDF fails
                log.warning("item PDF failed %s: %s", item.pdf_url, e)
                continue
            if not text.strip():
                item.redacted = True
                continue
            # The diary number is a bare line near the top: 'EKHVA/6531/00.01.04.30/2025'
            dno = re.search(r"^([A-ZÅÄÖ]{2,}[\w-]*/\d+/[\d.]+/\d{4})\s*$", text[:600], re.MULTILINE)
            if dno:
                item.diary_number = dno.group(1)
            fill_item_from_text(item, text)
            if item.preparer:  # PDF lines wrap mid-phrase
                item.preparer = re.sub(r"\s+", " ", item.preparer).strip()[:300]

        # The whole-meeting PDF opens with the time, the place and who attended. Agendas list
        # only the invited, so it is read for minutes only.
        if meeting.pdf_url and ref.stage != "agenda":
            try:
                front_matter(pdf_text(self.fetcher.get(meeting.pdf_url).content), meeting)
            except HostBackedOff:
                raise
            except Exception as e:  # noqa: BLE001
                log.warning("meeting PDF failed %s: %s", meeting.pdf_url, e)
        return meeting


def _download(view_url: str) -> str:
    return re.sub(r"/view/(\d+)$", r"/download/\1", view_url)


# ---------------------------------------------------------------- PDF text

_PAGE_HEADER = re.compile(
    r"^\s*\S.{0,60}\s(?:Pöytäkirja|Esityslista|Protokoll|Föredragningslista)(?:\s+(?:Julkinen|Offentlig))?\s*$"
    r"|^\s*Sivu\s+\d+\s*/\s*\d+\s*$|^\s*Sida\s+\d+\s*/\s*\d+\s*$"
    r"|^\s*\d{2}\.\d{2}\.\d{4}\s*$")


def item_text(text: str, item: Item) -> str:
    """The item's own text from its PDF: the title line removed, contact lines dropped and
    'Valmistelijat puh.' read as a plain preparer heading."""
    lines = [ln.rstrip() for ln in text.replace("\xa0", " ").split("\n")]
    out: list[str] = []
    for ln in lines:
        s = ln.strip()
        if _PAGE_HEADER.match(ln) or re.match(r"^\(Yhteydenotot\b.*\)$", s) or s in ("puh.", "tfn"):
            continue
        s = re.sub(r"^(Valmistelijat?|Beredare)\s+(?:puh|tfn)\.?$", r"\1", s)
        s = re.sub(r"^Tämän kokouksen käsittely:?$", "", s)
        out.append(s)
    while out and not out[0]:
        out.pop(0)
    # 'Aluehallitus 23.3.2026 § 78' lines of the handling history are not people
    out = [ln for ln in out if not re.match(r"^\S.{0,60}\s\d{1,2}\.\d{1,2}\.\d{4}\s*§\s*\d+$", ln)]
    out = _mark_proposals(out)
    # The PDF starts with the item's title, possibly over two lines
    if out and item.title and re.sub(r"\W", "", out[0].lower()) and \
            re.sub(r"\W", "", item.title.lower()).startswith(re.sub(r"\W", "", out[0].lower())[:30]):
        out.pop(0)
    body = "\n".join(out)
    body = re.sub(r"(\w)-\n(?=[a-zåäö])", r"\1-", body)   # 'EI-' + 'ääniä' wrapped over two lines
    body = re.sub(r"\n{3,}", "\n\n", body)
    body = re.split(r"\n(?:Muutoksenhakuohjee?t?|MUUTOKSENHAKUOHJEE?T?|Oikaisuvaatimusohje)\s*\n", body)[0]
    return body.strip()


_PRESENTER = re.compile(r"^(?:\w+(?:-\w+)?\s){0,2}\w*(?:johtaja|hal+it+us|lautakunta|valtuusto|päällikkö|"
                        r"ylilääkäri|jaosto|direktör|styrelse|nämnd)$", re.IGNORECASE)


def _mark_proposals(lines: list[str]) -> list[str]:
    """M-Files prints a proposal under the presenter's title alone ('Hyvinvointialuejohtaja'),
    without an 'Esitys' heading. Put the headings back so the proposal is found."""
    from ..text import heading_kind
    out = list(lines)
    decisions = [i for i, ln in enumerate(out) if heading_kind(ln) == "decision"]
    for p in reversed(decisions):
        for k in range(p - 1, -1, -1):
            if heading_kind(out[k]):
                break
            if _PRESENTER.match(out[k]) and k + 1 < p:
                out[k:k + 1] = ["Esittelijä", out[k], "Esitys"]
                break
    return out


_GROUP_START = [(re.compile(r"^(?:Päätöksentekijät|Jäsenet|Läsnä)\b\s*"), "member"),
                (re.compile(r"^(?:Poissaolevat|Poissa)\b\s*"), "absent"),
                (re.compile(r"^(?:Muut osallistujat|Muut läsnäolijat|Asiantuntijat)\b\s*"), "other")]
_FRONT_END = re.compile(r"^(?:Käsitellyt asiat\s+§|Pöytäkirja on nähtävillä|Allekirjoitukset|Pöytäkirjan tarkastus|§\s*\d)")
_NAME = r"[A-ZÅÄÖÉ][\wåäöéü'-]+"


def front_matter(text: str, meeting: Meeting) -> Meeting:
    """Time, place and participants from the first pages of the whole-meeting PDF:

      Aika 21.4.2026 kello 18.00 - 19.08
      Paikka Lappeenrannan kaupungintalo, valtuustosali
      Nimi Tehtävä Lisätieto
      Päätöksentekijät Ikävalko Johanna Puheenjohtaja
      Backman Sara Jäsen
      Poissaolevat Helminen Anna Jäsen
      Muut osallistujat Heino Kaisa Strategia- ja
      hallintojohtaja,
    """
    lines = [ln.strip() for ln in text.replace("\xa0", " ").split("\n")]
    lines = [ln for ln in lines if ln and not _PAGE_HEADER.match(ln)]
    out: list[Participant] = []
    group = None
    for ln in lines[:600]:
        m = re.match(r"^Aika\s+\d{1,2}\.\d{1,2}\.\d{4}\s+(?:kello|klo)\s+(\d{1,2}[.:]\d{2}(?:\s*[-–]\s*\d{1,2}[.:]\d{2})?)", ln)
        if m and not meeting.time:
            meeting.time = re.sub(r"\s*[-–]\s*", " - ", m.group(1).replace(".", ":"))
            continue
        m = re.match(r"^Paikka\s+(\S.{2,150})$", ln)
        if m and not meeting.place:
            meeting.place = m.group(1).strip()
            continue
        if _FRONT_END.match(ln):
            if out:
                break
            continue
        for pat, grp in _GROUP_START:
            m = pat.match(ln)
            if m:
                group, ln = grp, ln[m.end():]
                break
        if group is None or not ln:
            continue
        p = re.match(rf"^({_NAME}\s+{_NAME})(?:\s+(.*))?$", ln)
        if p and (p.group(2) is None or p.group(2)[:1].isupper() or p.group(2)[:1].isdigit()):
            role = re.sub(r"\s*(?:Saapui|Poistui)\b.*$", "", p.group(2) or "").strip(" ,")
            out.append(Participant(name=p.group(1), role=role, group=group))
        elif out and ln[:1].islower():  # a role wrapped onto the next line
            out[-1].role = f"{out[-1].role} {ln}".strip()
    for pp in out:
        pp.role = pp.role.strip(" ,")
        if pp.group == "member" and re.search(r"edustaja|sihteeri|esittelijä|pöytäkirjanpitäjä", pp.role, re.IGNORECASE):
            pp.group = "other"
    # Officials listed as absent are not members who missed the meeting.
    meeting.participants = [pp for pp in out if not (pp.group == "absent" and role_group(pp.role) == "other"
                                                      and not re.search(r"jäsen", pp.role, re.IGNORECASE))]
    return meeting
