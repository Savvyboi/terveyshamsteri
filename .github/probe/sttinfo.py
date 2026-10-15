"""Temporary: dump STT Info structure for the Varha adapter."""
import io, re, sys
from bs4 import BeautifulSoup
from pypdf import PdfReader
sys.path.insert(0, "scraper")
from terveyshamsteri.http import Fetcher

f = Fetcher(delay=1.5)
L = "https://www.sttinfo.fi/uutishuone/69820130/varsinais-suomen-hyvinvointialue-varha/r"
r = f.get(L)
s = BeautifulSoup(r.text, "lxml")
print("=== LISTING", r.status_code, len(r.text))
for a in s.find_all("a", href=True):
    h = a["href"]
    if "tiedote" in h or "page" in h.lower() or "sivu" in h.lower() or re.search(r"[?&]p=|/r/|offset", h):
        print("A", repr(h), "|", a.get_text(" ", strip=True)[:140])
for el in s.select("[data-page],[data-url],[data-href]")[:20]:
    print("DATA", el.name, dict(el.attrs))
for sc in s.find_all("script", src=True)[:20]:
    print("SCRIPT", sc["src"])
i = r.text.find("Viimeinen")
print("AROUND-LAST", r.text[max(0, i - 1500):i + 300])
for u in ["https://www.sttinfo.fi/tiedote/72406089/varhan-aluehallituksen-12102026-kokouksen-tarkastamaton-poytakirja?publisherId=69820130&lang=fi",
          "https://www.sttinfo.fi/tiedote/72362771/varhan-3092026-aluevaltuuston-esityslista?publisherId=69820130&lang=fi"]:
    r = f.get(u)
    s = BeautifulSoup(r.text, "lxml")
    print("=== RELEASE", u, r.status_code)
    main = s.find("main") or s.body
    print("TEXT", main.get_text("\n", strip=True)[:2500])
    pdfs = []
    for a in s.find_all("a", href=True):
        h = a["href"]
        if "/files/" in h or h.lower().endswith(".pdf") or "attachment" in h:
            print("ATT", repr(h), "|", a.get_text(" ", strip=True)[:140])
            pdfs.append(h)
    for h in pdfs[:1]:
        h = h if h.startswith("http") else "https://www.sttinfo.fi" + h
        p = f.get(h)
        print("PDF", h, p.status_code, p.headers.get("content-type"), len(p.content), p.headers.get("content-disposition"))
        rd = PdfReader(io.BytesIO(p.content))
        txt = "\n".join((pg.extract_text() or "") for pg in rd.pages)
        print("PAGES", len(rd.pages), "CHARS", len(txt))
        lines = txt.split("\n")
        print("----- HEAD"); print("\n".join(lines[:260]))
        mid = len(lines) // 2
        print("----- MID"); print("\n".join(lines[mid:mid + 160]))
        print("----- TAIL"); print("\n".join(lines[-80:]))
