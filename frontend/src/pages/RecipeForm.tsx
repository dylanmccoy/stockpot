import {
  useMemo,
  useRef,
  useState,
  type FormEvent,
  type KeyboardEvent,
} from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { recipesApi } from "../api/recipes";
import type {
  RecipeCreate,
  RecipeIngredientElement,
  RecipeIngredientIn,
  RecipeRead,
} from "../types";
import {
  Button,
  Dialog,
  Field,
  Input,
  Textarea,
  useToast,
} from "../components";
import {
  GENERIC_ERROR_MESSAGE,
  hasInlineFormError,
  useFormErrors,
} from "../lib/apiError";
import { parseIngredients } from "../lib/parseIngredients";
import {
  parseIngredientLine,
  type ParsedIngredientLine,
} from "../lib/parseIngredientLine";
import styles from "./RecipeForm.module.css";

// ── Draft model ────────────────────────────────────────────────────────────
// The form holds everything as strings; `buildRecipeCreate` is the single
// place drafts turn into the POST body (spec §10.3). Row/step identity is a
// local uid — never the server row id (R-16) — so reorder/remove keep React
// keys stable.

let seq = 0;
const uid = () => `r${++seq}`;

export interface IngredientDraft {
  uid: string;
  quantity: string;
  unit: string;
  item: string;
  note: string;
  /** How the row entered the table. A `paste` row that is still `pristine`
   *  serializes as a bare string element — the server re-parses it and keeps
   *  `raw_text`. Any edit (via `setRow`) flips `pristine` off, and the row
   *  then serializes as an object like a hand-entered one (spec §10.3). */
  origin: "manual" | "paste";
  pristine: boolean;
  /** The exact pasted line, sent verbatim as the string element. `""` for
   *  hand-entered rows. */
  raw: string;
}

export interface StepDraft {
  uid: string;
  text: string;
}

export interface RecipeFormState {
  title: string;
  cuisine: string;
  servings: string;
  prepTime: string;
  cookTime: string;
  sourceUrl: string;
  notes: string;
  tags: string[];
  steps: StepDraft[];
  ingredients: IngredientDraft[];
}

const blankIngredient = (): IngredientDraft => ({
  uid: uid(),
  quantity: "",
  unit: "",
  item: "",
  note: "",
  origin: "manual",
  pristine: false,
  raw: "",
});

/** A pasted string element is truncated to 200 chars server-side before it is
 *  parsed (spec §5) — Python slices by code point, so mirror that with
 *  `Array.from` rather than `String.slice` (UTF-16 units). */
const PASTED_LINE_MAX = 200;
const truncateLine = (raw: string): string =>
  Array.from(raw).slice(0, PASTED_LINE_MAX).join("");

interface PastePreviewRow extends ParsedIngredientLine {
  /** the exact (already truncated) line the server will keep as `raw_text` */
  line: string;
}

/** A previewed paste row → a `pristine` ingredient row. Its cells are seeded
 *  from the same mirror parse the preview showed (spec §7.1, §10.3); while
 *  pristine it serializes back to `line`, not an object. */
function pastedIngredient(row: PastePreviewRow): IngredientDraft {
  return {
    uid: uid(),
    quantity: quantityToInput(row.quantity),
    unit: row.unit ?? "",
    item: row.item,
    note: row.note ?? "",
    origin: "paste",
    pristine: true,
    raw: row.line,
  };
}

const blankStep = (): StepDraft => ({ uid: uid(), text: "" });

function emptyState(): RecipeFormState {
  return {
    title: "",
    cuisine: "",
    servings: "",
    prepTime: "",
    cookTime: "",
    sourceUrl: "",
    notes: "",
    tags: [],
    steps: [],
    ingredients: [blankIngredient()],
  };
}

// ── Pure serialization ─────────────────────────────────────────────────────

function numOrNull(raw: string): number | null {
  const t = raw.trim();
  if (!t) return null;
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

/** A parsed preview quantity → the string that seeds the editable cell.
 *  `null` (to taste / unparsed) → blank; otherwise a short decimal. The
 *  preview shows this same string, so the cell can't disagree with it. */
function quantityToInput(value: number | null): string {
  if (value === null) return "";
  return String(Number(value.toPrecision(6)));
}

/** "1 row" / "N rows" — shared by the paste dialog's button and caption. */
const rowCount = (n: number): string => `${n} ${n === 1 ? "row" : "rows"}`;

/** A row carries content once any cell is non-blank; fully blank rows never
 *  reach the server. */
export function ingredientHasContent(row: IngredientDraft): boolean {
  return Boolean(
    row.quantity.trim() ||
    row.unit.trim() ||
    row.item.trim() ||
    row.note.trim(),
  );
}

/** The rows that will be POSTed, in order — also the index space the server's
 *  `loc: ["body","ingredients",N,…]` errors point into. */
export function ingredientRowsToSubmit(
  state: RecipeFormState,
): IngredientDraft[] {
  return state.ingredients.filter(ingredientHasContent);
}

function toIngredientElement(row: IngredientDraft): RecipeIngredientElement {
  // An untouched pasted row goes over as the raw line (server keeps
  // `raw_text` and re-parses); anything hand-entered or edited is an object.
  if (row.origin === "paste" && row.pristine) return row.raw;

  const el: RecipeIngredientIn = { item: row.item.trim() };
  const q = row.quantity.trim();
  if (q) el.quantity = Number(q); // blank ⇒ omitted ⇒ to-taste (spec §10.3)
  const u = row.unit.trim();
  if (u) el.unit = u;
  const n = row.note.trim();
  if (n) el.note = n;
  return el;
}

/** Draft → `RecipeCreate`. Hand-entered / edited rows serialize as object
 *  elements; untouched pasted rows as bare strings (`toIngredientElement`). */
export function buildRecipeCreate(state: RecipeFormState): RecipeCreate {
  return {
    title: state.title.trim(),
    notes: state.notes,
    cuisine: state.cuisine.trim() || null,
    source_url: state.sourceUrl.trim() || null,
    prep_time: numOrNull(state.prepTime),
    cook_time: numOrNull(state.cookTime),
    servings: numOrNull(state.servings),
    tags: state.tags,
    steps: state.steps.map((s) => s.text.trim()).filter(Boolean),
    ingredients: ingredientRowsToSubmit(state).map(toIngredientElement),
  };
}

/** `source_url` is stored verbatim (R-14); this only decides whether to offer
 *  an "open link" affordance. */
export function asOpenableUrl(raw: string): string | null {
  const t = raw.trim();
  if (!t) return null;
  try {
    const url = new URL(t);
    return url.protocol === "http:" || url.protocol === "https:"
      ? url.href
      : null;
  } catch {
    return null;
  }
}

// ── Small array helpers (reorder / remove, keyed by uid) ───────────────────

function move<T>(list: T[], index: number, delta: number): T[] {
  const target = index + delta;
  if (target < 0 || target >= list.length) return list;
  const copy = [...list];
  [copy[index], copy[target]] = [copy[target], copy[index]];
  return copy;
}

// ── Edit placeholder ──────────────────────────────────────────────────────
// Pre-fill + PUT full-replace is ticket 06c; the route stays live so links
// don't 404.

function EditPlaceholder() {
  return <h1>Edit recipe</h1>;
}

// ── Create form ──────────────────────────────────────────────────────────

interface ClientErrors {
  title?: string;
  /** keyed by ingredient row uid */
  rows: Record<string, string>;
}

function CreateForm() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [state, setState] = useState<RecipeFormState>(emptyState);
  const [tagDraft, setTagDraft] = useState("");
  const [clientErrors, setClientErrors] = useState<ClientErrors>({ rows: {} });

  // submitted row order at the moment of the last POST — maps a server
  // `ingredients[N]` error back to the row that produced it.
  const submittedUidsRef = useRef<string[]>([]);

  const mutation = useMutation({
    mutationFn: (body: RecipeCreate) => recipesApi.create(body),
    onSuccess: (recipe: RecipeRead) => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate(`/recipes/${recipe.id}`);
    },
    onError: (error) => {
      if (!hasInlineFormError(error)) {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    },
  });

  const { fieldErrors, formError } = useFormErrors(mutation.error);

  const patch = (next: Partial<RecipeFormState>) =>
    setState((s) => ({ ...s, ...next }));

  // ── field-error lookup (server issues win; client guards fill the gap) ──
  const titleError = fieldErrors["title"] ?? clientErrors.title;

  function rowError(rowUid: string, field: keyof RecipeIngredientIn) {
    const idx = submittedUidsRef.current.indexOf(rowUid);
    const serverKey = idx >= 0 ? `ingredients.${idx}.${field}` : null;
    if (serverKey && fieldErrors[serverKey]) return fieldErrors[serverKey];
    if (field === "item") return clientErrors.rows[rowUid];
    return undefined;
  }

  // ── ingredient rows ──
  // Any cell edit un-pristines the row: an edited paste row now serializes as
  // an object, not the raw string (spec §10.3).
  const setRow = (rowUid: string, next: Partial<IngredientDraft>) =>
    setState((s) => ({
      ...s,
      ingredients: s.ingredients.map((r) =>
        r.uid === rowUid ? { ...r, ...next, pristine: false } : r,
      ),
    }));
  const addRow = () =>
    patch({ ingredients: [...state.ingredients, blankIngredient()] });
  const removeRow = (rowUid: string) =>
    setState((s) => {
      const kept = s.ingredients.filter((r) => r.uid !== rowUid);
      return { ...s, ingredients: kept.length ? kept : [blankIngredient()] };
    });
  const moveRow = (index: number, delta: number) =>
    patch({ ingredients: move(state.ingredients, index, delta) });

  // ── paste ingredients (spec §7.1, §10.3) ──
  // `parseIngredients` splits the block; `parseIngredientLine` previews the
  // per-line parse the server will do. Confirm appends the rows; each starts
  // `pristine` so an untouched one is POSTed as its raw string.
  const [pasteOpen, setPasteOpen] = useState(false);
  const [pasteText, setPasteText] = useState("");

  const pastePreview = useMemo<PastePreviewRow[]>(
    () =>
      parseIngredients(pasteText).map((raw) => {
        const line = truncateLine(raw);
        return { line, ...parseIngredientLine(line) };
      }),
    [pasteText],
  );

  const closePaste = () => {
    setPasteOpen(false);
    setPasteText("");
  };
  const confirmPaste = () => {
    if (pastePreview.length === 0) return;
    const rows = pastePreview.map(pastedIngredient);
    setState((s) => ({ ...s, ingredients: [...s.ingredients, ...rows] }));
    closePaste();
  };

  // ── steps ──
  const setStep = (stepUid: string, text: string) =>
    setState((s) => ({
      ...s,
      steps: s.steps.map((st) => (st.uid === stepUid ? { ...st, text } : st)),
    }));
  const addStep = () => patch({ steps: [...state.steps, blankStep()] });
  const removeStep = (stepUid: string) =>
    patch({ steps: state.steps.filter((st) => st.uid !== stepUid) });
  const moveStep = (index: number, delta: number) =>
    patch({ steps: move(state.steps, index, delta) });

  // ── tags ──
  const commitTag = () => {
    const t = tagDraft.trim();
    if (t && !state.tags.includes(t)) patch({ tags: [...state.tags, t] });
    setTagDraft("");
  };
  const removeTag = (tag: string) =>
    patch({ tags: state.tags.filter((t) => t !== tag) });

  function onTagKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commitTag();
    } else if (e.key === "Backspace" && !tagDraft && state.tags.length) {
      patch({ tags: state.tags.slice(0, -1) });
    }
  }

  // ── submit ──
  function validate(): ClientErrors | null {
    const errors: ClientErrors = { rows: {} };
    if (!state.title.trim()) errors.title = "Title is required.";
    for (const row of ingredientRowsToSubmit(state)) {
      if (!row.item.trim()) {
        errors.rows[row.uid] = "An ingredient row needs an item.";
      }
    }
    return errors.title || Object.keys(errors.rows).length ? errors : null;
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    // fold a half-typed tag into the list before serializing
    const pendingTag = tagDraft.trim();
    const working =
      pendingTag && !state.tags.includes(pendingTag)
        ? { ...state, tags: [...state.tags, pendingTag] }
        : state;
    if (pendingTag) {
      setState(working);
      setTagDraft("");
    }

    const problems = validate();
    setClientErrors(problems ?? { rows: {} });
    if (problems) return;

    const rows = ingredientRowsToSubmit(working);
    submittedUidsRef.current = rows.map((r) => r.uid);
    mutation.mutate(buildRecipeCreate(working));
  }

  const openUrl = useMemo(
    () => asOpenableUrl(state.sourceUrl),
    [state.sourceUrl],
  );

  return (
    <section className={styles.page}>
      <header className={styles.head}>
        <h1>New recipe</h1>
        <Link to="/" className={styles.cancel}>
          Cancel
        </Link>
      </header>

      <form className={styles.form} onSubmit={onSubmit} noValidate>
        {formError !== null && (
          <p className={styles.banner} role="alert">
            {formError}
          </p>
        )}

        <div className={styles.scalars}>
          <Field label="Title" error={titleError} required>
            <Input
              value={state.title}
              onChange={(e) => patch({ title: e.target.value })}
              autoFocus
            />
          </Field>
          <Field label="Cuisine" error={fieldErrors["cuisine"]}>
            <Input
              value={state.cuisine}
              onChange={(e) => patch({ cuisine: e.target.value })}
            />
          </Field>
          <Field label="Servings" error={fieldErrors["servings"]}>
            <Input
              type="number"
              min="0"
              inputMode="decimal"
              value={state.servings}
              onChange={(e) => patch({ servings: e.target.value })}
            />
          </Field>
          <Field label="Prep time (min)" error={fieldErrors["prep_time"]}>
            <Input
              type="number"
              min="0"
              inputMode="numeric"
              value={state.prepTime}
              onChange={(e) => patch({ prepTime: e.target.value })}
            />
          </Field>
          <Field label="Cook time (min)" error={fieldErrors["cook_time"]}>
            <Input
              type="number"
              min="0"
              inputMode="numeric"
              value={state.cookTime}
              onChange={(e) => patch({ cookTime: e.target.value })}
            />
          </Field>
          <Field
            label="Source URL"
            error={fieldErrors["source_url"]}
            hint={
              openUrl ? (
                <a href={openUrl} target="_blank" rel="noreferrer">
                  Open link
                </a>
              ) : undefined
            }
          >
            <Input
              value={state.sourceUrl}
              onChange={(e) => patch({ sourceUrl: e.target.value })}
              placeholder="https://…  (or any note)"
            />
          </Field>
        </div>

        <Field
          label="Tags"
          hint="Press Enter or comma to add each tag."
          error={fieldErrors["tags"]}
        >
          <div className={styles.tags}>
            {state.tags.map((tag) => (
              <span key={tag} className={styles.chip}>
                {tag}
                <button
                  type="button"
                  className={styles.chipRemove}
                  aria-label={`Remove tag ${tag}`}
                  onClick={() => removeTag(tag)}
                >
                  ×
                </button>
              </span>
            ))}
            <Input
              className={styles.tagInput}
              aria-label="Add tag"
              value={tagDraft}
              onChange={(e) => setTagDraft(e.target.value)}
              onKeyDown={onTagKeyDown}
              onBlur={commitTag}
            />
          </div>
        </Field>

        {/* ── Steps ── */}
        <fieldset className={styles.group}>
          <legend className={styles.legend}>Steps</legend>
          {state.steps.length === 0 && (
            <p className={styles.muted}>No steps yet.</p>
          )}
          <ol className={styles.steps}>
            {state.steps.map((step, i) => (
              <li key={step.uid} className={styles.stepRow}>
                <Textarea
                  aria-label={`Step ${i + 1}`}
                  rows={2}
                  value={step.text}
                  onChange={(e) => setStep(step.uid, e.target.value)}
                />
                <div className={styles.rowButtons}>
                  <Button
                    variant="ghost"
                    aria-label={`Move step ${i + 1} up`}
                    disabled={i === 0}
                    onClick={() => moveStep(i, -1)}
                  >
                    ↑
                  </Button>
                  <Button
                    variant="ghost"
                    aria-label={`Move step ${i + 1} down`}
                    disabled={i === state.steps.length - 1}
                    onClick={() => moveStep(i, 1)}
                  >
                    ↓
                  </Button>
                  <Button
                    variant="ghost"
                    aria-label={`Remove step ${i + 1}`}
                    onClick={() => removeStep(step.uid)}
                  >
                    Remove
                  </Button>
                </div>
              </li>
            ))}
          </ol>
          <Button variant="secondary" onClick={addStep}>
            Add step
          </Button>
        </fieldset>

        {/* ── Ingredients ── */}
        <fieldset className={styles.group}>
          <legend className={styles.legend}>Ingredients</legend>
          <p className={styles.muted}>
            Leave the quantity blank for “to taste”.
          </p>
          <div className={styles.tableScroll}>
            <table className={styles.table}>
              <thead>
                <tr>
                  <th scope="col">Quantity</th>
                  <th scope="col">Unit</th>
                  <th scope="col">Item</th>
                  <th scope="col">Note</th>
                  <th scope="col">
                    <span className="sr-only">Row actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {state.ingredients.map((row, i) => {
                  const itemErr = rowError(row.uid, "item");
                  const errId = itemErr ? `${row.uid}-item-error` : undefined;
                  return (
                    <tr key={row.uid}>
                      <td>
                        <Input
                          aria-label={`Quantity for ingredient ${i + 1}`}
                          inputMode="decimal"
                          value={row.quantity}
                          onChange={(e) =>
                            setRow(row.uid, { quantity: e.target.value })
                          }
                        />
                      </td>
                      <td>
                        <Input
                          aria-label={`Unit for ingredient ${i + 1}`}
                          value={row.unit}
                          onChange={(e) =>
                            setRow(row.uid, { unit: e.target.value })
                          }
                        />
                      </td>
                      <td>
                        <Input
                          aria-label={`Item for ingredient ${i + 1}`}
                          aria-invalid={itemErr ? true : undefined}
                          aria-describedby={errId}
                          value={row.item}
                          onChange={(e) =>
                            setRow(row.uid, { item: e.target.value })
                          }
                        />
                        {itemErr && (
                          <span
                            id={errId}
                            className={styles.cellError}
                            role="alert"
                          >
                            {itemErr}
                          </span>
                        )}
                      </td>
                      <td>
                        <Input
                          aria-label={`Note for ingredient ${i + 1}`}
                          value={row.note}
                          onChange={(e) =>
                            setRow(row.uid, { note: e.target.value })
                          }
                        />
                      </td>
                      <td className={styles.rowButtons}>
                        <Button
                          variant="ghost"
                          aria-label={`Move ingredient ${i + 1} up`}
                          disabled={i === 0}
                          onClick={() => moveRow(i, -1)}
                        >
                          ↑
                        </Button>
                        <Button
                          variant="ghost"
                          aria-label={`Move ingredient ${i + 1} down`}
                          disabled={i === state.ingredients.length - 1}
                          onClick={() => moveRow(i, 1)}
                        >
                          ↓
                        </Button>
                        <Button
                          variant="ghost"
                          aria-label={`Remove ingredient ${i + 1}`}
                          onClick={() => removeRow(row.uid)}
                        >
                          Remove
                        </Button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <div className={styles.rowButtons}>
            <Button variant="secondary" onClick={addRow}>
              Add ingredient
            </Button>
            <Button variant="secondary" onClick={() => setPasteOpen(true)}>
              Paste ingredients
            </Button>
          </div>
        </fieldset>

        <Dialog
          open={pasteOpen}
          onClose={closePaste}
          title="Paste ingredients"
          footer={
            <>
              <Button variant="ghost" onClick={closePaste}>
                Cancel
              </Button>
              <Button
                onClick={confirmPaste}
                disabled={pastePreview.length === 0}
              >
                Add {rowCount(pastePreview.length)}
              </Button>
            </>
          }
        >
          <Field
            label="Ingredient lines"
            hint="One ingredient per line. Blank lines, bullets, and “For the sauce:” headers are dropped."
          >
            <Textarea
              rows={8}
              value={pasteText}
              onChange={(e) => setPasteText(e.target.value)}
              placeholder={"2 tbsp olive oil\n1 onion, diced\nsalt to taste"}
            />
          </Field>

          {pasteText.trim() !== "" &&
            (pastePreview.length === 0 ? (
              <p className={styles.muted}>
                Nothing to add — every line was blank or a section header.
              </p>
            ) : (
              <div className={styles.tableScroll}>
                <table className={styles.table}>
                  <caption className={styles.previewCaption}>
                    Preview — {rowCount(pastePreview.length)} will be appended.
                    Fix any misparse in the table after.
                  </caption>
                  <thead>
                    <tr>
                      <th scope="col">Quantity</th>
                      <th scope="col">Unit</th>
                      <th scope="col">Item</th>
                      <th scope="col">Note</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pastePreview.map((p, i) => (
                      <tr key={i}>
                        <td>{quantityToInput(p.quantity) || "—"}</td>
                        <td>{p.unit || "—"}</td>
                        <td>{p.item}</td>
                        <td>{p.note || "—"}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
        </Dialog>

        <Field label="Notes" error={fieldErrors["notes"]}>
          <Textarea
            rows={3}
            value={state.notes}
            onChange={(e) => patch({ notes: e.target.value })}
          />
        </Field>

        <div className={styles.actions}>
          <Button type="submit" loading={mutation.isPending}>
            Save recipe
          </Button>
        </div>
      </form>
    </section>
  );
}

export default function RecipeForm({ mode }: { mode: "create" | "edit" }) {
  return mode === "edit" ? <EditPlaceholder /> : <CreateForm />;
}
