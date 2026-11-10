"""M-Files meeting site (Etelä-Karjala), from pages and PDF text saved from the live site."""

import json
from pathlib import Path

import requests

from terveyshamsteri.adapters import mfiles
from terveyshamsteri.run import gentle_hosts, scrape_region

FIX = Path(__file__).parent / "fixtures" / "mfiles"
B = "https://mfiles.ekhva.fi/Kokoukset/ekhva"
REGION = {"id": "etela-karjala", "since": "2025-06-01", "epochs": [{
    "platform": "mfiles", "base_url": "https://mfiles.ekhva.fi", "gentle": True,
    "entry_url": "https://mfiles.ekhva.fi/kokoukset/ekhva/"}]}
ROUTES = {
    f"{B}/": "root.html",
    f"{B}/21": "body21.html",
    f"{B}/22": None,                     # the board's list fails to load in this test
    f"{B}/21/356": "meeting356.html",
    f"{B}/21/393": None,
    f"{B}/21/356/4105/download/358780": "item358780.txt",
    f"{B}/21/356/4154/download/358784": "item358784.txt",
    f"{B}/21/356/0/download/365452": "meeting356.txt",
}


class Resp:
    def __init__(self, text):
        self.text = text
        self.content = text.encode()


class FakeFetcher:
    def __init__(self, **kw):
        self.requests_made = 0
        self.urls = []

    def get(self, url):
        self.requests_made += 1
        self.urls.append(url)
        name = ROUTES.get(url)
        if not name:
            raise requests.HTTPError(f"404 {url}")
        return Resp((FIX / name).read_text(encoding="utf-8"))


def test_gentle_hosts_from_config():
    assert gentle_hosts(REGION) == ["mfiles.ekhva.fi"]


def test_mfiles_region(tmp_path, monkeypatch):
    fetchers = []
    monkeypatch.setattr("terveyshamsteri.run.Fetcher", lambda **kw: fetchers.append(FakeFetcher()) or fetchers[-1])
    monkeypatch.setattr(mfiles, "pdf_text", lambda data: data.decode())
    status = scrape_region(REGION, tmp_path)
    # 10.11.2026 agenda fails (no fixture), 2024 meeting is before `since`
    assert status["fetched"] == 1, status
    assert not any("/23" in u for u in fetchers[0].urls)          # individual-case section never fetched
    assert not any("4174" in u for u in fetchers[0].urls)         # appeal instructions not fetched

    m = json.loads((tmp_path / "etela-karjala/meetings/aluevaltuusto/2026-04-21.json").read_text())
    assert m["stage"] == "minutes"
    assert m["pdf_url"] == f"{B}/21/356/0/download/365452"
    assert m["time"] == "18:00 - 19:08"
    assert m["place"].startswith("Lappeenrannan kaupungintalo")
    assert [i["number"] for i in m["items"]] == ["21", "28", "30"]

    people = {p["name"]: p for p in m["participants"]}
    assert people["Ikävalko Johanna"] == {"name": "Ikävalko Johanna", "role": "Puheenjohtaja", "group": "member"}
    assert people["Härkönen Timo"]["group"] == "member"
    assert people["Paananen Taina"]["role"] == "Jäsen"
    assert people["Kymäläinen Suna"]["group"] == "other"
    assert people["Helminen Anna"]["group"] == "absent"
    assert "Heinonen Merja" not in people and "Tamminen Juuso" not in people   # absent officials
    assert people["Heino Kaisa"] == {"name": "Heino Kaisa", "role": "Strategia- ja hallintojohtaja, kokoussihteeri",
                                     "group": "other"}

    first = m["items"][0]
    assert first["title"] == "Kokouksen laillisuus ja päätösvaltaisuus"
    assert first["proposal"] == "Kokous todetaan laillisesti koolle kutsutuksi ja päätösvaltaiseksi."
    assert first["decision"] == "Todettiin kokous lailliseksi ja päätösvaltaiseksi."
    assert first["pdf_url"] == f"{B}/21/356/4105/download/358780"

    it = m["items"][1]
    assert it["diary_number"] == "EKHVA/6531/00.01.04.30/2025"
    assert [a["url"] for a in it["attachments"]] == [f"{B}/21/356/4154/download/283782", f"{B}/21/356/4154/download/365454"]
    assert it["decision"].startswith("Keskustelun aikana")
    # The council's own proposal, under the presenter line 'Aluehalllitus' (sic), not the board's
    assert it["proposal"].startswith("Aluevaltuusto päättää merkitä"), it["proposal"]
    assert it["preparer"] == "Heino Kaisa"
    assert it["votes"][0]["counts"]["jaa"] == 56 and it["votes"][0]["counts"]["ei"] == 2
    full = json.dumps(it, ensure_ascii=False)
    assert "040 627 5521" not in full and "Yhteydenotot" not in full

    assert status["result"] == "partial"     # the board's list failed, so nothing is removed
    assert status["removed"] == 0
