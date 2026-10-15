// Reads the scraped JSON (the `data` branch, checked out next to the site) at build time.
// DATA_DIR defaults to ../data and falls back to ./sample-data for local development.
import fs from 'node:fs';
import path from 'node:path';

export type Lang = 'fi' | 'sv' | 'en';
export type Bilingual = Partial<Record<Lang, string>>;

export interface Vote {
  counts: Record<string, number>; context: string; provisional: boolean; names?: Record<string, string[]>;
  /** What each side stood for, e.g. { jaa: 'Pohjaehdotus', ei: 'SDP-valtuustoryhmän muutosehdotus' }. */
  question?: Record<string, string>; motion?: string | null;
}
/** The side that got more votes, or null on a tie (the chair's vote decides, which the counts do not show). */
export const winner = (v: Vote) => {
  const { jaa = 0, ei = 0 } = v.counts;
  return jaa > ei ? 'jaa' : ei > jaa ? 'ei' : null;
};
export interface Section { heading: string; text: string }
export interface Attachment { title: string; url: string }
export interface Participant { name: string; role: string; group: 'member' | 'other' | 'absent' }
export interface Item {
  number: string; title: string; source_url: string; pdf_url: string | null;
  diary_number: string | null; preparer: string | null; presenter: string | null;
  proposal: string | null; decision: string | null; discussion: string | null;
  sections: Section[]; attachments: Attachment[]; votes: Vote[]; redacted: boolean;
}
export interface Meeting {
  id: string; region: string; body_id: string; body_name: string; date: string; stage: string;
  source_url: string; pdf_url: string | null; time: string | null; place: string | null;
  language: string; items: Item[]; participants: Participant[];
  provenance: { source_url: string; fetched_at: string; content_hash: string; parser_version: string;
    platform: string; first_seen: string };
  /** Set on bilingual counties' meetings published in both languages: which copy this is.
   * 'dup' is an agenda whose other-language copy already has minutes; it is not shown. */
  twin?: 'fi' | 'sv' | 'dup';
}
export interface Body { id: string; name: string; type: string; url: string; language: string }
export interface RegionStatus {
  result: string; finished_at?: string; fetched?: number; changed?: number; errors?: string[];
  complete?: boolean;
}
export interface Region {
  id: string; name: Bilingual; short: Bilingual; homepage: string | null; enabled: boolean;
  platforms: string[]; sources: { platform: string; url: string; valid_from: string | null; valid_to: string | null }[];
  since: string | null; notes: Bilingual; meetings: number; status: RegionStatus | null;
}

function dataDir(): string {
  const candidates = [process.env.DATA_DIR, '../data', './sample-data'].filter(Boolean) as string[];
  for (const c of candidates) {
    const p = path.resolve(c);
    if (fs.existsSync(path.join(p, 'regions.json'))) return p;
  }
  return '';
}

export const DATA_DIR = dataDir();
export const IS_SAMPLE = DATA_DIR.endsWith('sample-data');

function readJson<T>(p: string, fallback: T): T {
  try { return JSON.parse(fs.readFileSync(p, 'utf-8')) as T; } catch { return fallback; }
}

function walk(dir: string): string[] {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
    e.isDirectory() ? walk(path.join(dir, e.name)) : e.name.endsWith('.json') ? [path.join(dir, e.name)] : []);
}

let cache: { regions: Region[]; bodies: Map<string, Body[]>; meetings: Meeting[];
  status: { updated_at?: string } } | null = null;

export function load() {
  if (cache) return cache;
  const regions = DATA_DIR ? readJson<Region[]>(path.join(DATA_DIR, 'regions.json'), []) : [];
  const bodies = new Map<string, Body[]>();
  const meetings: Meeting[] = [];
  for (const r of regions) {
    bodies.set(r.id, readJson<Body[]>(path.join(DATA_DIR, r.id, 'bodies.json'), []));
    for (const f of walk(path.join(DATA_DIR, r.id, 'meetings'))) meetings.push(readJson<Meeting>(f, null as never));
  }
  meetings.sort((a, b) => b.date.localeCompare(a.date) || a.body_name.localeCompare(b.body_name));
  const status = DATA_DIR ? readJson(path.join(DATA_DIR, 'status.json'), {}) : {};
  for (const r of regions) {
    // English has no official short names; the Finnish ones are used as proper nouns.
    r.short.en ??= r.short.fi;
    r.name.en ??= `${r.short.fi} wellbeing services county`;
  }
  cache = { regions, bodies, meetings: meetings.filter(Boolean), status };
  markTwins(cache.meetings, bodies);
  return cache;
}

// Bilingual counties publish some bodies twice, once in Finnish and once in Swedish
// ("Aluehallitus" and "Välfärdsområdesstyrelsen"). Each language shows its own copy only;
// when one copy already has minutes and the other is still an agenda, the minutes are shown.
const SWEDISH_BODY = /fullmäktige|styrelse|nämnd|sektion|rådet|\bråd\b|utskott|välfärdsområde|direktion|delegation|kommitté/i;
export const isSwedishBody = (name: string) => SWEDISH_BODY.test(name);

function markTwins(meetings: Meeting[], bodies: Map<string, Body[]>) {
  const type = (m: Meeting) => (bodies.get(m.region) || []).find((b) => b.id === m.body_id)?.type ?? 'other';
  const key = (m: Meeting) => [m.region, m.date, m.items.length, type(m)].join('|');
  const finnish = new Map<string, Meeting[]>();
  for (const m of meetings) if (!isSwedishBody(m.body_name)) finnish.set(key(m), [...(finnish.get(key(m)) ?? []), m]);
  for (const m of meetings) {
    if (!isSwedishBody(m.body_name)) continue;
    const fi = (finnish.get(key(m)) ?? []).filter((x) => !x.twin);
    if (fi.length !== 1) continue;
    const agenda = (x: Meeting) => x.stage === 'agenda';
    if (agenda(m) === agenda(fi[0])) { m.twin = 'sv'; fi[0].twin = 'fi'; }
    else (agenda(m) ? m : fi[0]).twin = 'dup';
  }
}

/** The rows a list shows in each language: the first `n` of the Finnish view and the first
 * `n` of the Swedish view, in their original order. Rows tagged with a twin language are
 * hidden in the other language by CSS. */
export function bothViews<T>(rows: T[], n: number, twin: (r: T) => Meeting['twin']): T[] {
  const fi = new Set(rows.filter((r) => twin(r) !== 'sv' && twin(r) !== 'dup').slice(0, n));
  const sv = new Set(rows.filter((r) => twin(r) !== 'fi' && twin(r) !== 'dup').slice(0, n));
  return rows.filter((r) => fi.has(r) || sv.has(r));
}
/** Whether a meeting is counted: Swedish copies and superseded agendas are not. */
export const counted = (m: Meeting) => m.twin !== 'sv' && m.twin !== 'dup';

export const regionById = (id: string) => load().regions.find((r) => r.id === id)!;
/** A region's meetings, or one body's. Without a body, Swedish copies of Finnish meetings are
 * left out so nothing is counted twice; pass `twins` to list both copies. */
export const meetingsOf = (region: string, body?: string, twins = false) =>
  load().meetings.filter((m) => m.region === region && (body ? m.body_id === body : twins || counted(m)));
export const bodiesOf = (region: string) => {
  // Only bodies that have at least one meeting in our archive.
  const withMeetings = new Set(meetingsOf(region, undefined, true).map((m) => m.body_id));
  return (load().bodies.get(region) || []).filter((b) => withMeetings.has(b.id));
};
/** 'sv' for a body whose every meeting is a Swedish copy, 'fi' for one whose every meeting has one. */
export function bodyTwin(region: string, body: string): 'fi' | 'sv' | undefined {
  const ms = meetingsOf(region, body);
  for (const lang of ['fi', 'sv'] as const) {
    if (ms.length && ms.every((m) => m.twin === lang || m.twin === 'dup') && ms.some((m) => m.twin === lang)) return lang;
  }
  return undefined;
}
export const bodyById = (region: string, body: string) =>
  (load().bodies.get(region) || []).find((b) => b.id === body) ||
  { id: body, name: meetingsOf(region, body)[0]?.body_name ?? body, type: 'other', url: '', language: 'fi' };

/** URL segment of an item: its § number when unique within the meeting, else its position. */
export function itemSlug(m: Meeting, i: number): string {
  const n = m.items[i].number.replace(/[^\w-]/g, '');
  const dup = m.items.filter((x) => x.number.replace(/[^\w-]/g, '') === n).length > 1;
  return n && !dup ? n : `k${i + 1}`;
}

/** "aluevaltuusto/2026-09-29" -> path segments after the region. */
export const meetingSlug = (m: Meeting) => m.id.split('/').slice(1).join('/');

export function url(...parts: string[]): string {
  const base = import.meta.env.BASE_URL.replace(/\/$/, '');
  const p = parts.filter(Boolean).join('/');
  return `${base}/${p}${p ? '/' : ''}`;
}

export const meetingUrl = (m: Meeting) => url(m.region, m.body_id, meetingSlug(m));
export const itemUrl = (m: Meeting, i: number) => url(m.region, m.body_id, meetingSlug(m), itemSlug(m, i));

// ------------------------------------------------------------------ elections
export interface Candidate {
  id: string; name: string; official_name: string; party: string; votes: number | null; share: number | null;
  status: 'elected' | 'deputy'; incumbent: boolean;
}
export interface PartyResult { party: string; votes: number; candidates: number; seats: number; share: number | null }
export interface Election {
  region: string; year: number; source: string; fetched_at: string; votes_total: number; seats: number;
  parties: PartyResult[]; people: Candidate[];
}
export interface PartyMeta { fi: string; sv: string; en: string; color: string }

const electionCache = new Map<string, Election | null>();
export function electionOf(region: string): Election | null {
  if (!electionCache.has(region)) {
    electionCache.set(region, DATA_DIR ? readJson<Election | null>(path.join(DATA_DIR, 'elections', '2025', `${region}.json`), null) : null);
  }
  return electionCache.get(region)!;
}
let partyCache: Record<string, PartyMeta> | null = null;
export function partyMeta(code: string): PartyMeta {
  partyCache ??= DATA_DIR ? readJson(path.join(DATA_DIR, 'elections', 'parties.json'), {}) : {};
  return partyCache![code] ?? { fi: code, sv: code, en: code, color: '#7a8494' };
}
/** Parties that won at least one seat anywhere, largest first. */
export function partiesNationwide() {
  const totals = new Map<string, { party: string; seats: number; votes: number; regions: number }>();
  let votes = 0;
  for (const r of load().regions) {
    const e = electionOf(r.id);
    if (!e) continue;
    votes += e.votes_total;
    for (const p of e.parties) {
      const t = totals.get(p.party) ?? { party: p.party, seats: 0, votes: 0, regions: 0 };
      t.seats += p.seats; t.votes += p.votes; t.regions += p.seats > 0 ? 1 : 0;
      totals.set(p.party, t);
    }
  }
  return [...totals.values()].filter((t) => t.seats > 0)
    .map((t) => ({ ...t, share: votes ? Math.round((1000 * t.votes) / votes) / 10 : null }))
    .sort((a, b) => b.seats - a.seats || b.votes - a.votes);
}
export const partySlug = (code: string) => code.toLowerCase();

// ------------------------------------------------------------------ people
export interface PersonStats {
  slug: string; name: string; roles: Set<string>; present: number; absent: number;
  bodies: Map<string, { present: number; absent: number }>; meetings: { m: Meeting; group: string; role: string }[];
  member: boolean;
  /** Set when the person is a councillor or deputy elected in 2025. */
  elected?: Candidate;
  /** Attendance at full council meetings. */
  council: { present: number; absent: number };
}

export function slugify(s: string): string {
  return s.toLowerCase().replace(/[äå]/g, 'a').replace(/ö/g, 'o').normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

/** Minutes write names "Surname Firstname" or "Firstname Surname"; compare them as sets of words. */
const nameTokens = (s: string) => s.toLowerCase().normalize('NFC').split(/\s+/).filter(Boolean);
const nameKey = (s: string) => nameTokens(s).sort().join(' ');

const peopleCache = new Map<string, PersonStats[]>();
const nameIndex = new Map<string, Map<string, PersonStats>>();
export function peopleOf(region: string): PersonStats[] {
  if (peopleCache.has(region)) return peopleCache.get(region)!;
  const election = electionOf(region);
  const byKey = new Map<string, Candidate>();
  for (const c of election?.people ?? []) byKey.set(nameKey(c.name), c);
  // Fallback for middle names: a councillor whose words are all in the minutes name, if unique.
  const fuzzy = (name: string): Candidate | undefined => {
    const toks = new Set(nameTokens(name));
    const hits = (election?.people ?? []).filter((c) => nameTokens(c.name).every((t) => toks.has(t)));
    return hits.length === 1 ? hits[0] : undefined;
  };

  const people = new Map<string, PersonStats>();
  const names = new Map<string, PersonStats>();
  const blank = (name: string, elected?: Candidate): PersonStats => ({
    slug: slugify(elected ? elected.name : name), name: elected ? elected.name : name, roles: new Set(),
    present: 0, absent: 0, bodies: new Map(), meetings: [], member: !!elected, elected,
    council: { present: 0, absent: 0 },
  });
  for (const m of meetingsOf(region)) {
    if (m.stage === 'agenda') continue;
    const isCouncil = bodyTypeOf(region, m.body_id) === 'council';
    for (const p of m.participants) {
      if (!slugify(p.name)) continue;
      const elected = byKey.get(nameKey(p.name)) ?? (p.group !== 'other' ? fuzzy(p.name) : undefined);
      const key = elected ? `c:${elected.id}` : nameKey(p.name);
      let s = people.get(key);
      if (!s) { s = blank(p.name, elected); people.set(key, s); }
      names.set(p.name, s);
      const b = s.bodies.get(m.body_id) || { present: 0, absent: 0 };
      if (p.group === 'absent') { s.absent++; b.absent++; } else { s.present++; b.present++; }
      if (isCouncil && p.group !== 'other') { if (p.group === 'absent') s.council.absent++; else s.council.present++; }
      if (p.group !== 'other') s.member = true;
      if (p.role) s.roles.add(p.role);
      s.bodies.set(m.body_id, b);
      s.meetings.push({ m, group: p.group, role: p.role });
    }
  }
  // Councillors who have not appeared in any minutes we hold still get a page.
  for (const c of election?.people ?? []) {
    if (!people.has(`c:${c.id}`)) people.set(`c:${c.id}`, blank(c.name, c));
  }
  // Slugs must be unique within a region.
  const seen = new Map<string, number>();
  const out = [...people.values()].sort((a, b) => a.name.localeCompare(b.name, 'fi'));
  for (const p of out) {
    const n = (seen.get(p.slug) ?? 0) + 1;
    seen.set(p.slug, n);
    if (n > 1) p.slug = `${p.slug}-${n}`;
  }
  peopleCache.set(region, out);
  nameIndex.set(region, names);
  return out;
}

export const councillorsOf = (region: string) => peopleOf(region).filter((p) => p.elected);
export const personUrl = (region: string, p: PersonStats) => url(region, 'henkilot', p.slug);

/** The person a name in a meeting's participant list belongs to. */
export function personByName(region: string, name: string): PersonStats | undefined {
  peopleOf(region);
  return nameIndex.get(region)!.get(name);
}

export function votesOf(region?: string, twins = false) {
  const out: { m: Meeting; i: number; v: Vote }[] = [];
  const ms = region ? meetingsOf(region, undefined, twins) : load().meetings.filter((m) => twins || counted(m));
  for (const m of ms) m.items.forEach((it, i) => it.votes.forEach((v) => out.push({ m, i, v })));
  return out;
}

export function fmtDate(iso: string, lang: Lang = 'fi'): string {
  const [y, mo, d] = iso.split('-').map(Number);
  return lang === 'sv' ? `${d}.${mo}.${y}` : `${d}.${mo}.${y}`;
}

/** Body types in display order, from the council down. */
export const BODY_TYPES = ['council', 'board', 'committee', 'section', 'advisory', 'other'] as const;

export const bodyTypeOf = (region: string, body: string) =>
  (load().bodies.get(region) || []).find((b) => b.id === body)?.type ?? 'other';

export const countVotes = (m: Meeting) => m.items.reduce((a, it) => a + it.votes.length, 0);

/** Compact rows for the all-meetings table (served as JSON, filtered in the browser). */
export function meetingRows() {
  return load().meetings.map((m) => ({
    date: m.date, region: m.region, body: m.body_name, bodyType: bodyTypeOf(m.region, m.body_id),
    stage: m.stage === 'agenda' ? 'agenda' : 'minutes', items: m.items.length, votes: countVotes(m),
    url: meetingUrl(m), source: m.source_url, twin: m.twin ?? null,
  }));
}

/** Rows for the all-votes table. */
export function voteRows() {
  const out = [];
  for (const m of load().meetings) {
    for (const [i, it] of m.items.entries()) {
      for (const v of it.votes) {
        out.push({
          date: m.date, region: m.region, body: m.body_name, bodyType: bodyTypeOf(m.region, m.body_id),
          number: it.number, title: it.title, jaa: v.counts.jaa ?? null, ei: v.counts.ei ?? null,
          tyhja: v.counts.tyhja ?? null, poissa: v.counts.poissa ?? null,
          jaaMeans: v.question?.jaa ?? null, eiMeans: v.question?.ei ?? null, url: itemUrl(m, i), source: it.source_url,
          twin: m.twin ?? null,
        });
      }
    }
  }
  return out;
}

/** Rows for the nationwide councillors table. */
export function peopleRows() {
  return load().regions.flatMap((r) => councillorsOf(r.id).map((p) => ({
    name: p.name, region: r.id, party: p.elected!.party, status: p.elected!.status, incumbent: p.elected!.incumbent,
    votes: p.elected!.votes, present: p.council.present, absent: p.council.absent, url: personUrl(r.id, p),
  })));
}

export const regionsWithElections = () => load().regions.filter((r) => electionOf(r.id));

// ------------------------------------------------------------------ named votes
export type Side = 'jaa' | 'ei' | 'tyhja' | 'poissa';
export interface Ballot { m: Meeting; i: number; v: Vote; side: Side }

/** The person behind a voter name in a meeting's vote. Minutes write voters as full names in
 * either order or as surnames only ("Eskola Tapani" when two share a surname), so the name
 * is matched against the people present at that meeting. */
export function voterOf(m: Meeting, voter: string): PersonStats | undefined {
  const toks = nameTokens(voter);
  if (!toks.length) return undefined;
  const exact = m.participants.find((p) => nameKey(p.name) === nameKey(voter));
  if (exact) return personByName(m.region, exact.name);
  const hits = m.participants.filter((p) => p.group !== 'other' && toks.every((t) => nameTokens(p.name).includes(t)));
  if (hits.length === 1) return personByName(m.region, hits[0].name);
  const e = electionOf(m.region)?.people.filter((c) => toks.every((t) => nameTokens(c.name).includes(t))) ?? [];
  if (e.length === 1) return peopleOf(m.region).find((p) => p.elected?.id === e[0].id);
  return undefined;
}

const ballotCache = new Map<string, Map<PersonStats, Ballot[]>>();
/** Every named ballot in a region, by person. */
export function ballotsOf(region: string): Map<PersonStats, Ballot[]> {
  if (ballotCache.has(region)) return ballotCache.get(region)!;
  const out = new Map<PersonStats, Ballot[]>();
  for (const m of meetingsOf(region)) {
    m.items.forEach((it, i) => it.votes.forEach((v) => {
      for (const [side, names] of Object.entries(v.names ?? {})) {
        for (const n of names) {
          const p = voterOf(m, n);
          if (!p) continue;
          if (!out.has(p)) out.set(p, []);
          out.get(p)!.push({ m, i, v, side: side as Side });
        }
      }
    }));
  }
  ballotCache.set(region, out);
  return out;
}

/** Votes by party for one named vote; voters who could not be matched are counted under '?'. */
const splitCache = new WeakMap<Vote, ReturnType<typeof splitOf>>();
export function partySplit(m: Meeting, v: Vote) {
  if (!splitCache.has(v)) splitCache.set(v, splitOf(m, v));
  return splitCache.get(v)!;
}
function splitOf(m: Meeting, v: Vote) {
  const rows = new Map<string, Record<Side, number>>();
  for (const [side, names] of Object.entries(v.names ?? {})) {
    for (const n of names) {
      const party = voterOf(m, n)?.elected?.party ?? '?';
      const r = rows.get(party) ?? { jaa: 0, ei: 0, tyhja: 0, poissa: 0 };
      r[side as Side]++;
      rows.set(party, r);
    }
  }
  return [...rows.entries()].map(([party, c]) => ({ party, ...c }))
    .sort((a, b) => (a.party === '?' ? 1 : b.party === '?' ? -1 : 0) || (b.jaa + b.ei + b.tyhja) - (a.jaa + a.ei + a.tyhja));
}

/** How often a person voted with the majority of their own party, over named votes. */
export function partyLine(region: string, p: PersonStats): { agree: number; total: number } | null {
  if (!p.elected) return null;
  let agree = 0, total = 0;
  for (const b of ballotsOf(region).get(p) ?? []) {
    if (b.side !== 'jaa' && b.side !== 'ei') continue;
    const row = partySplit(b.m, b.v).find((r) => r.party === p.elected!.party);
    if (!row || row.jaa + row.ei < 2) continue;
    const majority = row.jaa > row.ei ? 'jaa' : row.ei > row.jaa ? 'ei' : null;
    if (!majority) continue;
    total++;
    if (b.side === majority) agree++;
  }
  return total ? { agree, total } : null;
}

// ------------------------------------------------------------------ finances
export type FinKey = 'income' | 'sales' | 'fees' | 'grants_in' | 'other_income' | 'expenses' | 'staff' | 'purchases'
  | 'materials' | 'grants_out' | 'other_expenses' | 'operating_margin' | 'state_funding' | 'financial'
  | 'annual_margin' | 'depreciation' | 'result' | 'surplus' | 'investments' | 'loans' | 'person_years'
  | 'balance_total' | 'equity' | 'liabilities' | 'past_surplus' | 'cumulative_surplus' | 'cash';
export type FinLines = Partial<Record<FinKey, number>>;
export interface FinDoc { key: string; report: 'HTAS' | 'HTPE' | 'HHKNR'; period: string; stage: string; approved: string;
  url: string; columns: Record<string, FinLines> }
export interface Finances { region: string; ytunnus: string; source: string; api: string; fetched_at: string;
  years: string[]; documents: FinDoc[] }
/** One column of a county's finance table: what the figures are and where they come from. */
export interface FinColumn { year: number; kind: 'actual' | 'ytd' | 'forecast' | 'budget' | 'plan'; period?: string;
  lines: FinLines; doc: FinDoc }

const finCache = new Map<string, Finances | null>();
export function financesOf(region: string): Finances | null {
  if (!finCache.has(region)) {
    finCache.set(region, DATA_DIR ? readJson<Finances | null>(path.join(DATA_DIR, 'finances', `${region}.json`), null) : null);
  }
  return finCache.get(region)!;
}

let popCache: { source?: string; regions?: Record<string, Record<string, { population: number; over64_share: number }>> } | null = null;
/** Residents on 31 December of `year`, or the latest year we have before it. */
export function populationOf(region: string, year?: number): { year: number; population: number; over64_share: number } | null {
  popCache ??= DATA_DIR ? readJson(path.join(DATA_DIR, 'finances', 'population.json'), {}) : {};
  const byYear = popCache.regions?.[region];
  if (!byYear) return null;
  const years = Object.keys(byYear).map(Number).filter((y) => !year || y <= year).sort((a, b) => b - a);
  return years.length ? { year: years[0], ...byYear[String(years[0])] } : null;
}
export const populationSource = () => (populationOf('kainuu'), popCache?.source ?? '');

/** The columns of a county's finance table in time order: results, the year so far, the
 * forecast and budget for the current year, then the plan years. */
export function financeColumns(region: string): FinColumn[] {
  const f = financesOf(region);
  if (!f) return [];
  const docs = new Map(f.documents.map((d) => [d.key, d]));
  const out: FinColumn[] = [];
  const actualYears = f.documents.filter((d) => d.report === 'HHKNR' && d.period.endsWith('C12')).map((d) => +d.period.slice(0, 4));
  const lastActual = Math.max(0, ...actualYears);
  for (const y of actualYears.sort()) out.push({ year: y, kind: 'actual', lines: docs.get(`HHKNR/${y}C12`)!.columns[''] ?? {}, doc: docs.get(`HHKNR/${y}C12`)! });
  const ytd = f.documents.filter((d) => d.report === 'HHKNR' && !d.period.endsWith('C12') && +d.period.slice(0, 4) > lastActual)
    .sort((a, b) => a.period.localeCompare(b.period)).at(-1);
  const cur = lastActual + 1;
  if (ytd) out.push({ year: cur, kind: 'ytd', period: ytd.period, lines: ytd.columns[''] ?? {}, doc: ytd });
  const fc = docs.get(`HTPE/${cur}`);
  if (fc?.columns['']) out.push({ year: cur, kind: 'forecast', lines: fc.columns[''], doc: fc });
  const budgets = f.documents.filter((d) => d.report === 'HTAS').sort((a, b) => a.period.localeCompare(b.period));
  const b = docs.get(`HTAS/${cur}`);
  if (b?.columns['0']) out.push({ year: cur, kind: 'budget', lines: b.columns['0'], doc: b });
  const latest = budgets.at(-1);
  if (latest) {
    for (const off of ['1', '2']) {
      const y = +latest.period + +off;
      if (y > cur && latest.columns[off]) out.push({ year: y, kind: 'plan', lines: latest.columns[off], doc: latest });
    }
  }
  return out;
}

export interface FinSummary {
  region: Region; year: number; population: number | null; over64: number | null; actual: FinLines;
  forecast: FinLines | null; budget: FinLines | null; ytd: FinColumn | null;
  perCapita: (k: FinKey, lines?: FinLines | null) => number | null;
}
/** Headline figures for one county: the latest full year, and this year's forecast. */
export function financeSummary(region: string): FinSummary | null {
  const cols = financeColumns(region);
  const actual = cols.filter((c) => c.kind === 'actual').at(-1);
  if (!actual) return null;
  const pop = populationOf(region, actual.year);
  const forecast = cols.find((c) => c.kind === 'forecast')?.lines ?? null;
  return {
    region: regionById(region), year: actual.year, population: pop?.population ?? null, over64: pop?.over64_share ?? null,
    actual: actual.lines, forecast, budget: cols.find((c) => c.kind === 'budget')?.lines ?? null,
    ytd: cols.find((c) => c.kind === 'ytd') ?? null,
    perCapita: (k, lines = actual.lines) => (pop && lines?.[k] != null ? lines[k]! / pop.population : null),
  };
}
export const regionsWithFinances = () => load().regions.filter((r) => financesOf(r.id));

/** Rows for the nationwide finance table and its CSV/JSON export. */
export function financeRows() {
  return regionsWithFinances().map((r) => {
    const s = financeSummary(r.id)!;
    const a = s.actual;
    return {
      region: r.id, name: r.short.fi, year: s.year, population: s.population,
      expenses: a.expenses ?? null, state_funding: a.state_funding ?? null, surplus: a.surplus ?? null,
      cumulative_surplus: a.cumulative_surplus ?? null, loans: a.loans ?? null,
      expenses_per_resident: s.perCapita('expenses'), surplus_per_resident: s.perCapita('surplus'),
      cumulative_per_resident: s.perCapita('cumulative_surplus'), loans_per_resident: s.perCapita('loans'),
      forecast_surplus: s.forecast?.surplus ?? null, budget_surplus: s.budget?.surplus ?? null,
      url: url(r.id, 'talous'),
    };
  });
}
