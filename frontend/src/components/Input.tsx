import {
  forwardRef,
  useContext,
  type InputHTMLAttributes,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from "react";
import { FieldContext } from "./fieldContext";
import styles from "./Control.module.css";

type AriaInvalid = InputHTMLAttributes<HTMLInputElement>["aria-invalid"];

interface Wired {
  id?: string;
  "aria-describedby"?: string;
  "aria-invalid"?: AriaInvalid;
  className?: string;
}

/** Merge `<Field>` context (id / describedby / invalid) with explicit props. */
function useWiring(props: Wired) {
  const field = useContext(FieldContext);
  return {
    id: props.id ?? field?.controlId,
    describedBy: props["aria-describedby"] ?? field?.describedBy,
    ariaInvalid: props["aria-invalid"] ?? (field?.invalid ? true : undefined),
    className: [styles.control, props.className].filter(Boolean).join(" "),
  };
}

export const Input = forwardRef<
  HTMLInputElement,
  InputHTMLAttributes<HTMLInputElement>
>(function Input({ className, ...rest }, ref) {
  const w = useWiring({ ...rest, className });
  return (
    <input
      ref={ref}
      {...rest}
      id={w.id}
      aria-describedby={w.describedBy}
      aria-invalid={w.ariaInvalid}
      className={w.className}
    />
  );
});

export const Textarea = forwardRef<
  HTMLTextAreaElement,
  TextareaHTMLAttributes<HTMLTextAreaElement>
>(function Textarea({ className, ...rest }, ref) {
  const w = useWiring({ ...rest, className });
  return (
    <textarea
      ref={ref}
      {...rest}
      id={w.id}
      aria-describedby={w.describedBy}
      aria-invalid={w.ariaInvalid}
      className={w.className}
    />
  );
});

export const Select = forwardRef<
  HTMLSelectElement,
  SelectHTMLAttributes<HTMLSelectElement>
>(function Select({ className, ...rest }, ref) {
  const w = useWiring({ ...rest, className });
  return (
    <select
      ref={ref}
      {...rest}
      id={w.id}
      aria-describedby={w.describedBy}
      aria-invalid={w.ariaInvalid}
      className={w.className}
    />
  );
});
