"""Temporary: look for the published finance data behind Tutkihallintoa / Tutkikuntia."""
import json, re, urllib.request

def get(u, n=3_000_000):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return r.status, r.read(n).decode("utf-8", "replace")

def note(title, msg):
    print(f"::notice title={title}::" + msg.replace("\n", " ")[:3900])

B = "https://tkdpprodjrpstacc02.blob.core.windows.net"
for u in [f"{B}/kuntataloudentaksonomia?restype=container&comp=list", f"{B}/?comp=list",
          f"{B}/kuntataloudentaksonomia/HHTPP.json", f"{B}/kuntataloudentaksonomia/HTOLT.json",
          "https://prodkuntarest.westeurope.cloudapp.azure.com/",
          "https://www.tutkikuntia.fi/", "https://www.tutkikuntia.fi/avoimet-rajapinnat/",
          "https://www.tutkihallintoa.fi/ohjeet/"]:
    try:
        st, t = get(u)
        links = sorted(set(re.findall(r'https?://[^"\'\s<>)]*(?:rest|api|blob|xlsx|csv|json)[^"\'\s<>)]*', t)))[:60]
        text = re.sub(r"\s+", " ", re.sub(r"<script.*?</script>|<style.*?</style>|<[^>]+>", " ", t, flags=re.S))
        note(f"GET {st} {u[:60]}", f"len={len(t)} links={links} text={text[:2500]}")
    except Exception as e:
        note("ERR", f"{u} {e!r}")
