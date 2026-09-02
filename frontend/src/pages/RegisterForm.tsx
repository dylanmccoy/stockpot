import { useMemo, useState, type FormEvent } from "react";
import { useAuth } from "../auth/useAuth";
import {
  ApiError,
  GENERIC_ERROR_MESSAGE,
  hasInlineFormError,
  useFormErrors,
  type FormErrors,
} from "../lib/apiError";
import { Button, Field, Input, useToast } from "../components";
import styles from "./auth.module.css";

/**
 * First-user bootstrap form, rendered by `Login` only when
 * `VITE_ENABLE_REGISTER` is set (spec §4). The shipped production bundle never
 * mounts it. On success the new user is signed in and `Login`'s redirect runs.
 */
export default function RegisterForm() {
  const { register } = useAuth();
  const toast = useToast();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [submitError, setSubmitError] = useState<unknown>(null);
  const [submitting, setSubmitting] = useState(false);

  // 422 → per-field, 403 (disabled / bad code) → form banner: both from the
  // shared hook. The one row §6 sends to a field instead of the banner is
  // 409 "username taken", so that case is redirected onto the username field.
  const split = useFormErrors(submitError);
  const { fieldErrors, formError } = useMemo<FormErrors>(() => {
    if (
      submitError instanceof ApiError &&
      submitError.status === 409 &&
      typeof submitError.detail === "string"
    ) {
      return { fieldErrors: { username: submitError.detail }, formError: null };
    }
    return split;
  }, [submitError, split]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitError(null);
    setSubmitting(true);
    try {
      // Send the code exactly as typed (the server compares it verbatim);
      // an empty field means "no code" and is omitted by `AuthProvider`.
      await register(username, password, code);
    } catch (err) {
      setSubmitError(err);
      if (!hasInlineFormError(err)) {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className={styles.card} aria-labelledby="register-heading">
      <h2 id="register-heading">Create an account</h2>
      <form className={styles.form} onSubmit={onSubmit} noValidate>
        {formError !== null && (
          <p className={styles.formError} role="alert">
            {formError}
          </p>
        )}
        <Field label="Username" error={fieldErrors.username}>
          <Input
            name="username"
            autoComplete="username"
            required
            value={username}
            onChange={(event) => setUsername(event.target.value)}
          />
        </Field>
        <Field
          label="Password"
          hint="8–128 characters"
          error={fieldErrors.password}
        >
          <Input
            type="password"
            name="password"
            autoComplete="new-password"
            required
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </Field>
        <Field
          label="Registration code"
          hint="Only if your server requires one"
          error={fieldErrors.code}
        >
          <Input
            name="code"
            autoComplete="off"
            value={code}
            onChange={(event) => setCode(event.target.value)}
          />
        </Field>
        <Button type="submit" loading={submitting}>
          Create account
        </Button>
      </form>
    </section>
  );
}
