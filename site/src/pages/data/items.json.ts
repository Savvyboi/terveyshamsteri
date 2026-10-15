// Every agenda item that has a topic, for the /aiheet/ table and for download.
import { itemRows } from '../../lib/data';

export function GET() {
  return new Response(JSON.stringify(itemRows()), { headers: { 'content-type': 'application/json' } });
}
