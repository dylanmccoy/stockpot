import { useId, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "./Badge";
import { DeductionDetail } from "./DeductionDetail";
import { cx } from "../lib/cx";
import { formatDateTime, formatQuantity } from "../lib/format";
import type { CookDeductionRead, CookLogRead } from "../types";
import styles from "./CookLogRow.module.css";

// Shared cook-log row for both history surfaces (spec §10.8): the per-recipe
// panel in RecipeDetail (ticket 11a) and the global `/history` feed (ticket
// 11b). Collapsed it shows when / who / multiplier / whether stock moved;
// expanded (only when stock was deducted) it reveals the per-ingredient
// `DeductionDetail` table. Forward-only — no undo affordance (R-12).

/** Collapsed-accordion summary from the deduction reasons, e.g.
 *  "12 ingredients · 2 ran out · 1 not tracked" (spec §10.8). Only non-zero
 *  counts appear; a clean cook is just "N ingredients". */
export function deductionSummary(deductions: CookDeductionRead[]): string {
  const count = (r: CookDeductionRead["reason"]) =>
    deductions.filter((d) => d.reason === r).length;
  const parts = [
    `${deductions.length} ${deductions.length === 1 ? "ingredient" : "ingredients"}`,
  ];
  const ranOut = count("clamped to 0");
  const notTracked = count("not in inventory");
  const toCheck = count("have uncertain (incompatible unit)");
  if (ranOut) parts.push(`${ranOut} ran out`);
  if (notTracked) parts.push(`${notTracked} not tracked`);
  if (toCheck) parts.push(`${toCheck} to check`);
  return parts.join(" · ");
}

export interface CookLogRowProps {
  log: CookLogRead;
  /** The global feed shows the recipe title; the per-recipe panel omits it
   *  ("you know the recipe" — spec §10.8). Linking is the global surface's job. */
  showRecipeTitle?: boolean;
}

export function CookLogRow({ log, showRecipeTitle = false }: CookLogRowProps) {
  const [open, setOpen] = useState(false);
  const detailId = useId();

  const cook = log.cooked_by?.username ?? "Unknown cook";
  const when = formatDateTime(log.cooked_at);
  const times = `×${formatQuantity(log.multiplier, null)}`;
  // `deducted` and a non-empty `deductions` travel together, but guard anyway.
  const expandable = log.deducted && log.deductions.length > 0;

  return (
    <li className={styles.row}>
      <div className={styles.line}>
        {showRecipeTitle &&
          (log.recipe_id === null ? (
            // Recipe deleted: title snapshot survives, but there is nothing to
            // link to (spec §10.8).
            <span className={styles.title}>
              {log.recipe_title}
              <span className={styles.deleted}> (recipe deleted)</span>
            </span>
          ) : (
            <Link
              to={`/recipes/${log.recipe_id}`}
              className={cx(styles.title, styles.titleLink)}
            >
              {log.recipe_title}
            </Link>
          ))}
        <span className={styles.when}>{when}</span>
        <span className={styles.sep} aria-hidden="true">
          ·
        </span>
        <span>{cook}</span>
        <span className={styles.sep} aria-hidden="true">
          ·
        </span>
        <span className={styles.times}>{times}</span>

        {/* Explicit deduct on/off token (spec §10.8 shared-row line). */}
        {log.deducted ? (
          <Badge tone="ok" icon="✓">
            stock updated
          </Badge>
        ) : (
          <Badge tone="neutral" icon="•">
            logged — stock not changed
          </Badge>
        )}

        {expandable && (
          <button
            type="button"
            className={styles.toggle}
            aria-expanded={open}
            aria-controls={detailId}
            onClick={() => setOpen((o) => !o)}
          >
            <span aria-hidden="true">{open ? "▾" : "▸"}</span>
            {deductionSummary(log.deductions)}
          </button>
        )}
      </div>

      {expandable && open && (
        <div id={detailId} className={styles.detail}>
          <DeductionDetail deductions={log.deductions} />
        </div>
      )}
    </li>
  );
}
