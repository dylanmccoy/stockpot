import { useState, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { ApiError } from "../lib/apiError";
import { Button, Field, Input } from "../components";
import RegisterForm from "./RegisterForm";
import styles from "./Login.module.css";

const GENERIC_ERROR = "Something went wrong. Please try again.";

/**
 * Keep the post-login redirect on this origin: only a plain absolute path is
 * honoured, so a crafted `?next=//evil.example` or `?next=https://…` falls back
 * to the home route.
 */
function sanitizeNext(raw: string | null): string {
  if (
    raw &&
    raw.startsWith("/") &&
    !raw.startsWith("//") &&
    !raw.startsWith("/\\")
  ) {
    return raw;
  }
  return "/";
}

export default function Login() {
  const { status, login } = useAuth();
  const [params] = useSearchParams();
  const next = sanitizeNext(params.get("next"));

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  // Login only ever fails with a 401 string detail (spec §6), so there are no
  // field issues to split — a plain message, not `useFormErrors`.
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (status === "loading") {
    return (
      <main className={styles.page}>
        <div role="status">Checking your session…</div>
      </main>
    );
  }
  if (status === "authenticated") {
    return <Navigate to={next} replace />;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setSubmitting(true);
    try {
      await login(username, password);
      // Success flips auth status to "authenticated"; the guard above then
      // redirects to `next`.
    } catch (err) {
      // §6: the login-failure `401` string is shown verbatim; a 5xx / transport
      // failure is not — it gets the generic line rather than a raw server
      // message.
      setFormError(
        err instanceof ApiError &&
          err.status === 401 &&
          typeof err.detail === "string"
          ? err.detail
          : GENERIC_ERROR,
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className={styles.page}>
      <div className={styles.card}>
        <h1>Log in</h1>
        <form className={styles.form} onSubmit={onSubmit} noValidate>
          {formError !== null && (
            <p className={styles.formError} role="alert">
              {formError}
            </p>
          )}
          <Field label="Username">
            <Input
              name="username"
              autoComplete="username"
              autoFocus
              required
              value={username}
              onChange={(event) => setUsername(event.target.value)}
            />
          </Field>
          <Field label="Password">
            <Input
              type="password"
              name="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </Field>
          <Button type="submit" loading={submitting}>
            Log in
          </Button>
        </form>
      </div>

      {Boolean(import.meta.env.VITE_ENABLE_REGISTER) && <RegisterForm />}
    </main>
  );
}
