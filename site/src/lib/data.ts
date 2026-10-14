// Reads the scraped JSON (the `data` branch, checked out next to the site) at build time.
// DATA_DIR defaults to ../data and falls back to ./sample-data for local development.
import fs from 'node:fs';
import path from 'node:path';

export type Lang = 'fi' | 'sv' | 'en';
export type Bilingual = Partial<Record<Lang, string>>;

export interface Vote { counts: Record<string, number>; context: string; provisional: boolean }
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
  return cache;
}

export const regionById = (id: string) => load().regions.find((r) => r.id === id)!;
export const meetingsOf = (region: string, body?: string) =>
  load().meetings.filter((m) => m.region === region && (!body || m.body_id === body));
export const bodiesOf = (region: string) => {
  // Only bodies that have at least one meeting in our archive.
  const withMeetings = new Set(meetingsOf(region).map((m) => m.body_id));
  return (load().bodies.get(region) || []).filter((b) => withMeetings.has(b.id));
};
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

export function votesOf(region: string) {
  const out: { m: Meeting; i: number; v: Vote }[] = [];
  for (const m of meetingsOf(region)) m.items.forEach((it, i) => it.votes.forEach((v) => out.push({ m, i, v })));
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
    url: meetingUrl(m), source: m.source_url,
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
          tyhja: v.counts.tyhja ?? null, poissa: v.counts.poissa ?? null, url: itemUrl(m, i), source: it.source_url,
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
