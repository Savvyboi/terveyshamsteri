// Every extracted vote as one JSON file, for the /aanestykset/ table and for download.
import { voteRows } from '../../lib/data';

export function GET() {
  return new Response(JSON.stringify(voteRows()), { headers: { 'content-type': 'application/json' } });
}
