// Paste-block splitter — spec §7.1 (D2 / R-9). Runs entirely client-side; the
// backend does no newline splitting, so a bug here silently garbles every
// pasted recipe. Locked oracle: parseIngredients.oracle.test.ts.

// A leading list marker: a bullet (`- `, `* `, `• `) or an ordinal (`1.`, `2)`).
const LEADING_MARKER = /^(?:[-*•]\s+|\d+[.)]\s+)/;

// A parseable leading quantity: integer / decimal / `a/b` / `a b/c` / a unicode
// vulgar fraction (optionally `<int> ` before it). Anchored at the line start.
const LEADING_QUANTITY =
  /^(?:\d+(?:\.\d+)?(?:\s+\d+\/\d+)?|\d+\/\d+|\d*\s*[¼-¾⅐-⅞])/;

function isSectionHeader(line: string): boolean {
  return line.endsWith(":") && !LEADING_QUANTITY.test(line);
}

export function parseIngredients(block: string): string[] {
  return block
    .split("\n")
    .map((line) => line.trim())
    .filter((line) => line.length > 0)
    .map((line) => line.replace(LEADING_MARKER, "").trimStart())
    .filter((line) => !isSectionHeader(line));
}
