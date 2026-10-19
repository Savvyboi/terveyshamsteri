// Every council initiative and its steps, for the /aloitteet/ table and for download.
import { initiativeRows } from '../../lib/data';

export function GET() {
  return new Response(JSON.stringify(initiativeRows()), { headers: { 'content-type': 'application/json' } });
}
