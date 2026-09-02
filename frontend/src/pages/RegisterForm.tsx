import { useState, type FormEvent } from "react";
import { useAuth } from "../auth/useAuth";
import { ApiError, fieldName, isFieldError } from "../lib/apiError";
import { Button, Field, Input } from "../components";
import styles from "./Login.module.css";

const GENERIC_ERROR = "Something went wrong. Please try again.";

interface RegisterErrors {
  fieldErrors: Record<string, string>;
  formError: string | null;
}

/**
 * Route a register failure to its surface (spec §6):
 *  - `422 ValidationIssue[]` → per-field, keyed by the last `loc` segment
 *  - `409 "username taken"`  → the username field (the one string-detail row §6
 *    puts on a field instead of the form banner — so not `useFormErrors`)
 *  - `403 "registration disabled"` / `"invalid registration code"` → banner
 */
function toRegisterErrors(err: unknown): RegisterErrors {
  if (!(err instanceof ApiError)) {
    return { fieldErrors: {}, formError: GENERIC_ERROR };
  }
  if (isFieldError(err)) {
    const fieldErrors: Record<string, string> = {};
    for (const issue of err.detail) {
      const key = fieldName(issue);
      if (!(key in fieldErrors)) fieldErrors[key] = issue.msg;
    }
    return { fieldErrors, formError: null };
  }
  const detail = typeof err.detail === "string" ? err.detail : GENERIC_ERROR;
  if (err.status === 409) {
    return { fieldErrors: { username: detail }, formError: null };
  }
  return { fieldErrors: {}, formError: detail };
}

/**
 * First-user bootstrap form, rendered by `Login` only when
 * `VITE_ENABLE_REGISTER` is set (spec §4). The shipped production bundle never
 * mounts it. On success the new user is signed in and `Login`'s redirect runs.
 */
export default function RegisterForm() {
  const { register } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [code, setCode] = useState("");
  const [errors, setErrors] = useState<RegisterErrors>({
    fieldErrors: {},
    formError: null,
  });
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setErrors({ fieldErrors: {}, formError: null });
    setSubmitting(true);
    try {
      await register(username, password, code.trim() || undefined);
    } catch (err) {
      setErrors(toRegisterErrors(err));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <section className={styles.card} aria-labelledby="register-heading">
      <h2 id="register-heading">Create an account</h2>
      <form className={styles.form} onSubmit={onSubmit} noValidate>
        {errors.formError !== null && (
          <p className={styles.formError} role="alert">
            {errors.formError}
          </p>
        )}
        <Field label="Username" error={errors.fieldErrors.username}>
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
          error={errors.fieldErrors.password}
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
          error={errors.fieldErrors.code}
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
