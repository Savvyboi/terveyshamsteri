"""Temporary: look at the structure of the M-Files meeting site (a few pages, slowly)."""
import re, sys, time, requests
from urllib.parse import urljoin
UA = "terveyshamsteri/0.2 (civic archive of wellbeing services county decisions; +https://github.com/Savvyboi/terveyshamsteri)"
s = requests.Session(); s.headers["User-Agent"] = UA
def show(u, full=20000, pat=None):
    time.sleep(3)
    try:
        r = s.get(u, timeout=40)
    except Exception as e:
        print("ERR", u, e); return None, []
    if not r.encoding or r.encoding.lower() == "iso-8859-1":
        r.encoding = r.apparent_encoding
    print(f"\n######## {u} -> {r.status_code} {r.headers.get('content-type')} len={len(r.content)} final={r.url}")
    t = r.text
    if "html" in (r.headers.get("content-type") or ""):
        body = t.split("<body", 1)[-1]
        body = re.sub(r"<script.*?</script>", "", body, flags=re.S)
        body = re.sub(r"\n\s*\n+", "\n", body)
        print(body[:full])
    links = [urljoin(r.url, h) for h in re.findall(r'href\s*=\s*["\']([^"\']+)', t, re.I)]
    return t, links
B = "https://mfiles.ekhva.fi/Kokoukset/ekhva"
t, links = show(f"{B}/21")              # aluevaltuusto: list of meetings
t, links = show(f"{B}/21/393")          # one meeting
items = [l for l in links if re.search(r"/Kokoukset/ekhva/21/393/.+", l)]
print("ITEM LINKS", items[:40])
for l in items[:2]:
    show(l, 15000)
other = [l for l in links if "ekhva/21/393" not in l and "Kokoukset" in l]
print("OTHER", other[:40])
show("https://lapha-julkaisu.tweb.fi/robots.txt", 2000)
show("https://lapinhva-julkaisu.triplancloud.fi/", 2000)
