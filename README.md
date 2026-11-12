# Terveyshamsteri

Finnish wellbeing services counties (hyvinvointialueet) publish their agendas and minutes in
several different vendor systems. Terveyshamsteri scrapes them once a week and publishes a
searchable, bilingual (Finnish and Swedish) static site on GitHub Pages, so that citizens,
researchers and journalists can see what was decided, who voted how, and where every claim
came from.

## How it works

```
regions/*.yaml            one config per region: platform, URLs, source epochs, language
scraper/                  Python: adapters per platform -> normalized JSON
  terveyshamsteri/adapters/{dynasty,cloudnc,mfiles,sttinfo,tweb}.py
.github/workflows/
  scrape.yml              Sunday night: scrape each enabled region, push to the `data` branch, deploy
  deploy.yml              build the Astro site + Pagefind index and publish to GitHub Pages
  ci.yml                  tests, a site build with sample data, and a live probe of the pilot regions
site/                     Astro static site, Pagefind full-text search in the browser
```

Data lives on the `data` branch, not on `main`:

```
regions.json  status.json
{region}/bodies.json  {region}/status.json  {region}/state.json
{region}/meetings/{body}/{yyyy-mm-dd}.json
```

Each meeting file holds the meeting, its agenda items (title, diary number, preparer,
proposal, decision, full text split into sections, attachments, votes) and participants,
plus provenance: source URL, fetch time, content hash and parser version. The `data` branch is
force-pushed as a single commit each week, so personal data that a region removes after the
appeal period (Hyvinvointialuelaki 145 §) also disappears from our git history.

Each run re-checks the last 60 days, so agendas turn into minutes and redactions are mirrored.
A first run backfills from `since` (default 1.6.2025, the start of the current council term)
within a time budget; anything left over continues the next week.

## Coverage

| Region | Platform | Status |
|---|---|---|
| Keski-Suomi, Kanta-Häme, Etelä-Savo, Pohjois-Savo, Pohjois-Karjala, Keski-Pohjanmaa, Pohjanmaa, Länsi-Uusimaa | Dynasty | enabled |
| Pirkanmaa, Itä-Uusimaa, Keski-Uusimaa, Vantaa–Kerava, Kainuu, Pohjois-Pohjanmaa, Satakunta | CloudNC | enabled |
| Etelä-Karjala | M-Files | enabled, fetched gently (robots.txt disallows crawlers) |
| Varsinais-Suomi | STT Info press releases | enabled: board minutes only, as Varha's own Tweb is unreachable |
| Päijät-Häme, Lappi, Etelä-Pohjanmaa, Kymenlaakso | Tweb | scraped weekly from a computer in Finland (see below) |

The Tweb hosts time out or are turned away by a firewall when contacted from GitHub Actions,
whatever the User-Agent, so they need the county to open access, or a scraper run from a Finnish
network (a self-hosted runner). Their configs are ready (`gentle: true`); a Tweb adapter still
has to be written once a host can be reached.

## Hosts that disallow crawlers

Minutes are public documents that a county must publish (Hyvinvointialuelaki 145 §). Where a
host's robots.txt turns all crawlers away, the region's epoch can say `gentle: true`. Those hosts
are still fetched, but:

- at most one request every 5 seconds (or the robots.txt Crawl-delay, if longer), one at a time,
  once a week, and only new meetings or meetings from the last 60 days;
- with an honest User-Agent that links to this repository;
- honouring `Retry-After`, slowing down on 429/503, and stopping for the week after three
  failures in a row or when asked to wait more than five minutes;
- `status.json` lists the hosts fetched this way under `robots_ignored`.

## Counties scraped from a computer in Finland

Some Tweb servers (Päijät-Häme, Lappi, Etelä-Pohjanmaa, Kymenlaakso) do not answer GitHub's
servers at all. Their configs say `runner: local`, so the Weekly scrape skips them and
`.github/workflows/scrape-local.yml` scrapes them instead, on a self-hosted runner on a Windows
computer in Finland, every Sunday at 17:00 UTC. It pushes its results to the `data-local` branch
(one commit, force-pushed), and the Weekly scrape copies them into `data` when it publishes. If the
computer is off, the site keeps the last local results.

Setting up the runner (once):

1. Repository settings → Actions → Runners → New self-hosted runner → Windows x64. Download and
   unpack it to `C:\actions-runner`, then in an administrator PowerShell there run
   `.\config.cmd --url https://github.com/Savvyboi/terveyshamsteri --token <token from that page>
   --name savvas-pc --labels terveyshamsteri-fi --work _work --runasservice --unattended`.
   The service starts with Windows, so nobody needs to be logged in. The workflow brings its own
   Python (via uv), so nothing else needs installing.
2. Repository settings → Actions → General → "Fork pull request workflows from outside
   collaborators": choose **Require approval for all outside collaborators**, so no one else's
   pull request can run code on that computer.
3. Repository settings → Secrets and variables → Actions → Variables: set `LOCAL_RUNNER` to
   `true`, so the Sunday run is scheduled.
4. Actions → Local scrape (Finland) → Run workflow, to try it.

## Privacy rules built in

- Individual-case and personnel sections, employer/employee bodies and test bodies are never fetched
  (`DEFAULT_EXCLUDE_BODIES` in `scraper/terveyshamsteri/text.py`, extendable per region).
- E-mail addresses, phone numbers and personal identity codes are stripped before anything is written.
- PDFs and attachments are linked, never copied.
- Takedown requests go through a GitHub issue template.

## Running locally

```sh
cd scraper
pip install -r requirements.txt pytest
python -m pytest -q
python -m terveyshamsteri scrape pirkanmaa --data ../data --max-meetings 5
python -m terveyshamsteri index --data ../data

cd ../site
npm ci
npm run sample                          # or use ../data from the scrape above
DATA_DIR=./sample-data npm run build    # site in dist/, search index in dist/pagefind
npx astro preview
```

## Setting up GitHub Pages

1. Settings → Pages → Build and deployment → Source: **GitHub Actions**.
2. Actions → *Weekly scrape* → *Run workflow* for the first backfill (or wait for Sunday).

GitHub disables scheduled workflows after 60 days without repository activity; the weekly
push to the `data` branch counts as activity.

## Roadmap

Following the project plan: pilots → all 21 regions and people (election data, memberships,
interest registers) → reviewed votes → money (Tutkihallintoa, Hilma, purchase invoices) →
links into meeting recordings.
