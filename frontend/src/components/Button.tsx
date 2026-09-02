import { forwardRef, type ButtonHTMLAttributes } from "react";
import styles from "./Button.module.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  /** Shows a spinner and disables the button; keeps a real `type`. */
  loading?: boolean;
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = "primary",
      loading = false,
      disabled,
      children,
      className,
      type,
      ...rest
    },
    ref,
  ) {
    const classes = [styles.button, styles[variant], className]
      .filter(Boolean)
      .join(" ");

    return (
      <button
        ref={ref}
        type={type ?? "button"}
        className={classes}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...rest}
      >
        {loading && <span className={styles.spinner} aria-hidden="true" />}
        {children}
      </button>
    );
  },
);
