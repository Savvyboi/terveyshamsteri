"""Normalized records, loosely following the 6Aika Open Decision API shape:
region -> body -> meeting -> agenda item."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

PARSER_VERSION = "0.1.0"


@dataclass
class Attachment:
    title: str
    url: str


@dataclass
class Section:
    heading: str
    text: str


@dataclass
class Vote:
    """Roll-call result extracted from minutes prose. Always provisional until reviewed."""
    counts: dict[str, int]          # {"jaa": 42, "ei": 16, "tyhja": 1, "poissa": 0}
    context: str                    # the sentence(s) the counts came from
    provisional: bool = True


@dataclass
class Participant:
    name: str
    role: str = ""
    group: str = "member"           # member | other


@dataclass
class Item:
    number: str                     # pykälä, e.g. "278"
    title: str
    source_url: str
    pdf_url: str | None = None
    diary_number: str | None = None
    preparer: str | None = None
    presenter: str | None = None
    proposal: str | None = None
    decision: str | None = None
    discussion: str | None = None
    sections: list[Section] = field(default_factory=list)
    attachments: list[Attachment] = field(default_factory=list)
    votes: list[Vote] = field(default_factory=list)
    redacted: bool = False          # item is listed but its text is not published


@dataclass
class Meeting:
    id: str                         # "{body_id}/{yyyy-mm-dd}" (+ "-2" etc. on clashes)
    region: str
    body_id: str
    body_name: str
    date: str                       # ISO date
    stage: str                      # agenda | minutes | minutes-unverified
    source_url: str
    pdf_url: str | None = None
    time: str | None = None         # "16:00 - 19:00"
    place: str | None = None
    language: str = "fi"
    items: list[Item] = field(default_factory=list)
    participants: list[Participant] = field(default_factory=list)
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Body:
    id: str
    name: str
    url: str
    type: str                       # council | board | committee | section | advisory | other


@dataclass
class MeetingRef:
    """A meeting as seen on a listing page, before fetching it."""
    body: Body
    date: str
    url: str
    stage: str
