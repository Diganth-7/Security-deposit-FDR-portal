const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 });

export function formatMoney(value: unknown): string {
  const n = typeof value === 'number' ? value : Number(value);
  if (value === null || value === undefined || value === '' || Number.isNaN(n)) return '-';
  return inr.format(n);
}

/** Formats a plain ISO date (yyyy-mm-dd) without any timezone conversion. */
export function formatDate(iso?: string | null): string {
  if (!iso) return '-';
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(iso);
  if (!m) return iso;
  return `${m[3]} ${MONTHS[Number(m[2]) - 1] ?? m[2]} ${m[1]}`;
}

/** Formats a server timestamp. Naive timestamps are treated as UTC. */
export function formatDateTime(ts?: string | null): string {
  if (!ts) return '-';
  const hasTz = /(Z|[+-]\d{2}:?\d{2})$/.test(ts);
  const d = new Date(hasTz ? ts : `${ts}Z`);
  if (Number.isNaN(d.getTime())) return ts;
  return d.toLocaleString('en-IN', { dateStyle: 'medium', timeStyle: 'short' });
}

export function humanize(value: string | null | undefined): string {
  if (!value) return '-';
  return value
    .toLowerCase()
    .split('_')
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

/** True when the string is a positive amount with at most two decimals. */
export function isValidAmount(s: string): boolean {
  return /^\d+(\.\d{1,2})?$/.test(s.trim()) && Number(s) > 0;
}

export function saveBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function errMsg(e: unknown, fallback = 'Something went wrong.'): string {
  return e instanceof Error && e.message ? e.message : fallback;
}
