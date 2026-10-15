"""Temporary: map where a county publishes its minutes. Prints GitHub notice annotations."""
import re
import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

KEY = re.compile(r"päätöksen|paatoksen|pöytäkir|poytakir|esityslist|kokous|valtuusto|aluehallitus|tweb|dynasty|cloudnc|\.pdf|julkais|lautakun", re.I)
UA = {"User-Agent": "terveyshamsteri-probe (+https://github.com/Savvyboi/terveyshamsteri)"}


def notice(title, msg):
    msg = msg.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::notice title={title}::{msg[:3800]}")


def links(url):
    r = requests.get(url, headers=UA, timeout=30)
    s = BeautifulSoup(r.text, "html.parser")
    out = []
    for a in s.find_all("a", href=True):
        t = a.get_text(" ", strip=True)
        h = urljoin(r.url, a["href"])
        if KEY.search(t) or KEY.search(h):
            out.append((t[:70], h))
    return r, out


start, depth = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2
host = urlparse(start).netloc
try:
    rb = requests.get(f"https://{host}/robots.txt", headers=UA, timeout=30)
    notice(f"ROBOTS {host}", f"{rb.status_code}\n{rb.text[:1500]}")
except Exception as e:
    notice(f"ROBOTS {host}", repr(e))
seen, queue, n = set(), [(start, 0)], 0
while queue and n < 9:
    url, d = queue.pop(0)
    if url in seen:
        continue
    seen.add(url)
    try:
        r, ls = links(url)
    except Exception as e:
        notice(f"PAGE {n}", f"{url} {e!r}")
        n += 1
        continue
    uniq = list(dict.fromkeys(ls))
    notice(f"PAGE {n} {r.status_code}", f"{url} -> {r.url}\n" + "\n".join(f"{t} | {h}" for t, h in uniq[:45]))
    n += 1
    if d + 1 < depth:
        for t, h in uniq:
            if urlparse(h).netloc.endswith(host.removeprefix("www.")) and not h.lower().endswith(".pdf") \
                    and re.search(r"päätöksen|paatoksen|pöytäkir|poytakir|esityslist|julkais", t + h, re.I):
                queue.append((h, d + 1))
