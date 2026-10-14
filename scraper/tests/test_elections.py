import json
from pathlib import Path

from terveyshamsteri.elections import display_name, parse_jsonstat, summarize

FIX = Path(__file__).parent / "fixtures" / "elections"


def test_parse_and_summarize():
    doc = json.loads((FIX / "kainuu_small.json").read_text(encoding="utf-8"))
    cands = parse_jsonstat(doc)
    assert len(cands) == 4
    heikki = cands[0]
    assert heikki == {"id": "20999012176", "name": "Aaltonen Heikki", "party": "KOK", "votes": 512,
                      "share": 1.2, "status": "elected", "incumbent": True}
    s = summarize("kainuu", "14zs.px", cands)
    assert s["seats"] == 2 and s["votes_total"] == 512 + 40 + 1203 + 95
    assert [p["party"] for p in s["parties"]] == ["KESK", "KOK", "VIHR"]
    kok = next(p for p in s["parties"] if p["party"] == "KOK")
    assert kok == {"party": "KOK", "votes": 552, "candidates": 2, "seats": 1, "share": round(100 * 552 / 1850, 1)}
    # Only councillors and deputies are kept by name, elected first.
    assert [p["name"] for p in s["people"]] == ["Anna-Liisa Kemppainen", "Heikki Aaltonen", "Eva von Hertzen"]
    assert s["people"][2]["status"] == "deputy"


def test_display_name():
    assert display_name("Aaltonen Heikki") == "Heikki Aaltonen"
    assert display_name("Kemppainen Anna-Liisa") == "Anna-Liisa Kemppainen"
    assert display_name("von Hertzen Eva") == "Eva von Hertzen"
    assert display_name("Virtanen Matti Juhani") == "Matti Juhani Virtanen"
