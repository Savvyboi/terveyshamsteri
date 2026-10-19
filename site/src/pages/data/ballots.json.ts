// How each named person voted in each vote where the minutes list the voters.
import { ballotRows } from '../../lib/data';

export function GET() {
  return new Response(JSON.stringify(ballotRows()), { headers: { 'content-type': 'application/json' } });
}
