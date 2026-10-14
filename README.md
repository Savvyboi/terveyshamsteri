# Terveyshamsteri

Finnish wellbeing services counties (hyvinvointialueet) publish their agendas and minutes in
three different vendor systems. Terveyshamsteri scrapes them once a week and publishes a
searchable, bilingual (Finnish and Swedish) static site on GitHub Pages, so that citizens,
researchers and journalists can see what was decided, who voted how, and where every claim
came from.

## How it works

```
regions/*.yaml            one config per region: platform, URLs, source epochs, language
scraper/                  Python: adapters per platform -> normalized JSON
  terveyshamsteri/adapters/{dynasty,cloudnc,tweb}.py
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
| Päijät-Häme, Lappi, Varsinais-Suomi | Tweb | not supported: the Päijät-Häme and Lappi hosts disallow crawlers in robots.txt |
| Etelä-Pohjanmaa, Etelä-Karjala, Kymenlaakso | own site / unknown | not yet supported |

Dynasty and CloudNC regions should work by flipping `enabled: true` once their hosts are
confirmed (see `source_status` in each YAML). Tweb needs the region's permission or a bulk
export, and Etelä-Pohjanmaa needs a PDF adapter.

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
