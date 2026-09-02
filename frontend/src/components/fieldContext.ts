import { createContext } from "react";

/**
 * Set by `<Field>` so the control nested inside it inherits the generated `id`,
 * the `aria-describedby` target(s) for hint/error text, and the invalid flag —
 * without every screen re-wiring those by hand.
 */
export interface FieldContextValue {
  controlId: string;
  describedBy?: string;
  invalid: boolean;
  required: boolean;
}

export const FieldContext = createContext<FieldContextValue | null>(null);
