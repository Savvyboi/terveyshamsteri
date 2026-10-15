import type { APIContext } from 'astro';
import { bodiesOf, load, meetingsOf, url, type Body, type Region } from '../../../lib/data';
import { rss } from '../../../lib/rss';

export function getStaticPaths() {
  return load().regions.flatMap((r) => bodiesOf(r.id).map((b) => ({ params: { region: r.id, body: b.id }, props: { r, b } })));
}

export function GET({ site, props }: APIContext) {
  const { r, b } = props as { r: Region; b: Body };
  return rss({
    site: site!, self: `${url(r.id, b.id)}rss.xml`, link: url(r.id, b.id), limit: 50,
    title: `${b.name} – ${r.short.fi} – Terveyshamsteri`,
    description: `${b.name} (${r.name.fi}): uusimmat esityslistat ja päätökset.`,
    meetings: meetingsOf(r.id, b.id), regionName: () => r.short.fi ?? r.id,
  });
}
