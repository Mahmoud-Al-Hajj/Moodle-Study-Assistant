import { describe, expect, it } from "vitest";
import type { CourseItem, CourseSection } from "../../api/client";
import {
  countBy,
  filterSections,
  matches,
  normalize,
  parseFilters,
  toParams,
  toggle,
} from "./filters";

const item = (over: Partial<CourseItem>): CourseItem => ({
  id: "cm:1",
  title: "Lecture",
  type: "resource",
  module: "resource",
  status: "downloaded",
  note: "",
  url: "",
  target_url: "",
  section_name: "Week 1",
  files: [],
  ...over,
});

const none = { q: "", types: [], statuses: [] };

describe("filters", () => {
  it("normalizes case and accents", () => {
    expect(normalize("Résumé ÉCOLE")).toBe("resume ecole");
  });

  it("matches every word of the search in the title, plus type and status", () => {
    const it1 = item({ title: "Adam Smith: The Wealth of Nations" });
    expect(matches(it1, { ...none, q: "wealth smith" })).toBe(true);
    expect(matches(it1, { ...none, q: "wealth marx" })).toBe(false);
    expect(matches(it1, { ...none, types: ["url"] })).toBe(false);
    expect(matches(it1, { ...none, statuses: ["downloaded", "failed"] })).toBe(
      true,
    );
  });

  it("round-trips through the URL", () => {
    const f = { q: "smith", types: ["resource", "url"], statuses: ["failed"] };
    expect(parseFilters(toParams(f))).toEqual(f);
    expect(toParams(none).toString()).toBe("");
  });

  it("drops sections without matches only while filtering", () => {
    const sections: CourseSection[] = [
      { number: 0, name: "General", items: [item({ title: "Syllabus" })] },
      { number: 1, name: "Week 1", items: [item({ title: "Slides" })] },
      { number: 2, name: "Empty", items: [] },
    ];
    expect(filterSections(sections, none)).toHaveLength(3);
    const found = filterSections(sections, { ...none, q: "slides" });
    expect(found.map((s) => s.section.name)).toEqual(["Week 1"]);
  });

  it("counts values in first-seen order and toggles chips", () => {
    const items = [
      item({ type: "url" }),
      item({ type: "resource" }),
      item({ type: "url" }),
    ];
    expect(countBy(items, "type")).toEqual([
      ["url", 2],
      ["resource", 1],
    ]);
    expect(toggle(["a"], "b")).toEqual(["a", "b"]);
    expect(toggle(["a", "b"], "a")).toEqual(["b"]);
  });
});
