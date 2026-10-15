import type { APIContext } from 'astro';
import { load, meetingsOf, url, type Region } from '../../lib/data';
import { rss } from '../../lib/rss';

export function getStaticPaths() {
  return load().regions.filter((r) => meetingsOf(r.id).length).map((r) => ({ params: { region: r.id }, props: { r } }));
}

export function GET({ site, props }: APIContext) {
  const r = (props as { r: Region }).r;
  return rss({
    site: site!, self: `${url(r.id)}rss.xml`, link: url(r.id), limit: 100,
    title: `${r.short.fi} – Terveyshamsteri`,
    description: `${r.name.fi}: uusimmat esityslistat ja päätökset.`,
    meetings: meetingsOf(r.id), regionName: () => r.short.fi ?? r.id,
  });
}
