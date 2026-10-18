import { describe, expect, it } from "vitest";
import { extractedBody } from "./extracted";

describe("extractedBody", () => {
  it("drops the title, the metadata table, flag lines and bold markers", () => {
    const md = [
      "# Syllabus",
      "",
      "| | |",
      "|---|---|",
      "| Section | 00 General |",
      "| Words | 1,724 |",
      "",
      "> Word files have no fixed pages: `[¶N]` marks paragraph N.",
      "",
      "**HAIGAZIAN** **UNIVERSITY** [¶1]",
      "",
      "## Slide 2: Think | about it",
      "- the **meaning** of life",
    ].join("\r\n");
    expect(extractedBody(md)).toBe(
      [
        "HAIGAZIAN UNIVERSITY [¶1]",
        "",
        "## Slide 2: Think | about it",
        "- the meaning of life",
      ].join("\n"),
    );
  });

  it("leaves text without a header alone", () => {
    expect(extractedBody("Just text\n| a table later |")).toBe(
      "Just text\n| a table later |",
    );
  });
});
