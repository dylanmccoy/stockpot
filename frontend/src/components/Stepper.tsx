import { useEffect, useId, useState } from "react";
import styles from "./Stepper.module.css";

// The default presets only need ½; extend when a caller passes another fraction.
const FRACTION_GLYPH: Record<string, string> = { "0.500": "½" };

function presetLabel(n: number): string {
  return FRACTION_GLYPH[n.toFixed(3)] ?? String(n);
}

export interface StepperProps {
  value: number;
  onChange: (value: number) => void;
  /** Quick-pick values. Default matches the multiplier control (§10.2). */
  presets?: number[];
  step?: number;
  /** Exclusive lower bound. Default `0` — the control enforces `> 0`. */
  min?: number;
  id?: string;
  /** Visible group label. Falls back to `aria-label` when omitted. */
  label?: string;
  "aria-label"?: string;
}

export function Stepper({
  value,
  onChange,
  presets = [0.5, 1, 2, 3],
  step = 1,
  min = 0,
  id,
  label,
  "aria-label": ariaLabel,
}: StepperProps) {
  const autoId = useId();
  const groupId = id ?? autoId;
  const labelId = `${groupId}-label`;
  const inputId = `${groupId}-value`;

  const [draft, setDraft] = useState(String(value));
  useEffect(() => setDraft(String(value)), [value]);

  const commit = (raw: string) => {
    const parsed = Number(raw);
    if (Number.isFinite(parsed) && parsed > min) onChange(parsed);
    else setDraft(String(value));
  };

  const decDisabled = value - step <= min;

  return (
    <div
      className={styles.stepper}
      role="group"
      aria-labelledby={label ? labelId : undefined}
      aria-label={label ? undefined : ariaLabel}
    >
      {label && (
        <span id={labelId} className={styles.groupLabel}>
          {label}
        </span>
      )}

      <span className={styles.presets}>
        {presets.map((preset) => (
          <button
            key={preset}
            type="button"
            className={styles.preset}
            aria-pressed={preset === value}
            onClick={() => onChange(preset)}
          >
            {presetLabel(preset)}
          </button>
        ))}
      </span>

      <span className={styles.spin}>
        <button
          type="button"
          className={styles.step}
          aria-label="Decrease"
          disabled={decDisabled}
          onClick={() => onChange(value - step)}
        >
          −
        </button>
        <input
          id={inputId}
          className={styles.value}
          type="number"
          inputMode="decimal"
          min={min}
          step={step}
          aria-label="Exact value"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onBlur={(e) => commit(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit((e.target as HTMLInputElement).value);
            }
          }}
        />
        <button
          type="button"
          className={styles.step}
          aria-label="Increase"
          onClick={() => onChange(value + step)}
        >
          +
        </button>
      </span>
    </div>
  );
}
