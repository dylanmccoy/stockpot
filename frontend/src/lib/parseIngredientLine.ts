// Display-only mirror of the backend single-line parser
// (`backend/app/services/ingredient_parse.py`, backend spec §2.3).
//
// The RecipeForm paste flow (frontend spec §7.1, §10.3) previews how the
// server WILL split a pasted line into quantity / unit / item / note before
// the rows are appended to the ingredient table. The server stays the source
// of truth: an untouched pasted row is POSTed as a bare string and re-parsed
// server-side. This mirror only shapes the preview and the initial editable
// cell values — it is deliberately not under the locked-oracle gate.

export interface ParsedIngredientLine {
  quantity: number | null;
  unit: string | null;
  item: string;
  note: string | null;
}

// Unicode vulgar fractions the backend recognises (`_VULGAR_FRACTIONS`).
const VULGAR_FRACTIONS: Record<string, number> = {
  "½": 0.5,
  "¼": 0.25,
  "¾": 0.75,
  "⅓": 1 / 3,
  "⅔": 2 / 3,
  "⅛": 0.125,
};

// Whitespace-tolerant "to taste" (matches the backend `_TO_TASTE_RE`).
// Non-global for detection (no `lastIndex` state); the `g` twin strips EVERY
// occurrence, like the backend's `re.sub`.
const TO_TASTE_RE = /\bto\s+taste\b/i;
const TO_TASTE_RE_ALL = /\bto\s+taste\b/gi;

// MASS + VOLUME + COUNT synonyms from `backend/app/units.py` `_UNIT_TABLE`.
const KNOWN_UNITS = new Set([
  "g",
  "gram",
  "kg",
  "mg",
  "oz",
  "ounce",
  "lb",
  "lbs",
  "pound",
  "ml",
  "l",
  "litre",
  "liter",
  "tsp",
  "teaspoon",
  "tbsp",
  "tablespoon",
  "cup",
  "fl-oz",
  "fl oz",
  "floz",
  "pint",
  "quart",
  "gallon",
  "unit",
  "each",
  "dozen",
  "pair",
]);

// Deliberately-opaque unit tokens (`backend/app/units.py` `OPAQUE_TOKENS`,
// minus "to taste" which is handled as a note above).
const OPAQUE_UNITS = new Set([
  "clove",
  "slice",
  "piece",
  "stick",
  "can",
  "package",
  "pkg",
  "jar",
  "bottle",
  "box",
  "bag",
  "head",
  "bulb",
  "bunch",
  "sprig",
  "pinch",
  "handful",
  "dash",
  "splash",
]);

const finitePos = (n: number): number | null =>
  Number.isFinite(n) && n > 0 ? n : null;

/** Light mirror of the backend `_singularize_token` — enough for unit matching
 *  in a preview ("cups" → "cup", "boxes" → "box"). */
function singularize(token: string): string {
  if (token.length > 3 && /(?:ses|xes|ches|shes)$/.test(token)) {
    return token.slice(0, -2);
  }
  if (token.length > 1 && token.endsWith("s") && !token.endsWith("ss")) {
    return token.slice(0, -1);
  }
  return token;
}

/** A known synonym or an opaque unit token, matched the way the backend's
 *  `_is_unit_word` does (lower-case, drop one trailing ".", singularize). */
function isUnitWord(candidate: string): boolean {
  const c = candidate.trim().toLowerCase().replace(/\.$/, "");
  if (KNOWN_UNITS.has(c) || OPAQUE_UNITS.has(c)) return true;
  const s = singularize(c);
  return KNOWN_UNITS.has(s) || OPAQUE_UNITS.has(s);
}

/** Positive finite float from an integer / decimal / `a/b` / `a b/c` / vulgar
 *  fraction, else null (mirrors the backend `_parse_number`). */
function parseNumber(raw: string): number | null {
  const s = raw.trim();
  if (!s) return null;

  if (s in VULGAR_FRACTIONS) return finitePos(VULGAR_FRACTIONS[s]);

  let m = /^(\d+(?:\.\d+)?)\s+(\d+)\/(\d+)$/.exec(s);
  if (m) {
    const [, whole, num, den] = m;
    if (Number(den) === 0) return null;
    return finitePos(Number(whole) + Number(num) / Number(den));
  }

  m = /^(\d+(?:\.\d+)?)\/(\d+(?:\.\d+)?)$/.exec(s);
  if (m) {
    const [, num, den] = m;
    if (Number(den) === 0) return null;
    return finitePos(Number(num) / Number(den));
  }

  if (/^\d+(?:\.\d+)?$/.test(s)) return finitePos(Number(s));

  return null;
}

// A leading number: mixed number, then simple fraction, then integer/decimal.
const LEADING_NUMBER =
  /^(?:\d+(?:\.\d+)?\s+\d+\/\d+|\d+(?:\.\d+)?\/\d+(?:\.\d+)?|\d+(?:\.\d+)?)/;

/**
 * Parse one already-split ingredient line the way the server will. Never
 * throws for non-blank input; `item` is always non-empty.
 */
export function parseIngredientLine(text: string): ParsedIngredientLine {
  // Fold Unicode decimal digits (e.g. fullwidth "１２") to ASCII so the number
  // paths match Python's Unicode-aware `\d` + `float`. `\p{Nd}` is decimal
  // digits only — vulgar fractions (`½`, category `\p{No}`) are untouched.
  let working = text
    .trim()
    .replace(/\p{Nd}/gu, (digit) => digit.normalize("NFKC"));
  const original = working;

  let quantity: number | null = null;
  let unit: string | null = null;
  let note: string | null = null;

  // Step 1 — "to taste" anywhere becomes the note and nulls the quantity.
  let toTaste = false;
  if (TO_TASTE_RE.test(working)) {
    toTaste = true;
    note = "to taste";
    working = working
      .replace(TO_TASTE_RE_ALL, "")
      .split(/\s+/)
      .filter(Boolean)
      .join(" ");
  }

  // Step 2 — the first parenthetical becomes the note (unless we already have one).
  const paren = /\(([^)]+)\)/.exec(working);
  if (paren && note === null) {
    note = paren[1].trim();
    working = (
      working.slice(0, paren.index) +
      " " +
      working.slice(paren.index + paren[0].length)
    )
      .split(/\s+/)
      .filter(Boolean)
      .join(" ");
  }

  // Step 3 — leading quantity: a vulgar-fraction char first, then a number run.
  if (working && working[0] in VULGAR_FRACTIONS) {
    const q = parseNumber(working[0]);
    if (q !== null) {
      quantity = q;
      working = working.slice(1).trim();
    }
  }
  if (quantity === null && working) {
    const m = LEADING_NUMBER.exec(working);
    if (m) {
      const q = parseNumber(m[0]);
      if (q !== null) {
        quantity = q;
        working = working.slice(m[0].length).trim();
      }
    }
  }

  // Step 4 — unit: the 1–2 words after the quantity, if a known/opaque token.
  //          Stored as it appeared (lower-cased, one trailing "." dropped).
  if (quantity !== null && working) {
    const tokens = working.split(/\s+/);
    let matched: string | null = null;
    let consumed = 0;
    if (tokens.length >= 2 && isUnitWord(`${tokens[0]} ${tokens[1]}`)) {
      matched = `${tokens[0]} ${tokens[1]}`;
      consumed = 2;
    } else if (tokens.length >= 1 && isUnitWord(tokens[0])) {
      matched = tokens[0];
      consumed = 1;
    }
    if (matched !== null) {
      unit = matched.toLowerCase().replace(/\.$/, "");
      working = tokens.slice(consumed).join(" ").trim();
    }
  }

  // Steps 5–6 — the rest is the item; fall back to the original line.
  const item = working.trim() || original.trim() || "ingredient";

  // Step 7 — "to taste" always wins over a parsed quantity.
  if (toTaste) quantity = null;

  return { quantity, unit, item, note };
}
