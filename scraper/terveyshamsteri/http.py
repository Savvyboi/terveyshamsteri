"""Polite HTTP client: identifies itself, rate-limits per host and backs off on errors.

robots.txt is honoured by default. A few counties publish their minutes on hosts whose
robots.txt turns all crawlers away, although the minutes are public documents that the
counties must publish (Hyvinvointialuelaki 145 §, Kuntalaki 140 §). For those hosts a region
config can list `gentle_hosts`: we still read robots.txt and keep to its Crawl-delay, but fetch
anyway, much more slowly than elsewhere, one request at a time, and stop for the week as soon
as the host shows any sign of strain."""

from __future__ import annotations

import logging
import time
import urllib.robotparser
from email.utils import parsedate_to_datetime
from urllib.parse import urlsplit

import requests

log = logging.getLogger(__name__)

PROJECT_URL = "https://github.com/Savvyboi/terveyshamsteri"
USER_AGENT = (
    "terveyshamsteri/0.2 (civic archive of wellbeing services county decisions; "
    f"+{PROJECT_URL})"
)

# Hosts whose robots.txt disallows us but that we fetch anyway (see module docstring).
GENTLE_DELAY = 5.0          # seconds between requests to such a host, at least
GENTLE_MAX_FAILURES = 3     # consecutive failures before we leave the host alone for this run
MAX_RETRY_AFTER = 300       # longest Retry-After we are willing to wait


class RobotsDisallowed(Exception):
    """The host's robots.txt does not allow us to fetch this URL."""


class HostBackedOff(Exception):
    """The host kept failing or asked us to slow down too much; we stopped for this run."""


class Fetcher:
    def __init__(self, delay: float = 1.0, timeout: float | tuple[float, float] = 30.0, retries: int = 3,
                 respect_robots: bool = True, gentle_hosts: list[str] | None = None):
        self.delay = delay
        self.timeout = timeout
        self.retries = retries
        self.respect_robots = respect_robots
        self.gentle_hosts = {h.lower() for h in (gentle_hosts or [])}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT, "Accept-Language": "fi,sv;q=0.8,en;q=0.5"})
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self._failures: dict[str, int] = {}
        self._gave_up: set[str] = set()
        self.requests_made = 0
        self.ignored_robots: set[str] = set()   # hosts fetched despite robots.txt, for the status file

    # ------------------------------------------------------------------ pacing
    def _gentle(self, host: str) -> bool:
        return host.lower() in self.gentle_hosts

    def _delay_for(self, host: str, origin: str) -> float:
        d = self.delay
        rp = self._robots.get(origin)
        if rp is not None:
            crawl_delay = rp.crawl_delay(USER_AGENT) or rp.crawl_delay("*")
            if crawl_delay:
                d = max(d, float(crawl_delay))
        if self._gentle(host):
            d = max(d, GENTLE_DELAY)
        return d

    def _wait(self, host: str, delay: float | None = None) -> None:
        delay = self.delay if delay is None else delay
        last = self._last.get(host)
        if last is not None:
            gap = time.monotonic() - last
            if gap < delay:
                time.sleep(delay - gap)
        self._last[host] = time.monotonic()

    # ------------------------------------------------------------------ robots.txt
    def _robots_for(self, origin: str, host: str) -> urllib.robotparser.RobotFileParser | None:
        if origin not in self._robots:
            rp: urllib.robotparser.RobotFileParser | None = urllib.robotparser.RobotFileParser()
            try:
                self._wait(host, max(self.delay, GENTLE_DELAY) if self._gentle(host) else None)
                r = self.session.get(origin + "/robots.txt", timeout=self.timeout)
                if r.status_code >= 400:
                    rp = None  # no robots.txt: everything allowed
                else:
                    rp.parse(r.text.splitlines())
            except requests.RequestException as e:
                log.warning("robots.txt fetch failed for %s: %s", origin, e)
                rp = None
            self._robots[origin] = rp
        return self._robots[origin]

    def allowed(self, url: str) -> bool:
        """Whether robots.txt lets us fetch the URL, or the host is one we fetch gently anyway."""
        if not self.respect_robots:
            return True
        parts = urlsplit(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        rp = self._robots_for(origin, parts.netloc)
        ok = True if rp is None else rp.can_fetch(USER_AGENT, url)
        if not ok and self._gentle(parts.netloc):
            if parts.netloc not in self.ignored_robots:
                log.info("robots.txt disallows %s; fetching gently (public minutes)", parts.netloc)
            self.ignored_robots.add(parts.netloc)
            return True
        return ok

    # ------------------------------------------------------------------ fetching
    def get(self, url: str) -> requests.Response:
        parts = urlsplit(url)
        host = parts.netloc
        if host in self._gave_up:
            raise HostBackedOff(f"{host}: stopped for this run after repeated errors")
        if not self.allowed(url):
            raise RobotsDisallowed(url)
        delay = self._delay_for(host, f"{parts.scheme}://{host}")
        gentle = self._gentle(host)
        err: Exception | None = None
        for attempt in range(self.retries):
            self._wait(host, delay)
            try:
                self.requests_made += 1
                r = self.session.get(url, timeout=self.timeout)
                if r.status_code in (429, 500, 502, 503, 504):
                    raise requests.HTTPError(f"{r.status_code} for {url}", response=r)
                r.raise_for_status()
                if not r.encoding or r.encoding.lower() == "iso-8859-1":
                    # Several platforms omit or mislabel the charset.
                    r.encoding = r.apparent_encoding or "utf-8"
                self._failures[host] = 0
                return r
            except requests.RequestException as e:
                err = e
                resp = getattr(e, "response", None)
                status = getattr(resp, "status_code", None)
                if status is not None and 400 <= status < 500 and status != 429:
                    break
                backoff = float(2 ** (attempt + 1)) * (3 if gentle else 1)
                retry_after = _retry_after(resp)
                if retry_after is not None:
                    if retry_after > MAX_RETRY_AFTER:
                        self._gave_up.add(host)
                        raise HostBackedOff(f"{host} asked us to wait {retry_after:.0f}s") from e
                    backoff = max(backoff, retry_after)
                    # Keep to the slower pace for the rest of the run.
                    delay = max(delay, retry_after)
                if gentle and status in (429, 503):
                    delay *= 2
                log.warning("GET %s failed (%s), retrying in %ss", url, e, backoff)
                time.sleep(backoff)
        assert err is not None
        self._failures[host] = self._failures.get(host, 0) + 1
        if gentle and self._failures[host] >= GENTLE_MAX_FAILURES:
            log.warning("%s failed %d times in a row; leaving it alone for this run", host, self._failures[host])
            self._gave_up.add(host)
        raise err


def _retry_after(resp: requests.Response | None) -> float | None:
    value = resp.headers.get("Retry-After") if resp is not None else None
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        try:
            return max(0.0, parsedate_to_datetime(value).timestamp() - time.time())
        except (TypeError, ValueError):
            return None
