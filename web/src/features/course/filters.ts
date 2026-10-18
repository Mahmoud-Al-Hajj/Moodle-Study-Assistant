import type { CourseItem, CourseSection } from "../../api/client";

/** What the filter bar selects; kept in the URL (?q=&type=&status=) so a reload keeps it. */
export type Filters = { q: string; types: string[]; statuses: string[] };

export const TYPE_LABELS: Record<string, string> = {
  resource: "File",
  folder: "Folder",
  page: "Page",
  url: "Link",
  assign: "Assignment",
  other: "Other",
};

export const typeLabel = (type: string) => TYPE_LABELS[type] ?? type;

export function parseFilters(params: URLSearchParams): Filters {
  return {
    q: params.get("q") ?? "",
    types: params.getAll("type"),
    statuses: params.getAll("status"),
  };
}

export function toParams(f: Filters): URLSearchParams {
  const params = new URLSearchParams();
  if (f.q) params.set("q", f.q);
  f.types.forEach((t) => params.append("type", t));
  f.statuses.forEach((s) => params.append("status", s));
  return params;
}

export const isFiltering = (f: Filters) =>
  f.q.trim() !== "" || f.types.length > 0 || f.statuses.length > 0;

/** Lower case without accents, so "resume" finds "Résumé". */
export const normalize = (s: string) =>
  s.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase();

export function matches(item: CourseItem, f: Filters): boolean {
  if (f.types.length && !f.types.includes(item.type)) return false;
  if (f.statuses.length && !f.statuses.includes(item.status)) return false;
  const words = normalize(f.q).split(/\s+/).filter(Boolean);
  const title = normalize(item.title);
  return words.every((w) => title.includes(w));
}

/** Each section with its matching items; sections with no match are left out. */
export function filterSections(sections: CourseSection[], f: Filters) {
  return sections
    .map((section) => ({
      section,
      items: section.items.filter((it) => matches(it, f)),
    }))
    .filter((s) => s.items.length > 0 || !isFiltering(f));
}

/** How many items have each value of `key`, in first-seen order. */
export function countBy(
  items: CourseItem[],
  key: "type" | "status",
): [string, number][] {
  const counts = new Map<string, number>();
  for (const it of items) counts.set(it[key], (counts.get(it[key]) ?? 0) + 1);
  return [...counts];
}

/** Toggle one value in a list (for the filter chips). */
export const toggle = (list: string[], value: string) =>
  list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
