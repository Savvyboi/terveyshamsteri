"""Generate a small synthetic dataset for building the site locally without scraping.

  python -m terveyshamsteri.sample ../site/sample-data

Everything here is made up: an imaginary region, imaginary people, imaginary decisions."""

from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from pathlib import Path

from .elections import PARTIES, summarize
from .text import slugify

PEOPLE = ["Aaltonen Aino", "Bergström Erik", "Heikkinen Juha", "Kallio Sanna", "Laine Mikko",
          "Mäkinen Riikka", "Niemi Oskari", "Ojala Helmi", "Rantanen Ville", "Salo Emilia",
          "Toivonen Pekka", "Virtanen Laura", "Wikström Anna", "Yli-Koski Tero"]
OFFICIALS = [("Johtaja Jaana", "hyvinvointialuejohtaja, esittelijä"),
             ("Kirjuri Kalle", "hallintojohtaja, pöytäkirjanpitäjä")]
TOPICS = [
    ("Talousarvion toteutuminen {q}/{y}", "Aluehallitus merkitsee talousarvion toteutumisen tiedoksi."),
    ("Terveysaseman aukioloaikojen muutos", "Aluehallitus hyväksyy terveysaseman aukioloaikojen muutoksen 1.1. alkaen."),
    ("Valtuustoaloite kotihoidon henkilöstömitoituksesta", "Aloite lähetetään valmisteltavaksi."),
    ("Palveluverkkosuunnitelma {y}-{y2}", "Aluevaltuusto hyväksyy palveluverkkosuunnitelman."),
    ("Hankintapäätös: ensihoidon ajoneuvot", "Hankinta tehdään tarjouskilpailun voittaneelta toimittajalta."),
    ("Lausunto sosiaalihuoltolain muuttamisesta", "Aluehallitus antaa lausunnon liitteen mukaisesti."),
    ("Kuukausiraportti", "Aluehallitus merkitsee raportin tiedoksi."),
    ("Henkilöstökertomus {y}", "Merkitään tiedoksi."),
]
BODIES = [("Aluevaltuusto", "council"), ("Aluehallitus", "board"),
          ("Ikääntyneiden palvelujen lautakunta", "committee"), ("Vanhusneuvosto", "advisory")]
BASE = "https://example.invalid"


def main(out: Path) -> None:
    rnd = random.Random(7)
    rid = "esimerkki"
    root = out / rid
    bodies = []
    for name, typ in BODIES:
        bid = slugify(name)
        bodies.append({"id": bid, "name": name, "type": typ, "url": f"{BASE}/{bid}", "language": "fi"})
        d = date(2026, 10, 6)
        for n in range(8):
            d -= timedelta(days=rnd.choice([14, 21, 28]))
            members = rnd.sample(PEOPLE, 11)
            absent = rnd.sample([p for p in PEOPLE if p not in members], 1)
            items = []
            for k in range(rnd.randint(3, 7)):
                title, decision = rnd.choice(TOPICS)
                title = title.format(q=rnd.randint(1, 4), y=d.year, y2=d.year + 3)
                votes = []
                discussion = None
                if rnd.random() < 0.25:
                    jaa = rnd.randint(5, 9)
                    ei = 11 - jaa
                    proposer = rnd.choice(members)
                    discussion = (f"{proposer} ehdotti, että asia palautetaan uudelleen valmisteltavaksi. "
                                  f"Ehdotusta kannatettiin.\n\nPuheenjohtaja totesi, että on äänestettävä. "
                                  f"JAA = päätösehdotus, EI = palautusehdotus. Äänestyksessä annettiin "
                                  f"{jaa} JAA-ääntä ja {ei} EI-ääntä.")
                    votes = [{"counts": {"jaa": jaa, "ei": ei}, "context": discussion.split("\n\n")[1],
                              "provisional": True}]
                proposal = decision
                body_text = ("Asian taustalla on alueen palvelustrategia ja talousarvio. "
                             "Esimerkkiteksti kuvaa, miltä perustelut näyttävät sivulla.")
                sections = [{"heading": "", "text": f"Dno ESIM/{rnd.randint(100, 9999)}/00.01/{d.year}"},
                            {"heading": "Perustelut", "text": body_text},
                            {"heading": "Päätösehdotus", "text": proposal}]
                if discussion:
                    sections.append({"heading": "Kokouskäsittely", "text": discussion})
                sections.append({"heading": "Päätös", "text": decision if not votes else
                                 f"Päätösehdotus hyväksyttiin äänin {votes[0]['counts']['jaa']}–"
                                 f"{votes[0]['counts']['ei']}."})
                items.append({
                    "number": str(100 + n * 10 + k), "title": title,
                    "source_url": f"{BASE}/{bid}/{d}/{k}", "pdf_url": None,
                    "diary_number": sections[0]["text"][4:], "preparer": "Talousjohtaja Tuula Talous",
                    "presenter": OFFICIALS[0][0], "proposal": proposal, "decision": sections[-1]["text"],
                    "discussion": discussion, "sections": sections,
                    "attachments": [{"title": "Liite 1", "url": f"{BASE}/liite.pdf"}] if k % 2 else [],
                    "votes": votes, "redacted": False,
                })
            participants = ([{"name": p, "role": "jäsen", "group": "member"} for p in members] +
                            [{"name": p, "role": "jäsen", "group": "absent"} for p in absent] +
                            [{"name": nm, "role": r, "group": "other"} for nm, r in OFFICIALS])
            participants[0]["role"] = "puheenjohtaja"
            meeting = {
                "id": f"{bid}/{d}", "region": rid, "body_id": bid, "body_name": name, "date": str(d),
                "stage": "minutes", "source_url": f"{BASE}/{bid}/{d}", "pdf_url": f"{BASE}/{bid}/{d}.pdf",
                "time": "16:00 - 18:30", "place": "Hallintokeskus", "language": "fi", "items": items,
                "participants": participants,
                "provenance": {"source_url": f"{BASE}/{bid}/{d}", "fetched_at": "2026-10-12T01:00:00+00:00",
                               "content_hash": "0" * 16, "parser_version": "sample", "platform": "sample",
                               "first_seen": "2026-10-12T01:00:00+00:00"},
            }
            p = root / "meetings" / bid / f"{d}.json"
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(meeting, ensure_ascii=False, indent=1), encoding="utf-8")
    (root / "bodies.json").write_text(json.dumps(bodies, ensure_ascii=False, indent=1), encoding="utf-8")
    status = {"region": rid, "result": "ok", "finished_at": "2026-10-12T01:00:00+00:00", "fetched": 32,
              "changed": 32, "unchanged": 0, "removed": 0, "errors": [], "complete": True}
    (root / "status.json").write_text(json.dumps(status), encoding="utf-8")
    regions = [{
        "id": rid, "name": {"fi": "Esimerkin hyvinvointialue", "sv": "Exempels välfärdsområde"},
        "short": {"fi": "Esimerkki", "sv": "Exempel"}, "homepage": "https://example.invalid",
        "enabled": True, "platforms": ["sample"],
        "sources": [{"platform": "sample", "url": BASE, "valid_from": None, "valid_to": None}],
        "since": "2025-06-01", "notes": {"fi": "Keksitty esimerkkialue kehitystä varten.",
                                         "sv": "Påhittat exempelområde för utveckling."},
        "meetings": 32, "status": status,
    }, {
        "id": "toinen", "name": {"fi": "Toisen hyvinvointialue", "sv": "Andra välfärdsområde"},
        "short": {"fi": "Toinen", "sv": "Andra"}, "homepage": None, "enabled": False,
        "platforms": ["tweb"], "sources": [], "since": None, "notes": {}, "meetings": 0, "status": None,
    }]
    (out / "regions.json").write_text(json.dumps(regions, ensure_ascii=False, indent=1), encoding="utf-8")
    (out / "status.json").write_text(json.dumps({"updated_at": "2026-10-12T01:00:00+00:00",
                                                 "regions": {rid: "ok"}}), encoding="utf-8")

    # Election results: the first ten people were elected, the rest are deputies.
    parties = ["KOK", "SDP", "PS", "KESK", "VIHR"]
    candidates = [{"id": str(i), "name": name, "party": parties[i % len(parties)], "votes": 2000 - 120 * i,
                   "share": None, "status": "elected" if i < 10 else "deputy", "incumbent": i % 3 == 0}
                  for i, name in enumerate(PEOPLE)]
    candidates += [{"id": f"x{i}", "name": f"Ehdokas{i} Eino", "party": parties[i % len(parties)], "votes": 50 + i,
                    "share": None, "status": "not-elected", "incumbent": False} for i in range(20)]
    edir = out / "elections" / "2025"
    edir.mkdir(parents=True, exist_ok=True)
    (edir / f"{rid}.json").write_text(json.dumps(summarize(rid, "sample", candidates), ensure_ascii=False, indent=1),
                                      encoding="utf-8")
    (out / "elections" / "parties.json").write_text(json.dumps(PARTIES, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]))
