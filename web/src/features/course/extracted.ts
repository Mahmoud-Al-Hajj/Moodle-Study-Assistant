/**
 * Readable plain text from one of Stage 4's per-file .md files (data/text/...): drops the
 * header (`# title`, the Section/Source/... table, `> flag` lines) and the `**bold**` markers.
 * Headings, bullets and [¶N] markers stay. Stage D's Reader renders the Markdown properly.
 */
export function extractedBody(md: string): string {
  const lines = md.replace(/\r\n/g, "\n").split("\n");
  let i = 0;
  if (lines[0]?.startsWith("# ")) i = 1;
  while (
    i < lines.length &&
    (lines[i].trim() === "" ||
      lines[i].startsWith("|") ||
      lines[i].startsWith("> "))
  )
    i += 1;
  return lines
    .slice(i)
    .join("\n")
    .replace(/\*\*(.+?)\*\*/g, "$1");
}
