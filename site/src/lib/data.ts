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

// ------------------------------------------------------------------ people
export interface PersonStats {
  slug: string; name: string; roles: Set<string>; present: number; absent: number;
  bodies: Map<string, { present: number; absent: number }>; meetings: { m: Meeting; group: string; role: string }[];
  member: boolean;
}

export function slugify(s: string): string {
  return s.toLowerCase().replace(/[äå]/g, 'a').replace(/ö/g, 'o').normalize('NFKD')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

export function peopleOf(region: string): PersonStats[] {
  const people = new Map<string, PersonStats>();
  for (const m of meetingsOf(region)) {
    if (m.stage === 'agenda') continue;
    for (const p of m.participants) {
      const slug = slugify(p.name);
      if (!slug) continue;
      let s = people.get(slug);
      if (!s) {
        s = { slug, name: p.name, roles: new Set(), present: 0, absent: 0, bodies: new Map(), meetings: [], member: false };
        people.set(slug, s);
      }
      const b = s.bodies.get(m.body_id) || { present: 0, absent: 0 };
      if (p.group === 'absent') { s.absent++; b.absent++; } else { s.present++; b.present++; }
      if (p.group !== 'other') s.member = true;
      if (p.role) s.roles.add(p.role);
      s.bodies.set(m.body_id, b);
      s.meetings.push({ m, group: p.group, role: p.role });
    }
  }
  return [...people.values()].sort((a, b) => a.name.localeCompare(b.name, 'fi'));
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
