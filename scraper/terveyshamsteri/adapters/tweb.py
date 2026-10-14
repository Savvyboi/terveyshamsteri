"""Triplan Tweb, e.g. https://phhyky-julkaisu.tweb.fi/ktwebscr/pk_tek_tweb.htm

Not implemented yet. Tweb hosts we checked (Päijät-Häme, Lappi) disallow crawlers in
robots.txt, so this adapter only checks whether that is still the case and reports it.
The region needs to grant access or provide a bulk export before we parse it."""

from __future__ import annotations

from ..http import RobotsDisallowed
from ..models import Body, Meeting, MeetingRef
from .base import Adapter


class TwebAdapter(Adapter):
    platform = "tweb"

    def list_bodies(self) -> list[Body]:
        entry = self.epoch.get("entry_url", f"{self.base}/ktwebscr/pk_tek_tweb.htm")
        if not self.fetcher.allowed(entry):
            raise RobotsDisallowed(entry)
        raise NotImplementedError("Tweb adapter is not implemented yet; robots.txt now allows "
                                  f"{entry}, so it can be built.")

    def list_meetings(self, body: Body) -> list[MeetingRef]:
        raise NotImplementedError

    def fetch_meeting(self, ref: MeetingRef) -> Meeting:
        raise NotImplementedError
