"""Temporary: look at the structure of Tweb / M-Files sites (a few pages each, slowly)."""
import re, sys, time, requests
from urllib.parse import urljoin, urlsplit
UA = "terveyshamsteri/0.1 (civic archive of wellbeing services county decisions; +https://github.com/Savvyboi/terveyshamsteri)"
s = requests.Session(); s.headers["User-Agent"] = UA
def get(u):
    time.sleep(2)
    try:
        r = s.get(u, timeout=40)
        if not r.encoding or r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r
    except Exception as e:
        print("ERR", u, e); return None
def show(u, full=8000):
    r = get(u)
    print(f"\n######## {u} -> {getattr(r,'status_code',None)} {r.headers.get('content-type') if r is not None else ''} final={getattr(r,'url',None)}")
    if r is None: return None, []
    t = r.text
    print(t[:full])
    links = [urljoin(r.url, h) for h in re.findall(r'(?:href|src)\s*=\s*["\']([^"\']+)', t, re.I)]
    print("LINKS:", len(links)); [print("  ", l) for l in links[:80]]
    return t, links
for start in sys.argv[1:]:
    parts = urlsplit(start)
    show(f"{parts.scheme}://{parts.netloc}/robots.txt", 2000)
    show(start)
