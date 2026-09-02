import { useId, useMemo, type ReactNode } from "react";
import { FieldContext, type FieldContextValue } from "./fieldContext";
import styles from "./Field.module.css";

export interface FieldProps {
  label: ReactNode;
  children: ReactNode;
  /** Override the generated control id (e.g. to match an external `htmlFor`). */
  id?: string;
  hint?: ReactNode;
  /** Field-level error(s). An array renders as a list. */
  error?: string | string[];
  required?: boolean;
}

/**
 * Label + control + hint + error, and the single place field errors render
 * (docs/frontend/spec.md §8). The control nested as `children` picks up the
 * wiring through `FieldContext`.
 */
export function Field({
  label,
  children,
  id,
  hint,
  error,
  required = false,
}: FieldProps) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const hintId = `${controlId}-hint`;
  const errorId = `${controlId}-error`;

  const errors =
    error === undefined ? [] : Array.isArray(error) ? error : [error];
  const hasError = errors.length > 0;

  const describedBy =
    [hint ? hintId : null, hasError ? errorId : null]
      .filter(Boolean)
      .join(" ") || undefined;

  const ctx = useMemo<FieldContextValue>(
    () => ({ controlId, describedBy, invalid: hasError, required }),
    [controlId, describedBy, hasError, required],
  );

  return (
    <div className={styles.field}>
      <label htmlFor={controlId} className={styles.label}>
        {label}
        {required && (
          <span className={styles.requiredMark} aria-hidden="true">
            {" "}
            *
          </span>
        )}
      </label>

      <FieldContext.Provider value={ctx}>{children}</FieldContext.Provider>

      {hint && (
        <p id={hintId} className={styles.hint}>
          {hint}
        </p>
      )}

      {hasError && (
        <p id={errorId} className={styles.error} role="alert">
          {errors.length === 1 ? (
            errors[0]
          ) : (
            <ul>
              {errors.map((message, i) => (
                <li key={i}>{message}</li>
              ))}
            </ul>
          )}
        </p>
      )}
    </div>
  );
}
