import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { cx } from "../lib/cx";
import styles from "./Toast.module.css";

export type ToastVariant = "info" | "success" | "error";

export interface ToastOptions {
  variant?: ToastVariant;
  /** Override the auto-dismiss delay (ms). Errors never auto-dismiss. */
  duration?: number;
}

interface ToastItem {
  id: number;
  variant: ToastVariant;
  message: ReactNode;
  duration: number | null;
}

interface ToastApi {
  show: (message: ReactNode, opts?: ToastOptions) => number;
  dismiss: (id: number) => void;
}

const DEFAULT_DURATION = 5000;
const VARIANT_LABEL: Record<ToastVariant, string> = {
  info: "Info",
  success: "Success",
  error: "Error",
};

const ToastContext = createContext<ToastApi | null>(null);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const nextId = useRef(1);

  const dismiss = useCallback((id: number) => {
    setItems((current) => current.filter((t) => t.id !== id));
  }, []);

  const show = useCallback((message: ReactNode, opts: ToastOptions = {}) => {
    const variant = opts.variant ?? "info";
    const id = nextId.current++;
    const duration =
      variant === "error" ? null : (opts.duration ?? DEFAULT_DURATION);
    setItems((current) => [...current, { id, variant, message, duration }]);
    return id;
  }, []);

  const api = useMemo<ToastApi>(() => ({ show, dismiss }), [show, dismiss]);

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        className={styles.region}
        role="region"
        aria-label="Notifications"
        aria-live="polite"
      >
        {items.map((item) => (
          <ToastRow key={item.id} item={item} onDismiss={dismiss} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastRow({
  item,
  onDismiss,
}: {
  item: ToastItem;
  onDismiss: (id: number) => void;
}) {
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (item.duration === null || paused) return;
    const timer = setTimeout(() => onDismiss(item.id), item.duration);
    return () => clearTimeout(timer);
  }, [item.duration, item.id, paused, onDismiss]);

  return (
    <div
      className={cx(styles.toast, styles[item.variant])}
      role="status"
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
    >
      <span className={styles.label}>{VARIANT_LABEL[item.variant]}</span>
      <span className={styles.body}>{item.message}</span>
      <button
        type="button"
        className={styles.dismiss}
        aria-label="Dismiss notification"
        onClick={() => onDismiss(item.id)}
      >
        ×
      </button>
    </div>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (ctx === null) {
    throw new Error("useToast must be used within a <ToastProvider>");
  }
  return ctx;
}
