"""Common adapter interface. One adapter per publishing platform; a region is an adapter
plus a config file (base URL, source epochs, bodies to skip, language)."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from bs4 import Tag

from ..http import Fetcher
from ..models import Body, Item, Meeting, MeetingRef, Section
from ..text import diary_number, html_text, extract_votes, heading_kind, last_of, scrub, split_sections


class Adapter(ABC):
    platform: str = ""

    def __init__(self, region: dict[str, Any], epoch: dict[str, Any], fetcher: Fetcher):
        self.region = region
        self.epoch = epoch
        self.base = epoch["base_url"].rstrip("/")
        self.fetcher = fetcher
        self.language = epoch.get("language", region.get("language", "fi"))

    @abstractmethod
    def list_bodies(self) -> list[Body]: ...

    @abstractmethod
    def list_meetings(self, body: Body) -> list[MeetingRef]: ...

    @abstractmethod
    def fetch_meeting(self, ref: MeetingRef) -> Meeting:
        """Fetch a meeting page and all of its agenda items."""


def fill_item_from_text(item: Item, text: str) -> Item:
    """Populate the structured fields of an item from its plain text."""
    text = scrub(text) or ""
    sections = _move_proposal_out_of_presenter(split_sections(text))
    item.sections = sections
    item.diary_number = item.diary_number or diary_number(text)
    item.proposal = last_of(sections, "proposal")
    item.decision = last_of(sections, "decision")
    item.discussion = last_of(sections, "discussion")
    for s in sections:
        kind = heading_kind(s.heading)
        if kind == "preparer" and not item.preparer:
            item.preparer = "; ".join(ln.strip().rstrip(",").strip() for ln in s.text.split("\n") if ln.strip())[:300]
        elif kind == "presenter" and not item.presenter:
            item.presenter = first_line(s.text).rstrip(",").strip()
    # "Valmistelija: Etunimi Sukunimi, talousjohtaja" written inline
    if not item.preparer:
        m = re.search(r"\b(?:Valmistelija|Lisätiedot|Beredare)t?(?:\s*:\s*|\s+(?=[A-ZÅÄÖ]))([^\n]{3,120})", text)
        if m:
            item.preparer = m.group(1).strip()
    if not item.presenter:
        m = re.search(r"\b(?:Esittelijä|Föredragande)(?:\s*:\s*|\s+(?=[A-ZÅÄÖ]))([^\n]{3,120})", text)
        if m:
            item.presenter = m.group(1).strip()
    item.votes = extract_votes("\n\n".join(filter(None, [item.discussion, item.decision])))
    if not item.votes and item.discussion is None:
        item.votes = extract_votes(text)
    return item


def _move_proposal_out_of_presenter(sections: list[Section]) -> list[Section]:
    """CloudNC prints 'Ehdotus' as an empty heading followed by 'Esittelijä: Name, TITLE'
    and only then the proposal text. Move that text back under the proposal heading."""
    out = list(sections)
    for i in range(len(out) - 1):
        a, b = out[i], out[i + 1]
        if heading_kind(a.heading) == "proposal" and not a.text and heading_kind(b.heading) == "presenter":
            parts = re.split(r"\n\s*\n", b.text, maxsplit=1)
            if len(parts) == 2 and parts[1].strip():
                out[i] = Section(a.heading, parts[1].strip())
                out[i + 1] = Section(b.heading, parts[0].strip())
    return out


def first_line(s: str) -> str:
    return next((ln.strip() for ln in s.split("\n") if ln.strip()), "")[:200]


def cut_navigation(text: str) -> str:
    """Dynasty ends item pages with a 'Navigointi' block and a DATAEND marker."""
    ends = list(re.finditer(r"(?:^|\n)(?:Navigointi|DATAEND)\s*(?:\n|$)", text))
    if ends:
        text = text[:ends[0].start()]
    # Previous/next links without a heading
    return re.split(r"\n(?:Edellinen|Seuraava|Föregående|Nästa|Takaisin|Tillbaka)"
                    r"(?: kokousasia| ärende| asia)?\s*(?:\|[^\n]*)?(?:\n|$)", text)[0]


def content_after(h1: Tag) -> str:
    """Text of the page from the h1 onwards, without the h1 itself and the footer."""
    container = h1.parent
    while container is not None and container.parent is not None and \
            len(container.get_text(strip=True)) - len(h1.get_text(strip=True)) < 200:
        container = container.parent
    full = html_text(container)
    head = h1.get_text(" ", strip=True)
    # The h1 may contain line breaks or nested tags, so match it whitespace-insensitively.
    m = re.search(r"\s+".join(map(re.escape, head.split())), full) if head else None
    text = full[m.end():] if m else full
    text = re.sub(r"\n©\s*$", "", text.strip())
    text = cut_navigation(text)
    return text.strip()


_MEMBER_ROLE = re.compile(r"jäsen|valtuutettu|puheenjohtaja|ledamot|ordförande|ersättare", re.IGNORECASE)
_STAFF_ROLE = re.compile(r"pöytäkirjanpitäjä|sihteeri|esittelijä|sekreterare|protokollförare|"
                         r"föredragande|(?<!puheen)johtaja|direktör|asiantuntija|edustaja", re.IGNORECASE)


def role_group(role: str) -> str:
    """'member' for elected members and deputies, 'other' for officials and guests."""
    return "member" if _MEMBER_ROLE.search(role) and not _STAFF_ROLE.search(role) else "other"
