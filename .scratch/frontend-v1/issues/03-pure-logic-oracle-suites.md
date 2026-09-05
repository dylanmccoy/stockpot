# 03: Pure logic + locked oracle suites

**What to build:** The three client-owned pure functions that have no server counterpart, each locked to an oracle table authored as tests *before* the implementation exists. After this ticket, pasted ingredient blocks split correctly, quantities render for humans, and API errors classify into the shape the UI routes on.

**Blocked by:** 01.

**Status:** done

- [ ] `parseIngredients`: splits on newline, trims, drops blank lines, strips one leading bullet/number marker, drops section-header lines (trailing `:` with no parseable leading quantity), no soft-wrap rejoin. Passes all 10 oracle rows (spec §7.1).
- [ ] `format`: `formatQuantity(value, unit)` — fraction-prefer (`⅛ ¼ ⅓ ½ ⅔ ¾`, incl. integer+fraction) when `value < 10` and within 2% of a common fraction; counts snap to integer within 1%; canonical bulk units (`g`, `ml`) always decimal; otherwise 3 significant figures, trailing zeros trimmed, no thousands separators; `null` → `""`. `formatDateTime` per spec. Passes all 15 oracle rows (spec §7.2).
- [ ] `apiError`: `parseApiError(status, body)` → `ApiError`; helpers `isFieldError`, `fieldName` (last `loc` segment); `useFormErrors` hook splits field-level (`ValidationIssue[]`) from form-level (string `detail`). Passes all 8 oracle rows (spec §7.3).
- [ ] For each module the oracle table is translated to black-box tests and accepted **before** implementation code is written (R-7 analogue gate); the implementation pass may add cases but not change an accepted expected value. A wrong oracle is corrected by editing spec + test together with the reason recorded in `decisions.md`.

**Refs:** `docs/frontend/spec.md` §7; plan "Contract-test gate".
