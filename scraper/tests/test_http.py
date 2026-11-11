"""The polite fetcher: robots.txt, gentle hosts and backing off."""

import pytest
import requests

from terveyshamsteri import http
from terveyshamsteri.http import Fetcher, HostBackedOff, RobotsDisallowed


class Resp:
    def __init__(self, status=200, text="", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}
        self.encoding = "utf-8"
        self.apparent_encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"{self.status_code}", response=self)


class Session:
    def __init__(self, pages):
        self.pages = pages
        self.headers = {}
        self.calls = []

    def get(self, url, timeout=None):
        self.calls.append(url)
        page = self.pages.get(url, Resp(404))
        return page.pop(0) if isinstance(page, list) else page


@pytest.fixture
def no_sleep(monkeypatch):
    slept = []
    monkeypatch.setattr(http.time, "sleep", lambda s: slept.append(s))
    return slept


DISALLOW = Resp(200, "User-agent: *\nDisallow: /\nCrawl-delay: 7\n")


def make(pages, **kw):
    f = Fetcher(delay=0, **kw)
    f.session = Session(pages)
    return f


def test_robots_disallow_is_respected_by_default(no_sleep):
    f = make({"https://a.fi/robots.txt": DISALLOW})
    with pytest.raises(RobotsDisallowed):
        f.get("https://a.fi/page")


def test_gentle_host_is_fetched_slowly(no_sleep):
    f = make({"https://a.fi/robots.txt": DISALLOW, "https://a.fi/x": Resp(200, "ok"),
              "https://a.fi/y": Resp(200, "ok")}, gentle_hosts=["a.fi"])
    assert f.get("https://a.fi/x").text == "ok"
    assert f.get("https://a.fi/y").text == "ok"
    assert f.ignored_robots == {"a.fi"}
    # Crawl-delay (7 s) is longer than the gentle minimum, so it wins.
    assert f._delay_for("a.fi", "https://a.fi") == 7
    assert any(s > 6 for s in no_sleep)


def test_gentle_host_stops_after_repeated_failures(no_sleep):
    f = make({"https://a.fi/robots.txt": Resp(404)}, gentle_hosts=["a.fi"], retries=1)
    for _ in range(http.GENTLE_MAX_FAILURES):
        with pytest.raises(requests.HTTPError):
            f.session.pages[f"https://a.fi/p"] = Resp(503)
            f.get("https://a.fi/p")
    with pytest.raises(HostBackedOff):
        f.get("https://a.fi/q")


def test_long_retry_after_gives_up(no_sleep):
    f = make({"https://a.fi/robots.txt": Resp(404),
              "https://a.fi/p": Resp(429, headers={"Retry-After": "3600"})})
    with pytest.raises(HostBackedOff):
        f.get("https://a.fi/p")
    assert max(no_sleep, default=0) < 3600


def test_short_retry_after_is_honoured(no_sleep):
    f = make({"https://a.fi/robots.txt": Resp(404),
              "https://a.fi/p": [Resp(503, headers={"Retry-After": "20"}), Resp(200, "ok")]})
    assert f.get("https://a.fi/p").text == "ok"
    assert 20 in no_sleep
