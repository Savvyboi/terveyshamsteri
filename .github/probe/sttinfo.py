"""Temporary: find how STT Info pages a publisher's releases."""
import json, re, sys
sys.path.insert(0, "scraper")
from terveyshamsteri.http import Fetcher

f = Fetcher(delay=1.5)
js = f.get("https://www.sttinfo.fi/public/b/app.a3f0c88074bff42a455b.js").text
for key in ["/public-website-api/releases", "pressroomreleases", "resultsShownQuantity"]:
    for m in list(re.finditer(re.escape(key), js))[:4]:
        print("CTX", key, "::", js[max(0, m.start() - 600):m.end() + 600].replace("\n", " "))
for m in list(re.finditer(r"public-website-api[^\"'`]{0,80}", js))[:60]:
    print("API", m.group(0))
B = "https://www.sttinfo.fi/public-website-api"
for u in [B + "/releases?publisherId=69820130", B + "/releases?publisherId=69820130&page=1",
          B + "/releases/pressroom/69820130", B + "/releases/pressroom/69820130?page=1&limit=20",
          B + "/pressroom/69820130/releases?page=1"]:
    try:
        r = f.get(u)
        print("TRY", u, r.status_code, r.headers.get("content-type"), r.text[:800].replace("\n", " "))
    except Exception as e:
        print("TRY", u, repr(e)[:300])
sm = f.get("https://www.sttinfo.fi/sitemap-months/1.xml").text
locs = re.findall(r"<loc>([^<]+)</loc>", sm)
print("SM1", len(sm), len(locs), locs[:3])
print("SMVARHA", [l for l in locs if "varha" in l][:40])
print("SMSAMPLE", sm[:1200])
