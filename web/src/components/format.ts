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

/** "1.2 MB", "340 KB"... */
export function formatBytes(bytes: number | null | undefined): string {
  if (bytes === null || bytes === undefined) return "";
  const units = ["bytes", "KB", "MB", "GB"];
  let value = bytes;
  let unit = 0;
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024;
    unit += 1;
  }
  return `${unit === 0 ? value : value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`;
}
