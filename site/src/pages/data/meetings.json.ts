// Every meeting as one JSON file: the /kokoukset/ table filters it in the browser,
// and anyone can download it.
import { meetingRows } from '../../lib/data';

export function GET() {
  return new Response(JSON.stringify(meetingRows()), { headers: { 'content-type': 'application/json' } });
}
