"""Polite HTTP client: identifies itself, honours robots.txt, rate-limits per host."""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

USER_AGENT = (
    "terveyshamsteri/0.1 (civic archive of wellbeing services county decisions; "
    "+https://github.com/Savvyboi/terveyshamsteri)"
)


class RobotsDisallowed(Exception):
    """The host's robots.txt does not allow us to fetch this URL."""


class Fetcher:
    def __init__(self, delay: float = 1.0, timeout: float = 30.0, retries: int = 3,
                 respect_robots: bool = True):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.respect_robots = respect_robots
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fi,sv;q=0.8,en;q=0.5"})
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.requests_made = 0

    def _wait(self, host: str) -> None:
        last = self._last.get(host)
        if last is not None:
            gap = time.monotonic() - last
            if gap < self.delay:
                time.sleep(self.delay - gap)
        self._last[host] = time.monotonic()

    def allowed(self, url: str) -> bool:
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                self._wait(parts.netloc)
                r = self.session.get(origin + "/robots.txt", timeout=self.timeout)
                if r.status_code >= 400:
                    rp = None  # no robots.txt: everything allowed
                else:
                    rp.parse(r.text.splitlines())
            except requests.RequestException as e:
                log.warning("robots.txt fetch failed for %s: %s", origin, e)
                rp = None
            self._robots[origin] = rp
        rp = self._robots[origin]
        return True if rp is None else rp.can_fetch(USER_AGENT, url)

    def get(self, url: str) -> requests.Response:
        if not self.allowed(url):
            raise RobotsDisallowed(url)
        host = urlsplit(url).netloc
        err: Exception | None = None
        for attempt in range(self.retries):
            self._wait(host)
            try:
                self.requests_made += 1
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"{r.status_code} for {url}", response=r)
                r.raise_for_status()
                if not r.encoding or r.encoding.lower() == "iso-8859-1":
                    # Several platforms omit or mislabel the charset.
                    r.encoding = r.apparent_encoding or "utf-8"
                return r
            except requests.RequestException as e:
                err = e
                status = getattr(getattr(e, "response", None), "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    break
                backoff = 2 ** (attempt + 1)
                log.warning("GET %s failed (%s), retrying in %ss", url, e, backoff)
                time.sleep(backoff)
        assert err is not None
        raise err
