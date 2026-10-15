"""Temporary: print robots.txt and chunks of raw HTML as GitHub notices."""
import re
import sys
from urllib.parse import urlparse

import requests

UA = {"User-Agent": "terveyshamsteri-probe (+https://github.com/Savvyboi/terveyshamsteri)"}


def notice(title, msg):
    msg = msg.replace("%", "%25").replace("\r", "").replace("\n", "%0A")
    print(f"::notice title={title}::{msg[:3900]}")


for host in sorted({urlparse(u).netloc for u in sys.argv[1:]}):
    try:
        r = requests.get(f"https://{host}/robots.txt", headers=UA, timeout=30)
        notice(f"ROBOTS {host}", f"{r.status_code}\n{r.text[:1500]}")
    except Exception as e:
        notice(f"ROBOTS {host}", repr(e))
for i, url in enumerate(sys.argv[1:]):
    try:
        r = requests.get(url, headers=UA, timeout=30)
    except Exception as e:
        notice(f"RAW {i}", f"{url} {e!r}")
        continue
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", r.text, flags=re.S)
    body = re.sub(r"\s+", " ", body)
    head = f"{url} -> {r.url} {r.status_code} {r.headers.get('content-type')} len={len(r.content)}\n"
    for k in range(3):
        notice(f"RAW {i}.{k}", head + body[k * 3500:(k + 1) * 3500])
