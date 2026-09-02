import type { HTMLAttributes } from "react";
import styles from "./Card.module.css";

export type CardProps = HTMLAttributes<HTMLDivElement>;

/** Padded surface for list items and panels (docs/frontend/spec.md §8). */
export function Card({ className, children, ...rest }: CardProps) {
  return (
    <div
      className={[styles.card, className].filter(Boolean).join(" ")}
      {...rest}
    >
      {children}
    </div>
  );
}
