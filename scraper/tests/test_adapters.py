import json
from pathlib import Path

import pytest
import requests

from terveyshamsteri.run import scrape_region
from terveyshamsteri.text import extract_votes, parse_fi_date, scrub, slugify

FIX = Path(__file__).parent / "fixtures"


class FakeResponse:
    def __init__(self, text):
        self.text = text


class FakeFetcher:
    """Serves fixture files by URL instead of touching the network."""

    def __init__(self, routes):
        self.routes = routes
        self.requests_made = 0

    def allowed(self, url):
        return True

    def get(self, url):
        self.requests_made += 1
        for key, path in self.routes.items():
            if url.endswith(key):
                return FakeResponse((FIX / path).read_text(encoding="utf-8"))
        raise requests.HTTPError(f"404 {url}")


@pytest.fixture
def patch_fetcher(monkeypatch):
    def apply(routes):
        monkeypatch.setattr("terveyshamsteri.run.Fetcher", lambda **kw: FakeFetcher(routes))
    return apply


DYN = "https://esim-d10julk.oncloudos.com"
DYNASTY_REGION = {"id": "esimerkki", "since": "2025-06-01",
                  "epochs": [{"platform": "dynasty", "base_url": DYN}]}
DYNASTY_ROUTES = {
    "page=meeting_handlers&id=": "dynasty/handlers.html",
    "page=meetings&id=7": "dynasty/meetings7.html",
    "page=meeting&id=2026365": "dynasty/meeting2026365.html",
    "page=meeting&id=2026390": "dynasty/meeting2026390.html",
    "page=meetingitem&id=2026390-1": "dynasty/item2026365-5.html",
    "page=meetingitem&id=2026365-4": "dynasty/item2026365-4.html",
    "page=meetingitem&id=2026365-5": "dynasty/item2026365-5.html",
}


def test_dynasty_region(tmp_path, patch_fetcher):
    patch_fetcher(DYNASTY_ROUTES)
    status = scrape_region(DYNASTY_REGION, tmp_path)
    assert status["result"] == "ok", status
    assert status["fetched"] == 2          # 2024 meeting is before `since`

    bodies = json.loads((tmp_path / "esimerkki/bodies.json").read_text())
    assert [b["name"] for b in bodies] == ["Aluevaltuusto"]   # yksilöasiainjaosto skipped
    assert bodies[0]["type"] == "council"

    m = json.loads((tmp_path / "esimerkki/meetings/aluevaltuusto/2026-09-29.json").read_text())
    assert m["time"] == "16:00 - 19:00"
    assert m["stage"] == "minutes"
    assert m["pdf_url"] == f"{DYN}/kokous/2026365.PDF"
    assert [i["number"] for i in m["items"]] == ["50", "51"]
    assert m["participants"][0] == {"name": "Meikäläinen Matti", "role": "puheenjohtaja", "group": "member"}
    assert m["participants"][3]["group"] == "other"
    assert m["provenance"]["source_url"].endswith("page=meeting&id=2026365")

    item = m["items"][0]
    assert item["source_url"] == f"{DYN}/cgi/DREQUEST.PHP?page=meetingitem&id=2026365-4"
    assert item["pdf_url"] == f"{DYN}/kokous/2026365-4.PDF"
    assert item["diary_number"] == "ESIM/1234/02.02.00/2026"
    assert [a["url"] for a in item["attachments"]] == [f"{DYN}/kokous/2026365-4-124611.PDF"]
    assert item["proposal"] == "Aluevaltuusto merkitsee puolivuosikatsauksen tiedoksi."
    assert item["decision"].startswith("Aluevaltuusto merkitsi")
    assert item["votes"][0]["counts"] == {"jaa": 42, "ei": 16, "tyhja": 1, "poissa": 0}
    full = json.dumps(item, ensure_ascii=False)
    assert "teija.talous@" not in full and "040 123 4567" not in full and "010190-123A" not in full
    assert "Teija Talous" in item["preparer"]
    assert "Seuraava" not in full
    assert [s["heading"] for s in item["sections"]][:2] == ["", "Liitteet"]

    agenda_like = m["items"][1]          # proposal only, empty decision, navigation block
    assert agenda_like["decision"] is None
    assert agenda_like["proposal"] == "Aloite lähetetään aluehallitukselle valmisteltavaksi."
    assert "DATAEND" not in json.dumps(agenda_like) and "Navigointi" not in json.dumps(agenda_like)
    # Real layout: navigation/attachment tables, then a Word export in div.htmCnt
    assert agenda_like["diary_number"] == "878/00.01.01.01/2026"
    assert agenda_like["preparer"] == "hallintojohtaja Hanna Hallinto"
    assert [s["heading"] for s in agenda_like["sections"]] == [
        "Valmistelija", "Selostus asiasta", "Päätösehdotus", "Päätös"]
    assert agenda_like["sections"][1]["text"].endswith("Vastaus tuodaan valtuustolle.")
    assert [(a["title"], a["url"]) for a in agenda_like["attachments"]] == [
        ("Valtuustoaloite palveluverkosta", f"{DYN}/kokous/2026365-5-130001.PDF")]
    assert "064 7666" not in json.dumps(agenda_like) and "Muutoksenhakuohje" not in json.dumps(agenda_like)


def test_dynasty_incremental_rerun_is_stable(tmp_path, patch_fetcher):
    patch_fetcher(DYNASTY_ROUTES)
    scrape_region(DYNASTY_REGION, tmp_path)
    before = (tmp_path / "esimerkki/meetings/aluevaltuusto/2026-09-29.json").read_text()
    status = scrape_region(DYNASTY_REGION, tmp_path)
    after = (tmp_path / "esimerkki/meetings/aluevaltuusto/2026-09-29.json").read_text()
    assert before == after
    assert status["changed"] == 0


CNC = "https://esim.cloudnc.fi"
CLOUDNC_REGION = {"id": "esim2", "since": "2025-06-01",
                  "epochs": [{"platform": "cloudnc", "base_url": CNC}]}


def test_cloudnc_region(tmp_path, patch_fetcher):
    patch_fetcher({
        "/fi-FI/Toimielimet": "cloudnc/bodies.html",
        "/fi-FI/Toimielimet/Aluehallitus": "cloudnc/aluehallitus.html",
        "/fi-FI/Toimielimet/Lasten_nuorten_perheiden_ja_tyoumlikaumlisten_valiokunta": "cloudnc/aluehallitus.html",
        "/Kokous_5102026": "cloudnc/kokous.html",
        "/fi-FI/content/46498/14970": "cloudnc/item.html",
        "/fi-FI/content/46499/14970": "cloudnc/item_real.html",
    })
    status = scrape_region(CLOUDNC_REGION, tmp_path)
    assert status["result"] == "ok", status
    bodies = {b["name"] for b in json.loads((tmp_path / "esim2/bodies.json").read_text())}
    assert "Yksilöasioiden jaosto" not in bodies and "Aluehallitus" in bodies

    m = json.loads((tmp_path / "esim2/meetings/aluehallitus/2026-10-05.json").read_text())
    assert m["pdf_url"].endswith("/77219")
    assert m["time"] == "13:00 - 15:30"
    assert m["place"] == "Hallintokeskus, kokoushuone Näsi"
    names = {(p["name"], p["group"]) for p in m["participants"]}
    assert ("Hanna Esimerkki", "member") in names
    assert ("Pekka Poissaoleva", "absent") in names
    assert ("Marja Johtaja", "other") in names

    item = m["items"][0]
    assert (item["number"], item["title"]) == ("278", "Kuukausiraportti")
    assert item["proposal"] == "Aluehallitus päättää merkitä raportin tiedoksi."
    assert item["decision"] == "Päätösehdotus hyväksyttiin."
    assert item["presenter"].startswith("Marja Johtaja")
    assert item["attachments"][0]["title"].startswith("Kuukausiraportti 8_2026.pdf")
    assert "pasi.talous@" not in json.dumps(item, ensure_ascii=False)
    assert ("Hanna Esimerkki", "Puheenjohtaja") in {(p["name"], p["role"]) for p in m["participants"]}

    real = m["items"][1]
    assert [a["url"] for a in real["attachments"]] == [
        "https://esim.cloudnc.fi/download/noname/{508c25fa-c1f5-4ffd-acbb-15cfb749ee75}/77295"]
    assert real["attachments"][0]["title"].startswith("Tavoitteet 2027.pdf")
    assert "Liitteet" not in [x["heading"] for x in real["sections"]]
    assert real["source_url"] == f"{CNC}/fi-FI/content/46499/14970"
    assert real["diary_number"] == "16442/2026"
    assert real["sections"][0]["heading"] == "Valmistelija"
    assert real["preparer"] == "Timo Esimerkki, KONSERNIOHJAUKSEN PÄÄLLIKKÖ"
    assert real["presenter"] == "Mika Malli, KONSERNIJOHTAJA"
    assert real["proposal"] == "Jaosto päättää esittää aluehallitukselle tavoitteet."
    assert real["votes"][0]["counts"] == {"jaa": 6, "ei": 3}


@pytest.mark.parametrize("text,expected", [
    ("Äänestyksessä annettiin 42 JAA-ääntä, 16 EI-ääntä ja 1 TYHJÄ-ääni.", {"jaa": 42, "ei": 16, "tyhja": 1}),
    ("Äänestys: JAA 30, EI 20, TYHJÄ 2, POISSA 7", {"jaa": 30, "ei": 20, "tyhja": 2, "poissa": 7}),
    ("I omröstningen avgavs 40 JA-röster och 19 NEJ-röster.", {"jaa": 40, "ei": 19}),
    ("Ehdotus ei saanut kannatusta. Ei äänestystä.", None),
])
def test_votes(text, expected):
    votes = extract_votes(text)
    if expected is None:
        assert votes == []
    else:
        assert votes[0].counts == expected


def test_helpers():
    assert slugify("Lasten, nuorten ja perheiden lautakunta") == "lasten-nuorten-ja-perheiden-lautakunta"
    assert slugify("Yksilöasiainjaosto") == "yksiloasiainjaosto"
    assert parse_fi_date("Kokous 5.10.2026 Pöytäkirja") == "2026-10-05"
    assert scrub("soita 040 123 4567 tai maili@x.fi") == "soita tai"


def test_region_configs_load():
    from terveyshamsteri.adapters import ADAPTERS
    from terveyshamsteri.config import load_regions
    regions = load_regions(Path(__file__).resolve().parents[2] / "regions")
    assert len(regions) == 21
    unimplemented = {"mfiles"}   # documented sources we have no adapter for (robots.txt forbids)
    for r in regions.values():
        assert r["name"]["fi"] and r["name"]["sv"]
        for e in r.get("epochs", []):
            assert e["platform"] in ADAPTERS or e["platform"] in unimplemented
            if e["platform"] not in ADAPTERS:
                assert not r["enabled"]


def test_dynasty_newer_layout():
    """Dynasty 10.5.0.2601+ puts the item in div.data-part-block-htm with plain paragraph labels."""
    from terveyshamsteri.adapters.base import fill_item_from_text
    from terveyshamsteri.adapters.dynasty import _item_text
    from terveyshamsteri.models import Item
    from terveyshamsteri.text import soup
    html = (Path(__file__).parent / "fixtures/dynasty/item_new_layout.html").read_text(encoding="utf-8")
    text, _ = _item_text(soup(html))
    item = fill_item_from_text(Item(number="64", title="Kokouksen päättäminen", source_url="u"), text)
    assert item.proposal == "Puheenjohtaja päättää kokouksen."
    assert item.preparer == "hallintosihteeri Maija Malli"
    assert "Navigointi" not in text and "Laadun raportti" not in text and "Confidential" not in text


def test_split_sections_label_variants():
    from terveyshamsteri.text import split_sections
    text = ("Selostus\nTaustaa.\n\nToimialajohtajan\n\npäätösesitys\nValiokunta merkitsee tiedoksi.\n\n"
            "Päätös: Hyväksyttiin.")
    secs = split_sections(text)
    assert [(s.heading, s.text) for s in secs] == [
        ("Selostus", "Taustaa."), ("Toimialajohtajan päätösesitys", "Valiokunta merkitsee tiedoksi."),
        ("Päätös", "Hyväksyttiin.")]


_TWO_HANDLINGS = ("Päätösehdotus\nAluehallitus päättää hyväksyä.\n\nKäsittely\nÄänestyksessä JAA 9 ääntä, EI 4 ääntä.\n\n"
                  "Päätös\nAluehallitus hyväksyi päätösehdotuksen äänin 9-4.\n\n"
                  "Päätösehdotus\nLautakunta päättää esittää.\n\nPäätös\nLautakunta hyväksyi yksimielisesti.")


def test_newest_first_handlings():
    """Some sites print the current handling first, the earlier bodies' handlings after it."""
    from terveyshamsteri.adapters.base import fill_item_from_text
    from terveyshamsteri.models import Item
    item = fill_item_from_text(Item(number="1", title="t", source_url="u"), _TWO_HANDLINGS, newest_first=True)
    assert item.decision.startswith("Aluehallitus hyväksyi")
    assert [v.counts for v in item.votes] == [{"jaa": 9, "ei": 4}]
    item = fill_item_from_text(Item(number="1", title="t", source_url="u"), _TWO_HANDLINGS)
    assert item.decision == "Lautakunta hyväksyi yksimielisesti."


def test_earlier_handlings_votes_are_not_read():
    """Without a discussion section the current handling is read, but not the earlier ones."""
    from terveyshamsteri.adapters.base import fill_item_from_text
    from terveyshamsteri.models import Item
    text = ("Ehdotus\nLautakunta esittää.\n\nPäätös\nÄänestyksessä annettiin 11 ääntä.\nJaa: 8 ääntä\nEi: 3 ääntä\n\n"
            "Ehdotus\nAluehallitus esittää.\n\nPäätös\nHyväksyttiin yksimielisesti.")
    item = fill_item_from_text(Item(number="1", title="t", source_url="u"), text)
    assert item.votes == []
    text = ("Ehdotus\nLautakunta esittää.\n\nPäätös\nHyväksyttiin.\n\n"
            "Ehdotus\nAluevaltuusto hyväksyy.\n\nAsian kokouskäsittely:\nÄänestyksessä JAA 50 ääntä, EI 12 ääntä.\n\n"
            "Päätös\nHyväksyttiin äänestyksen jälkeen.")
    item = fill_item_from_text(Item(number="1", title="t", source_url="u"), text)
    assert [v.counts for v in item.votes] == [{"jaa": 50, "ei": 12}]


def test_reextract_uses_region_order(tmp_path):
    import json
    from dataclasses import asdict
    from terveyshamsteri.adapters.base import fill_item_from_text
    from terveyshamsteri.models import Item
    from terveyshamsteri.run import reextract_votes
    item = asdict(fill_item_from_text(Item(number="1", title="t", source_url="u"), _TWO_HANDLINGS))
    meeting = {"region": "r", "date": "2026-01-01", "items": [item], "provenance": {"platform": "dynasty"}}
    path = tmp_path / "r/meetings/b/2026-01-01.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(meeting))
    regions = {"r": {"epochs": [{"platform": "dynasty", "base_url": "x", "newest_first": True}]}}
    assert reextract_votes(tmp_path, regions)["changed"] == 1
    it = json.loads(path.read_text())["items"][0]
    assert it["decision"].startswith("Aluehallitus") and it["votes"][0]["counts"] == {"jaa": 9, "ei": 4}
    assert reextract_votes(tmp_path, regions)["changed"] == 0
