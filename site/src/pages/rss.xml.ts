import type { APIContext } from 'astro';
import { load, regionById, url } from '../lib/data';
import { rss } from '../lib/rss';

export function GET({ site }: APIContext) {
  return rss({
    site: site!, self: `${url()}rss.xml`, link: url('kokoukset'), limit: 200,
    title: 'Terveyshamsteri – uusimmat asiat',
    description: 'Hyvinvointialueiden uusimmat esityslistat ja päätökset.',
    meetings: load().meetings, regionName: (id) => regionById(id).short.fi ?? id,
  });
}
