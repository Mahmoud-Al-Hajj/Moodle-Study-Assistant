const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
const STEPS: [Intl.RelativeTimeFormatUnit, number][] = [
  ["second", 60],
  ["minute", 60],
  ["hour", 24],
  ["day", 7],
  ["week", 4.35],
  ["month", 12],
  ["year", Infinity],
];

/** "5 minutes ago", "yesterday"... `now` is injectable for tests. */
export function timeAgo(
  iso: string | null | undefined,
  now: number = Date.now(),
): string {
  if (!iso) return "never";
  let value = (new Date(iso).getTime() - now) / 1000;
  for (const [unit, size] of STEPS) {
    if (Math.abs(value) < size) return rtf.format(Math.round(value), unit);
    value /= size;
  }
  return "";
}

export const fullDate = (iso: string) => new Date(iso).toLocaleString();
