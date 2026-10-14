"""Temporary: find an open API for wellbeing services county finances (Valtiokonttori)."""
import re, urllib.request, urllib.parse

def get(u, n=400000):
    req = urllib.request.Request(u, headers={"User-Agent": "terveyshamsteri-probe", "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.status, r.headers.get("content-type", ""), r.read(n).decode("utf-8", "replace")

def note(title, msg):
    print(f"::notice title={title}::" + msg.replace("\n", " ")[:3800])

# 1. Crawl the avoindata portal's scripts for API addresses.
found = set()
try:
    _, _, html = get("https://avoindata.tutkihallintoa.fi/apis")
    scripts = re.findall(r'src="([^"]+\.js[^"]*)"', html)
    note("PORTAL", f"scripts={scripts[:10]} html={html[:600]}")
    for s in scripts[:15]:
        u = urllib.parse.urljoin("https://avoindata.tutkihallintoa.fi/", s)
        try:
            _, _, js = get(u, 5_000_000)
            found |= set(re.findall(r'https?://[a-z0-9.-]*(?:tutkihallintoa|valtiokonttori|azure-api|azurewebsites|cloudapp)[^"\'\s`)]*', js))
            found |= {"PATH:" + p for p in re.findall(r'["\'](/(?:apis?|developer|docs)[^"\']{0,80})["\']', js)}
        except Exception as e:
            note("SCRIPT", f"{u} {e!r}")
except Exception as e:
    note("PORTAL", repr(e))
note("FOUND", " | ".join(sorted(found))[:3800])

# 2. Try likely catalogue and API addresses.
for u in [
    "https://avoindata.tutkihallintoa.fi/developer/apis",
    "https://avoindata.tutkihallintoa.fi/developer/apis?api-version=2022-04-01-preview",
    "https://api.tutkihallintoa.fi/",
    "https://api.tutkihallintoa.fi/kuntatalous/v1/",
    "https://api.tutkihallintoa.fi/hyvinvointialuetalous/v1/",
    "https://api.tutkihallintoa.fi/hyvinvointialueet/v1/",
    "https://www.exploreadministration.fi/application-program-interfaces/",
    "https://www.tutkihallintoa.fi/avoimet-rajapinnat/",
]:
    try:
        st, ct, body = get(u)
        links = sorted(set(re.findall(r'https?://(?:api|avoindata)\.tutkihallintoa\.fi[^"\'\s<)]*', body)))
        note(f"GET {st}", f"{u} [{ct}] links={links[:40]} body={re.sub(r'<[^>]+>', ' ', body)[:800]}")
    except Exception as e:
        note("GET ERR", f"{u} {e!r}")
