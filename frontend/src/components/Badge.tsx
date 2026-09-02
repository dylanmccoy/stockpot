import type { HTMLAttributes, ReactNode } from "react";
import { cx } from "../lib/cx";
import styles from "./Badge.module.css";

export type BadgeTone = "neutral" | "ok" | "warn" | "danger" | "accent";

export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  /** Optional leading glyph; status is never conveyed by color alone (§9). */
  icon?: ReactNode;
  children: ReactNode;
}

export function Badge({
  tone = "neutral",
  icon,
  children,
  className,
  ...rest
}: BadgeProps) {
  return (
    <span className={cx(styles.badge, styles[tone], className)} {...rest}>
      {icon && <span aria-hidden="true">{icon}</span>}
      {children}
    </span>
  );
}
