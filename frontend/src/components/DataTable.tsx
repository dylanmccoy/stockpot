import type { ReactNode } from "react";
import styles from "./DataTable.module.css";

export interface Column<Row> {
  key: string;
  header: string;
  render: (row: Row) => ReactNode;
  align?: "start" | "end";
}

export interface DataTableProps<Row> {
  /** Accessible name for the table. Rendered as a `<caption>`. */
  caption: string;
  columns: Column<Row>[];
  rows: Row[];
  rowKey: (row: Row) => string | number;
  /** Shown in place of the body when `rows` is empty. */
  empty?: ReactNode;
}

/**
 * Real `<table>` >= 640px, stacked key/value rows below (docs/frontend/spec.md
 * §8). `scope` on headers; `data-label` feeds the stacked layout.
 */
export function DataTable<Row>({
  caption,
  columns,
  rows,
  rowKey,
  empty = "Nothing to show.",
}: DataTableProps<Row>) {
  return (
    <div className={styles.scroll}>
      <table className={styles.table}>
        <caption className={styles.caption}>{caption}</caption>
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                scope="col"
                className={col.align === "end" ? styles.alignEnd : undefined}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td className={styles.empty} colSpan={columns.length}>
                {empty}
              </td>
            </tr>
          ) : (
            rows.map((row) => (
              <tr key={rowKey(row)}>
                {columns.map((col) => (
                  <td
                    key={col.key}
                    data-label={col.header}
                    className={
                      col.align === "end" ? styles.alignEnd : undefined
                    }
                  >
                    {col.render(row)}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  );
}
