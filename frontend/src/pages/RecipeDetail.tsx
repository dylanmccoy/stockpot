import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { recipesApi } from "../api/recipes";
import { cookLogsApi } from "../api/cookLogs";
import type {
  AvailabilityLine,
  AvailabilityReport,
  AvailabilityStatus,
  RecipeIngredientRead,
  RecipeRead,
} from "../types";
import {
  ApiError,
  GENERIC_ERROR_MESSAGE,
  STOCK_CONFLICT_MESSAGE,
  isStockConflict,
} from "../lib/apiError";
import { formatDateTime, formatQuantity } from "../lib/format";
import { cx } from "../lib/cx";
import {
  Badge,
  Button,
  CookLogRow,
  DataTable,
  Dialog,
  Stepper,
  useToast,
} from "../components";
import type { BadgeTone, Column } from "../components";
import styles from "./RecipeDetail.module.css";

// RecipeDetail — body + multiplier (spec §10.4, body Phase 3), the availability
// table (Phase 4), the cook action (Phase 5), and the per-recipe made-history
// panel (spec §10.8, ticket 11a). Availability and cook are built against the
// spec DTO through the recipes adapter (R-2) and wired to real calls in tickets
// 16 / 17.

/** `source_url` is stored verbatim and never validated (R-14); this only decides
 *  whether to offer an "open link" affordance. Mirrors `asOpenableUrl` in
 *  RecipeForm — a few lines, kept local rather than importing across pages. */
export function asOpenableUrl(raw: string | null): string | null {
  const t = raw?.trim();
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

/** Count units carry no unit word — the label is just the number (spec §7.2). */
const COUNT_UNITS: ReadonlySet<string | null> = new Set([null, "unit", "each"]);

/** Append the unit word to an already-formatted amount, except for count units
 *  which carry none (spec §7.2). Empty in → empty out. */
function withUnitWord(formatted: string, unit: string | null): string {
  if (!formatted) return "";
  if (COUNT_UNITS.has(unit)) return formatted;
  return [formatted, unit].filter(Boolean).join(" ");
}

/** A recipe row's quantity, scaled by the multiplier and run through
 *  `formatQuantity` (spec §7.2), with its unit appended — never a raw float.
 *  `null` quantity (to-taste) → `""`; the caller renders "to taste" itself. */
export function scaledQuantityLabel(
  ingredient: Pick<RecipeIngredientRead, "quantity" | "unit">,
  multiplier: number,
): string {
  const { quantity, unit } = ingredient;
  if (quantity === null) return "";
  return withUnitWord(formatQuantity(quantity * multiplier, unit), unit);
}

/** A bare amount + unit for availability copy (spec §7.2); `null`/non-finite
 *  → `""`. */
export function amountLabel(value: number | null, unit: string | null): string {
  return withUnitWord(formatQuantity(value, unit), unit);
}

interface StatusMeta {
  tone: BadgeTone;
  /** Non-color status glyph — status is never color-only (spec §9). */
  icon: string;
  /** Badge text; `short` gets the shortfall amount appended by the caller. */
  label: string;
  /** Counted toward the "Missing N items" banner tally. `have_uncertain` is
   *  not — the household may in fact have it, just in an incomparable unit
   *  (spec §7.4). */
  countsAsMissing: boolean;
}

const STATUS_META: Record<AvailabilityStatus, StatusMeta> = {
  ok: { tone: "ok", icon: "✓", label: "Have it", countsAsMissing: false },
  short: { tone: "warn", icon: "△", label: "Short", countsAsMissing: true },
  have_uncertain: {
    tone: "warn",
    icon: "?",
    label: "Check what you have",
    countsAsMissing: false,
  },
  missing: {
    tone: "danger",
    icon: "✕",
    label: "Missing",
    countsAsMissing: true,
  },
  to_taste: {
    tone: "neutral",
    icon: "•",
    label: "To taste",
    countsAsMissing: false,
  },
};

interface AvailabilityRow {
  groupKey: string;
  item: string;
  status: AvailabilityStatus;
  /** Scaled requirement for the group, canonical unit; `"—"` for to-taste. */
  needLabel: string;
  /** Badge text — includes the shortfall amount only for `short` (§7.4). */
  statusLabel: string;
}

/** Collapse matching quantified lines into one row per `group_key` (spec §10.4).
 *  A mixed quantified/to-taste group keeps one row for each state so neither is
 *  hidden. Insertion order is preserved so the table reads like the recipe. */
export function groupAvailabilityLines(
  lines: AvailabilityLine[],
): AvailabilityRow[] {
  const order: string[] = [];
  const byKey = new Map<string, AvailabilityLine[]>();
  for (const line of lines) {
    const members = byKey.get(line.group_key);
    if (members) {
      members.push(line);
    } else {
      byKey.set(line.group_key, [line]);
      order.push(line.group_key);
    }
  }
  return order.flatMap((key) => {
    const members = byKey.get(key)!;
    const toTaste = members.filter((member) => member.status === "to_taste");
    const quantified = members.filter(
      (member) => member.status !== "to_taste",
    );

    const buildRow = (
      rowMembers: AvailabilityLine[],
      first: AvailabilityLine,
      rowKey: string,
    ): AvailabilityRow => ({
      groupKey: rowKey,
      item: [...new Set(rowMembers.map((member) => member.item))].join(", "),
      status: first.status,
      needLabel:
        first.status === "to_taste"
          ? "—"
          : amountLabel(first.group_need, first.group_unit) || "—",
      statusLabel:
        first.status === "short"
          ? `Short ${amountLabel(first.group_short, first.group_unit)}`.trimEnd()
          : STATUS_META[first.status].label,
    });

    if (toTaste.length > 0 && quantified.length > 0) {
      // The backend deliberately emits a group's to-taste members before its
      // quantified members. Keep both states visible instead of letting that
      // first vacuous line hide the group's real need/status.
      return [
        buildRow(toTaste, toTaste[0], `${key}|to-taste`),
        buildRow(quantified, quantified[0], `${key}|quantified`),
      ];
    }

    const first = members[0];
    return [buildRow(members, first, key)];
  });
}

const availabilityColumns: Column<AvailabilityRow>[] = [
  { key: "item", header: "Ingredient", render: (r) => r.item },
  { key: "need", header: "Need", align: "end", render: (r) => r.needLabel },
  {
    key: "status",
    header: "Status",
    render: (r) => (
      <span className={styles.statusCell}>
        <Badge
          tone={STATUS_META[r.status].tone}
          icon={STATUS_META[r.status].icon}
        >
          {r.statusLabel}
        </Badge>
        {r.status === "have_uncertain" && (
          <span className={styles.statusNote}>
            You have some, but in a unit we can’t compare (e.g. cans vs grams).
          </span>
        )}
      </span>
    ),
  },
];

/** Header banner (spec §10.4). `all_available` is the server's word for "every
 *  non-to-taste line is ok". When it isn't, tally the distinct groups that are
 *  genuinely short/missing; a report whose only gaps are `have_uncertain` rows
 *  gets the §7.4 "check what you have" prompt instead of a "missing" count. */
function availabilityBanner(report: AvailabilityReport): string {
  if (report.all_available) return "You have everything";
  const missing = new Set(
    report.lines
      .filter((l) => STATUS_META[l.status].countsAsMissing)
      .map((l) => l.group_key),
  ).size;
  if (missing === 0) return "Check what you have";
  return `Missing ${missing} ${missing === 1 ? "item" : "items"}`;
}

/** Availability table (spec §10.4). Driven by the same multiplier as the
 *  ingredient list; `["availability", id, multiplier]` re-runs on each change,
 *  keeping the last result on screen while the next loads. */
function AvailabilityPanel({
  id,
  multiplier,
}: {
  id: number;
  multiplier: number;
}) {
  const query = useQuery({
    queryKey: ["availability", id, multiplier],
    queryFn: () => recipesApi.availability(id, multiplier),
    placeholderData: keepPreviousData,
  });

  return (
    <section className={styles.section} aria-labelledby="availability-heading">
      <h2 id="availability-heading">Availability</h2>

      {query.isPending && (
        <p role="status" className={styles.muted}>
          Checking what you have…
        </p>
      )}

      {query.isError && (
        <div className={styles.panelError} role="alert">
          <p className={styles.muted}>Couldn’t check availability.</p>
          <Button variant="secondary" onClick={() => query.refetch()}>
            Retry
          </Button>
        </div>
      )}

      {query.data && (
        <>
          <p
            aria-live="polite"
            className={cx(
              styles.banner,
              query.data.all_available ? styles.bannerOk : styles.bannerWarn,
            )}
          >
            <span aria-hidden="true">
              {query.data.all_available ? "✓ " : "! "}
            </span>
            {availabilityBanner(query.data)}
          </p>
          <DataTable
            caption="Per-ingredient availability at the current multiplier"
            columns={availabilityColumns}
            rows={groupAvailabilityLines(query.data.lines)}
            rowKey={(r) => r.groupKey}
            empty="No tracked ingredients to check."
          />
        </>
      )}
    </section>
  );
}

/** Cook action (spec §10.4, Phase 5). A single "mark as cooked" button plus a
 *  "deduct from inventory" toggle (on by default); the POST carries the screen's
 *  current multiplier, so a double batch deducts twice the stock. Forward-only —
 *  there is no undo affordance (R-12). Built against the spec DTO through the
 *  recipes adapter; wired to real calls in ticket 17. */
function CookPanel({ id, multiplier }: { id: number; multiplier: number }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [deduct, setDeduct] = useState(true);

  // The availability table and Inventory screen both read from stock; a cook
  // (or a failed cook that may have half-applied) makes them stale.
  const invalidateStockViews = () => {
    queryClient.invalidateQueries({ queryKey: ["availability", id] });
    queryClient.invalidateQueries({ queryKey: ["inventory"] });
  };

  const cook = useMutation({
    mutationFn: () => recipesApi.cook(id, { multiplier, deduct }),
    onSuccess: () => {
      // Every stock- and history-derived view is now stale (spec §10.4).
      invalidateStockViews();
      queryClient.invalidateQueries({ queryKey: ["cook-logs"] });
      queryClient.invalidateQueries({ queryKey: ["recipe-cook-logs", id] });
      toast.show("Cooked — logged to your history.", { variant: "success" });
    },
    onError: (err: unknown) => {
      if (isStockConflict(err)) {
        // R-11: refetch what the deduction would have touched, ask for a retry.
        invalidateStockViews();
        toast.show(STOCK_CONFLICT_MESSAGE, { variant: "error" });
      } else {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    },
  });

  return (
    <section className={styles.section} aria-labelledby="cook-heading">
      <h2 id="cook-heading">Cook</h2>
      <div className={styles.cookBar}>
        <Button loading={cook.isPending} onClick={() => cook.mutate()}>
          {deduct ? "Mark as cooked & update inventory" : "Mark as cooked"}
        </Button>
        <label className={styles.deductToggle}>
          <input
            type="checkbox"
            checked={deduct}
            onChange={(e) => setDeduct(e.target.checked)}
          />
          Deduct from inventory
        </label>
      </div>
    </section>
  );
}

/** Per-recipe made-history panel (spec §10.8) — lives inside RecipeDetail, not
 *  its own route. Lists every cook of this recipe, newest first, unpaginated,
 *  with no recipe-title column. Shares `CookLogRow` with the global `/history`
 *  feed (ticket 11b). The `["recipe-cook-logs", id]` key is invalidated by a
 *  cook in `CookPanel` above. */
function HistoryPanel({ id }: { id: number }) {
  const query = useQuery({
    queryKey: ["recipe-cook-logs", id],
    queryFn: () => cookLogsApi.byRecipe(id),
  });

  // Server order is `cooked_at DESC, id DESC`; sort defensively so "newest
  // first" holds even if that ever slips (matches the ingredient sort above).
  const logs = query.data
    ? [...query.data].sort(
        (a, b) =>
          Date.parse(b.cooked_at) - Date.parse(a.cooked_at) || b.id - a.id,
      )
    : [];

  return (
    <section className={styles.section} aria-labelledby="history-heading">
      <h2 id="history-heading">Made history</h2>

      {query.isPending && (
        <p role="status" className={styles.muted}>
          Loading history…
        </p>
      )}

      {query.isError && (
        <div className={styles.panelError} role="alert">
          <p className={styles.muted}>Couldn’t load this recipe’s history.</p>
          <Button variant="secondary" onClick={() => query.refetch()}>
            Retry
          </Button>
        </div>
      )}

      {query.data &&
        (logs.length === 0 ? (
          <p className={styles.muted}>
            Cook this recipe to start its history.
          </p>
        ) : (
          <>
            <p className={styles.muted}>
              Cooked {logs.length} {logs.length === 1 ? "time" : "times"} · last{" "}
              {formatDateTime(logs[0].cooked_at)}
            </p>
            <ul className={styles.history}>
              {logs.map((log) => (
                <CookLogRow key={log.id} log={log} />
              ))}
            </ul>
          </>
        ))}
    </section>
  );
}

function NotFoundPanel() {
  return (
    <section className={styles.panel} role="alert">
      <h1>Recipe not found</h1>
      <p className={styles.muted}>This recipe may have been deleted.</p>
      <Link to="/">Back to recipes</Link>
    </section>
  );
}

export default function RecipeDetail() {
  const { id } = useParams();
  const numeric = Number(id);
  if (!id || !Number.isInteger(numeric) || numeric <= 0) {
    return <NotFoundPanel />;
  }
  // Remount on id change so the multiplier resets to 1 on every visit to the
  // screen (spec §10.4 — a stale remembered multiplier is a footgun).
  return <RecipeDetailView key={id} id={numeric} />;
}

function RecipeDetailView({ id }: { id: number }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [multiplier, setMultiplier] = useState(1);
  const [confirmOpen, setConfirmOpen] = useState(false);

  // One query per screen; request cancellation buys nothing here, so the
  // adapter's optional `signal` is left unused (matches RecipeList).
  const query = useQuery({
    queryKey: ["recipe", id],
    queryFn: () => recipesApi.get(id),
  });

  const del = useMutation({
    mutationFn: () => recipesApi.remove(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["recipes"] });
      navigate("/");
    },
    onError: () => {
      setConfirmOpen(false);
      toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
    },
  });

  if (query.isPending) {
    return (
      <section className={styles.page} aria-busy="true">
        <p role="status" className="sr-only">
          Loading recipe…
        </p>
        <div className={styles.skeleton} aria-hidden="true" />
      </section>
    );
  }

  if (query.isError) {
    const notFound =
      query.error instanceof ApiError && query.error.status === 404;
    if (notFound) return <NotFoundPanel />;
    return (
      <section className={styles.panel} role="alert">
        <p>
          {query.error instanceof Error
            ? query.error.message
            : "Could not load this recipe."}
        </p>
        <Button variant="secondary" onClick={() => query.refetch()}>
          Retry
        </Button>
      </section>
    );
  }

  const recipe: RecipeRead = query.data;
  const openUrl = asOpenableUrl(recipe.source_url);
  // The API returns ingredients ordered by position; sort defensively so the
  // screen still reads top-to-bottom if that ever slips (ticket: "in order").
  const ingredients = [...recipe.ingredients].sort(
    (a, b) => a.position - b.position,
  );

  const meta: Array<[string, string]> = [];
  if (recipe.cuisine) meta.push(["Cuisine", recipe.cuisine]);
  if (recipe.servings != null) meta.push(["Servings", String(recipe.servings)]);
  if (recipe.prep_time != null) meta.push(["Prep", `${recipe.prep_time} min`]);
  if (recipe.cook_time != null) meta.push(["Cook", `${recipe.cook_time} min`]);

  return (
    <section className={styles.page}>
      <header className={styles.head}>
        <h1>{recipe.title}</h1>
        <Button variant="danger" onClick={() => setConfirmOpen(true)}>
          Delete recipe
        </Button>
      </header>

      {meta.length > 0 && (
        <dl className={styles.meta}>
          {meta.map(([term, value]) => (
            <div key={term} className={styles.metaItem}>
              <dt>{term}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      )}

      {recipe.source_url && (
        <p className={styles.source}>
          {openUrl ? (
            <a href={openUrl} target="_blank" rel="noreferrer">
              Open source link
            </a>
          ) : (
            <span>Source: {recipe.source_url}</span>
          )}
        </p>
      )}

      <section className={styles.section} aria-labelledby="ingredients-heading">
        <div className={styles.sectionHead}>
          <h2 id="ingredients-heading">Ingredients</h2>
          <Stepper
            label="Multiplier"
            value={multiplier}
            onChange={setMultiplier}
          />
        </div>
        <ul className={styles.ingredients}>
          {ingredients.map((ing) => {
            const qty = scaledQuantityLabel(ing, multiplier);
            const note = ing.note?.trim();
            return (
              <li key={ing.id} className={styles.ingredient}>
                {qty && <span className={styles.qty}>{qty}</span>}
                <span className={styles.item}>{ing.item}</span>
                {ing.quantity === null && (
                  <span className={styles.note}>to taste</span>
                )}
                {note && note.toLowerCase() !== "to taste" && (
                  <span className={styles.note}>{note}</span>
                )}
              </li>
            );
          })}
        </ul>
      </section>

      <AvailabilityPanel id={id} multiplier={multiplier} />

      <CookPanel id={id} multiplier={multiplier} />

      {recipe.steps.length > 0 && (
        <section className={styles.section} aria-labelledby="steps-heading">
          <h2 id="steps-heading">Steps</h2>
          <ol className={styles.steps}>
            {recipe.steps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ol>
        </section>
      )}

      {recipe.notes.trim() && (
        <section className={styles.section} aria-labelledby="notes-heading">
          <h2 id="notes-heading">Notes</h2>
          <p className={styles.notes}>{recipe.notes}</p>
        </section>
      )}

      <HistoryPanel id={id} />

      <Dialog
        open={confirmOpen}
        onClose={() => setConfirmOpen(false)}
        title="Delete this recipe?"
        footer={
          <>
            <Button variant="ghost" onClick={() => setConfirmOpen(false)}>
              Cancel
            </Button>
            <Button
              variant="danger"
              loading={del.isPending}
              onClick={() => del.mutate()}
            >
              Delete
            </Button>
          </>
        }
      >
        <p>
          “{recipe.title}” will be permanently removed. This can’t be undone.
        </p>
      </Dialog>
    </section>
  );
}
