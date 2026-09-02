import { useState, type FormEvent } from "react";
import { Navigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { ApiError, GENERIC_ERROR_MESSAGE } from "../lib/apiError";
import { Button, Field, Input, useToast } from "../components";
import RegisterForm from "./RegisterForm";
import styles from "./auth.module.css";

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

/** Only an explicit opt-in string builds the register form (spec §4). A stray
 *  `VITE_ENABLE_REGISTER=false` / `=0` must not switch signup on. */
function registerEnabled(): boolean {
  const flag = import.meta.env.VITE_ENABLE_REGISTER;
  return flag === "1" || flag === "true";
}

export default function Login() {
  const { status, login } = useAuth();
  const toast = useToast();
  const [params] = useSearchParams();
  const next = sanitizeNext(params.get("next"));

  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  // Login's only inline failure is the login-rejection 401 string (spec §6) —
  // no field issues to split, so a plain message rather than `useFormErrors`.
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
      // §6: the login-rejection `401` string shows verbatim on the inline
      // banner; transport / `5xx` / anything else goes to a generic toast.
      if (
        err instanceof ApiError &&
        err.status === 401 &&
        typeof err.detail === "string"
      ) {
        setFormError(err.detail);
      } else {
        toast.show(GENERIC_ERROR_MESSAGE, { variant: "error" });
      }
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

      {registerEnabled() && <RegisterForm />}
    </main>
  );
}
