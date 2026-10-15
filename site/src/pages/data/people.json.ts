// Every councillor and deputy elected in 2025, for the /valtuutetut/ table and for download.
import { peopleRows } from '../../lib/data';

export function GET() {
  return new Response(JSON.stringify(peopleRows()), { headers: { 'content-type': 'application/json' } });
}
