// RSS 2.0 feeds of the newest agenda and minutes items, for following a county or a body
// in a feed reader. Items are ordered by meeting date, which is also their pubDate, so a
// long backfill of old meetings does not push them to the top of anyone's reader.
import { itemUrl, type Meeting } from './data';

const esc = (s: string) => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
// XML 1.0 forbids most control characters, which do turn up in text extracted from PDFs.
const clean = (s: string) => s.replace(/[\u0000-\u0008\u000b\u000c\u000e-\u001f]/g, '');

function snippet(s: string | null, max = 600): string {
  const t = (s ?? '').replace(/\s+/g, ' ').trim();
  return t.length > max ? `${t.slice(0, max).replace(/\s\S*$/, '')} …` : t;
}

/** The newest `limit` items of these meetings (newest first, as load() sorts them). */
export function feedItems(meetings: Meeting[], limit: number) {
  const out: { m: Meeting; i: number }[] = [];
  for (const m of meetings) {
    for (let i = 0; i < m.items.length && out.length < limit; i++) out.push({ m, i });
    if (out.length >= limit) break;
  }
  return out;
}

export function rss(opts: { site: URL; self: string; title: string; link: string; description: string;
  meetings?: Meeting[]; entries?: { m: Meeting; i: number }[]; limit: number; regionName: (id: string) => string }): Response {
  const abs = (p: string) => new URL(p, opts.site).href;
  const entries = opts.entries ? opts.entries.slice(0, opts.limit) : feedItems(opts.meetings ?? [], opts.limit);
  const items = entries.map(({ m, i }) => {
    const it = m.items[i];
    const agenda = m.stage === 'agenda';
    const link = abs(itemUrl(m, i));
    const title = `${agenda ? 'Esityslista: ' : ''}${it.number ? `§ ${it.number} ` : ''}${it.title}`;
    const body = agenda ? it.proposal : it.decision ?? it.proposal;
    const desc = `${m.body_name}, ${opts.regionName(m.region)} ${m.date.split('-').reverse().map(Number).join('.')}` +
      (body ? `. ${agenda ? 'Ehdotus' : 'Päätös'}: ${snippet(body)}` : '');
    return `<item><title>${esc(clean(title))}</title><link>${link}</link>` +
      // A new guid when the minutes replace the agenda, so readers show the decision as new.
      `<guid isPermaLink="false">${esc(`${link}#${m.stage}`)}</guid>` +
      `<pubDate>${new Date(`${m.date}T12:00:00Z`).toUTCString()}</pubDate>` +
      `<category>${esc(m.body_name)}</category><description>${esc(clean(desc))}</description></item>`;
  });
  const xml = `<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:atom="http://www.w3.org/2005/Atom"><channel>
<title>${esc(opts.title)}</title><link>${abs(opts.link)}</link><description>${esc(opts.description)}</description>
<language>fi</language><atom:link href="${abs(opts.self)}" rel="self" type="application/rss+xml"/>
${items.join('\n')}
</channel></rss>
`;
  return new Response(xml, { headers: { 'Content-Type': 'application/rss+xml; charset=utf-8' } });
}
