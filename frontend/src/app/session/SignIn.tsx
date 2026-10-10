import { useId, useState, type FormEvent } from "react";
import {
  Button,
  DesignSystemRoot,
  FormField,
  InlineNotice,
  PageTitle,
  SectionCard,
  TextInput,
} from "../../design-system";
import { useSession } from "./useSession";
import styles from "./SignIn.module.css";
import { clearPasswordLink, passwordLinkToken } from "./passwordLink";

export function SignIn() {
  const { signIn, notice, api, expired, dismissExpiry } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [completed, setCompleted] = useState(false);
  const emailId = useId();
  const passwordId = useId();
  const kind =
    window.location.pathname === "/setup-password"
      ? "setup"
      : window.location.pathname === "/reset-password"
        ? "reset"
        : null;
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      if (kind && !completed) {
        await api.request(`/auth/${kind}`, {
          method: "POST",
          body: JSON.stringify({
            token: passwordLinkToken(),
            password,
          }),
        });
        clearPasswordLink();
        window.history.replaceState(null, "", "/");
        window.dispatchEvent(new PopStateEvent("popstate"));
        setCompleted(true);
      } else await signIn(email, password);
      setPassword("");
    } catch (failure) {
      setError(
        failure instanceof Error
          ? failure.message
          : "Unable to sign in. Please retry.",
      );
    } finally {
      setBusy(false);
    }
  };
  const showExpiry = expired && !kind;
  const heading = showExpiry
    ? "Session expired"
    : kind && !completed
      ? "Set your password"
      : "Sign in";
  const submitLabel = kind && !completed ? "Save password" : "Sign in";
  return (
    <DesignSystemRoot className={styles.root}>
      <main className={styles.page} aria-label={heading}>
        <SectionCard className={styles.card}>
          <img
            className={styles.logo}
            src="/production/amafh-core-full-logo-exact.svg"
            alt="AMAFH Core"
          />
          {showExpiry ? (
            <>
              <div role="alert">
                <PageTitle
                  className={styles.heading}
                  title={heading}
                  subtitle="Your one-hour inactive session has ended. Sign in again to continue."
                />
              </div>
              <Button
                size="large"
                className={styles.submit}
                onClick={dismissExpiry}
              >
                Go to sign in
              </Button>
            </>
          ) : (
            <>
              <PageTitle
                className={styles.heading}
                title={heading}
                subtitle={
                  completed
                    ? "Password saved. Sign in with your Official/Login email and new password."
                    : notice ||
                      (kind
                        ? "Use 12–128 characters with uppercase, lowercase, a number and a special character."
                        : "Enter your Official/Login email and password to continue.")
                }
              />
              <form onSubmit={submit} className={styles.form}>
                {(!kind || completed) && (
                  <FormField label="Official/Login email" htmlFor={emailId}>
                    <TextInput
                      id={emailId}
                      type="email"
                      autoComplete="username"
                      autoCapitalize="none"
                      spellCheck={false}
                      placeholder="Enter your Official/Login email"
                      required
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                    />
                  </FormField>
                )}
                <FormField label="Password" htmlFor={passwordId}>
                  <TextInput
                    id={passwordId}
                    type="password"
                    placeholder="Enter your password"
                    autoComplete={
                      kind && !completed ? "new-password" : "current-password"
                    }
                    required
                    minLength={kind && !completed ? 12 : undefined}
                    maxLength={128}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </FormField>
                {error ? (
                  <InlineNotice tone="error">{error}</InlineNotice>
                ) : null}
                <Button
                  type="submit"
                  size="large"
                  className={styles.submit}
                  loading={busy}
                  aria-label={busy ? "Please wait…" : undefined}
                >
                  {submitLabel}
                </Button>
              </form>
              <p className={styles.support}>
                Need help signing in? Contact your system administrator.
              </p>
            </>
          )}
        </SectionCard>
      </main>
    </DesignSystemRoot>
  );
}
