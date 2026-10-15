import json
from pathlib import Path

import requests

from terveyshamsteri.adapters import sttinfo
from terveyshamsteri.adapters.sttinfo import parse_minutes, parse_release_title
from terveyshamsteri.models import Meeting
from terveyshamsteri.run import scrape_region

FIX = Path(__file__).parent / "fixtures" / "sttinfo"
MINUTES = (FIX / "aluehallitus_2026-10-12.txt").read_text(encoding="utf-8")


def test_release_titles():
    assert parse_release_title("Varhan aluehallituksen 12.10.2026 kokouksen tarkastamaton pöytäkirja") == \
        ("Aluehallitus", "2026-10-12", "minutes-unverified")
    assert parse_release_title("Varhan aluevaltuuston 10.6.2026 kokouksen pöytäkirja") == \
        ("Aluevaltuusto", "2026-06-10", "minutes")
    # Agenda releases only summarise the agenda; news about decisions is not minutes.
    assert parse_release_title("Varhan 30.9.2026 aluevaltuuston esityslista") is None
    assert parse_release_title("Aluehallitus päätti Varhan tulevasta palveluverkosta") is None


def _meeting():
    return Meeting(id="", region="varsinais-suomi", body_id="aluehallitus", body_name="Aluehallitus",
                   date="2026-10-12", stage="minutes-unverified", source_url="https://www.sttinfo.fi/tiedote/1",
                   pdf_url="https://www.sttinfo.fi/files/1")


def test_minutes_pdf_text():
    m = parse_minutes(MINUTES, _meeting())
    assert m.time == "9:30 - 12:28"
    assert m.place == "Tyks, T-sairaala, A-osa, 6. krs, hallituksen kokoushuone"
    members = [p for p in m.participants if p.group == "member"]
    assert len(members) == 16 and members[0].name == "Niina Alho" and members[0].role == "pj"
    assert any(p.name == "Jari-Pekka Tuominen" and p.group == "other" for p in m.participants)

    assert [it.number for it in m.items] == ["273", "274", "275", "276", "283", "284"]
    i276 = m.items[3]
    assert i276.title == "Varsinais-Suomen hyvinvointialueen palveluverkkovisio 2027–2037"
    assert i276.diary_number == "VARHA/18405/00.01.02.00/2025"
    assert i276.preparer.startswith("strategia- ja integraatiojohtaja Antti Parpo")
    assert "johtava asiantuntija Leena Setälä" in i276.preparer
    assert i276.proposal.startswith("Aluehallitus päättää hyväksyä")
    assert i276.source_url == "https://www.sttinfo.fi/tiedote/1#276"

    # Running page headers must not leak into item text.
    for it in m.items:
        for s in it.sections:
            assert "19/2026" not in s.text and "Pöytäkirja\n" not in s.text

    i283 = m.items[4]
    assert i283.decision == "Päätösehdotus hyväksyttiin kokouksessa tehdyllä muutoksella."
    assert i283.discussion.startswith("Merkittiin, että Niina Alho ehdotti")
    assert m.items[5].title == "Vastaus valtuustoaloitteeseen nuorten päihdepoliklinikan perustamiseksi Turkuun"
    # The appeal instructions after the last item are not part of it.
    assert all("oikaisuvaatimusohje" not in s.text for s in m.items[5].sections)


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.content = text.encode()


class FakeFetcher:
    routes = {
        "/sitemap.xml": "sitemap.xml",
        "/sitemap-months/0.xml": "sitemap-month0.xml",
        "/tiedote/72406089/varhan-aluehallituksen-12102026-kokouksen-tarkastamaton-poytakirja?publisherId=69820130&lang=fi":
            "release72406089.html",
        "/files/69820130/72406089/522021/fi": "aluehallitus_2026-10-12.txt",
    }

    def __init__(self, **kw):
        self.requests_made = 0

    def allowed(self, url):
        return True

    def get(self, url):
        self.requests_made += 1
        for key, name in self.routes.items():
            if url.endswith(key):
                return FakeResponse((FIX / name).read_text(encoding="utf-8"))
        raise requests.HTTPError(f"404 {url}")


def test_sttinfo_region(tmp_path, monkeypatch):
    monkeypatch.setattr("terveyshamsteri.run.Fetcher", FakeFetcher)
    monkeypatch.setattr(sttinfo, "pdf_text", lambda data: data.decode())
    region = {"id": "varsinais-suomi", "since": "2025-06-01", "epochs": [{
        "platform": "sttinfo", "base_url": "https://www.sttinfo.fi", "publisher_id": 69820130,
        "newsroom_url": "https://www.sttinfo.fi/uutishuone/69820130/varsinais-suomen-hyvinvointialue-varha"}]}
    status = scrape_region(region, tmp_path)
    assert status["result"] == "ok", status
    # Only the Finnish minutes release of this publisher; the month before the start date
    # is never fetched (it has no route here).
    assert status["fetched"] == 1
    bodies = json.loads((tmp_path / "varsinais-suomi" / "bodies.json").read_text())
    assert [b["id"] for b in bodies] == ["aluehallitus"]
    m = json.loads((tmp_path / "varsinais-suomi" / "meetings" / "aluehallitus" / "2026-10-12.json").read_text())
    assert m["stage"] == "minutes-unverified"
    assert m["pdf_url"] == "https://www.sttinfo.fi/files/69820130/72406089/522021/fi"
    assert len(m["items"]) == 6


def test_handling_separator_removed():
    from terveyshamsteri.adapters.sttinfo import _strip_headers
    lines = ["Päätös", "", "Päätösehdotus hyväksyttiin.", "_________________________________",
             "Aluehallitus 8.9.2025", "", "Toimivalta"]
    assert _strip_headers(lines) == ["Päätös", "", "Päätösehdotus hyväksyttiin.", "", "Toimivalta"]
