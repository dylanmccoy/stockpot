import type { HTMLAttributes } from "react";
import { cx } from "../lib/cx";
import styles from "./Card.module.css";

export type CardProps = HTMLAttributes<HTMLDivElement>;

/** Padded surface for list items and panels (docs/frontend/spec.md §8). */
export function Card({ className, children, ...rest }: CardProps) {
  return (
    <div className={cx(styles.card, className)} {...rest}>
      {children}
    </div>
  );
}
