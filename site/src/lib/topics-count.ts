import { counted, load } from './data';
import { TOPICS, topicsOf } from './topics';

/** How many items (not counting the other language's copies) each topic has, largest first. */
export function topicCounts() {
  const n = new Map<string, number>();
  for (const m of load().meetings) {
    if (!counted(m)) continue;
    for (const it of m.items) for (const id of topicsOf(it.title)) n.set(id, (n.get(id) ?? 0) + 1);
  }
  return TOPICS.map((topic) => ({ topic, n: n.get(topic.id) ?? 0 })).filter((x) => x.n > 0).sort((a, b) => b.n - a.n);
}
