// New items on one topic from every county, as RSS (/aiheet/{topic}/rss.xml). Ported from Kotihiiri.
import type { APIContext } from 'astro';
import { regionById, url } from '../../../lib/data';
import { rss } from '../../../lib/rss';
import { TOPICS, type Topic } from '../../../lib/topics';
import { topicItems } from '../../../lib/topics-count';

export function getStaticPaths() {
  return TOPICS.map((topic) => ({ params: { topic: topic.id }, props: { topic } }));
}

export function GET({ site, props }: APIContext) {
  const topic = (props as { topic: Topic }).topic;
  return rss({
    site: site!, self: `${url('aiheet', topic.id)}rss.xml`, link: url('aiheet', topic.id), limit: 100,
    title: `Terveyshamsteri – ${topic.label.fi}`,
    description: `${topic.label.fi}: uusimmat esityslistat ja päätökset kaikilta hyvinvointialueilta.`,
    entries: topicItems(topic.id), regionName: (id) => regionById(id).short.fi ?? id,
  });
}
