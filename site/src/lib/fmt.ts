// Number formatting for money. Finnish formatting is used in every language: it is what the
// source data and the minutes use, and its spaces and comma read correctly in Swedish too.
export const num = (n: number, d = 0) => n.toLocaleString('fi-FI', { minimumFractionDigits: d, maximumFractionDigits: d });
/** 607 361 486 -> "607,4 M€" */
export const meur = (n: number | null | undefined) => (n == null ? '–' : `${num(n / 1e6, Math.abs(n) >= 1e8 ? 0 : 1)} M€`);
/** 4120.4 -> "4 120 €" */
export const eur = (n: number | null | undefined) => (n == null ? '–' : `${num(Math.round(n))} €`);
/** Signed: "+12,3 M€", "−4,1 M€". */
export const smeur = (n: number | null | undefined) => (n == null ? '–' : (n > 0 ? '+' : '') + meur(n));
export const seur = (n: number | null | undefined) => (n == null ? '–' : (n > 0 ? '+' : '') + eur(n));
export const tone = (n: number | null | undefined) => (n == null ? '' : n < 0 ? 'neg' : n > 0 ? 'pos' : '');
