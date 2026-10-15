"""Temporary: find how STT Info pages a publisher's releases."""
import re, sys
from bs4 import BeautifulSoup
sys.path.insert(0, "scraper")
from terveyshamsteri.http import Fetcher

f = Fetcher(delay=1.5)
L = "https://www.sttinfo.fi/uutishuone/69820130/varsinais-suomen-hyvinvointialue-varha/r"

def titles(html):
    s = BeautifulSoup(html, "lxml")
    return [a["href"].split("/")[2] for a in s.find_all("a", href=True) if a["href"].startswith("/tiedote/")][:3]

for u in [L, L + "?page=2", L + "?p=2", L + "/2", L + "?sivu=2", L + "?pageNumber=2",
          "https://www.sttinfo.fi/rss/releases/latest?publisherId=69820130&page=2",
          "https://www.sttinfo.fi/rss/releases/latest?publisherId=69820130&limit=100"]:
    try:
        r = f.get(u)
        extra = ""
        if "rss" in u:
            extra = f"items={r.text.count('<item>')} first={re.findall(r'<link>([^<]+)</link>', r.text)[1:3]}"
        print("TRY", u, r.status_code, titles(r.text), extra)
    except Exception as e:
        print("TRY", u, repr(e))

r = f.get(L)
m = re.search(r"window\.__[A-Z_]+__\s*=", r.text)
print("STATE", m.group(0) if m else None)
for m in re.finditer(r"<script[^>]*>(.{0,300})", r.text):
    if "publisher" in m.group(1).lower() or "__" in m.group(1):
        print("INLINE", m.group(1)[:300])
js = f.get("https://www.sttinfo.fi/public/b/app.a3f0c88074bff42a455b.js").text
print("JS", len(js))
for pat in [r'"/api[^"]{0,120}"', r'`/api[^`]{0,160}`', r'"[^"]{0,60}releases[^"]{0,80}"', r'[a-zA-Z/]*search[a-zA-Z/?=&]{0,80}']:
    seen = set()
    for m in re.finditer(pat, js):
        v = m.group(0)
        if v not in seen and len(seen) < 40:
            seen.add(v); print("JSPAT", v)
for m in re.finditer(r"pageNumber|pageSize|offset", js):
    print("CTX", js[max(0, m.start()-200):m.end()+200].replace("\n", " "))
    break

sm = f.get("https://www.sttinfo.fi/sitemap.xml").text
print("SITEMAP", len(sm), sm[:1500])
