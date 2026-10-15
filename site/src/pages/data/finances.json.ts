import { financeRows } from '../../lib/data';

export function GET() {
  return new Response(JSON.stringify(financeRows()), { headers: { 'Content-Type': 'application/json' } });
}
