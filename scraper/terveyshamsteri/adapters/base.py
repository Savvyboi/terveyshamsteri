"""Common adapter interface. One adapter per publishing platform; a region is an adapter
plus a config file (base URL, source epochs, bodies to skip, language)."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from typing import Any

from bs4 import Tag

from ..http import Fetcher
from ..models import Body, Item, Meeting, MeetingRef
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
    sections = split_sections(text)
    item.sections = sections
    item.diary_number = item.diary_number or diary_number(text)
    item.proposal = last_of(sections, "proposal")
    item.decision = last_of(sections, "decision")
    item.discussion = last_of(sections, "discussion")
    for s in sections:
        kind = heading_kind(s.heading)
        if kind == "preparer" and not item.preparer:
            item.preparer = first_line(s.text)
        elif kind == "presenter" and not item.presenter:
            item.presenter = first_line(s.text)
    # "Valmistelija: Etunimi Sukunimi, talousjohtaja" written inline
    if not item.preparer:
        m = re.search(r"(?:Valmistelija|Lisätiedot|Beredare)t?\s*:?\s*([^\n]{3,120})", text)
        if m:
            item.preparer = m.group(1).strip()
    if not item.presenter:
        m = re.search(r"(?:Esittelijä|Föredragande)\s*:?\s*([^\n]{3,120})", text)
        if m:
            item.presenter = m.group(1).strip()
    item.votes = extract_votes("\n\n".join(filter(None, [item.discussion, item.decision])))
    if not item.votes and item.discussion is None:
        item.votes = extract_votes(text)
    return item


def first_line(s: str) -> str:
    return next((ln.strip() for ln in s.split("\n") if ln.strip()), "")[:200]


def content_after(h1: Tag) -> str:
    """Text of the page from the h1 onwards, without the h1 itself and the footer."""
    container = h1.parent
    while container is not None and container.parent is not None and \
            len(container.get_text(strip=True)) - len(h1.get_text(strip=True)) < 200:
        container = container.parent
    full = html_text(container)
    head = h1.get_text(" ", strip=True)
    idx = full.find(head)
    text = full[idx + len(head):] if idx >= 0 else full
    text = re.sub(r"\n©\s*$", "", text.strip())
    # Drop the trailing navigation and PDF links block
    text = re.split(r"\n(?:Edellinen|Seuraava|Föregående|Nästa|Takaisin|Tillbaka)"
                    r"(?: kokousasia| ärende| asia)?\s*(?:\n|$)", text)[0]
    return text.strip()


_MEMBER_ROLE = re.compile(r"jäsen|valtuutettu|puheenjohtaja|ledamot|ordförande|ersättare", re.IGNORECASE)
_STAFF_ROLE = re.compile(r"pöytäkirjanpitäjä|sihteeri|esittelijä|sekreterare|protokollförare|"
                         r"föredragande|(?<!puheen)johtaja|direktör|asiantuntija|edustaja", re.IGNORECASE)


def role_group(role: str) -> str:
    """'member' for elected members and deputies, 'other' for officials and guests."""
    return "member" if _MEMBER_ROLE.search(role) and not _STAFF_ROLE.search(role) else "other"
