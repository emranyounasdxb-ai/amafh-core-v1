import { useEffect, useId, useState, type FormEvent } from "react";
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
import {
  clearPasswordLink,
  passwordLinkKind,
  passwordLinkToken,
} from "./passwordLink";
import { ApiClient, ApiFailure } from "../api/http";

export function SignIn() {
  const { signIn, notice, expired, dismissExpiry, refreshSession } =
    useSession();
  // Redemption is authorized by the link, not the current account. Session
  // refresh/sign-out in this or another tab must not abort this public command.
  const [linkApi] = useState(() => new ApiClient(() => null));
  useEffect(() => () => linkApi.invalidateSession(), [linkApi]);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [completed, setCompleted] = useState(false);
  const emailId = useId();
  const passwordId = useId();
  const kind = passwordLinkKind();
  const token = passwordLinkToken();
  const linkProblem =
    kind && (!token || token.length < 30 || token.length > 128)
      ? "This password link is missing or invalid. Reopen the complete link supplied to you, or ask your system administrator for a new link."
      : "";
  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (linkProblem) return;
    setBusy(true);
    setError("");
    try {
      if (kind) {
        await linkApi.request(`/auth/${kind}`, {
          method: "POST",
          body: JSON.stringify({
            token,
            password,
          }),
        });
        clearPasswordLink();
        dismissExpiry();
        // The server revokes only the target account's sessions. Recheck the
        // current identity without logging in as, or switching to, that target.
        refreshSession();
        window.history.replaceState(null, "", "/");
        window.dispatchEvent(new PopStateEvent("popstate"));
        setCompleted(true);
      } else await signIn(email, password);
      setPassword("");
    } catch (failure) {
      setError(
        failure instanceof ApiFailure && failure.code === "INVALID_LINK"
          ? "This password link is invalid or no longer available. It may have expired, already been used, or been replaced or revoked. Ask your system administrator for a new link."
          : failure instanceof Error
            ? failure.message
            : kind
              ? "Unable to save your password. Please retry."
              : "Unable to sign in. Please retry.",
      );
    } finally {
      setBusy(false);
    }
  };
  const showExpiry = expired && !kind;
  const heading = showExpiry
    ? "Session expired"
    : kind
      ? kind === "reset"
        ? "Reset your password"
        : "Set your password"
      : "Sign in";
  const submitLabel = kind ? "Save password" : "Sign in";
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
                  kind
                    ? "Use 12–128 characters with uppercase, lowercase, a number and a special character."
                    : completed
                      ? "Password saved. Sign in with your Official/Login email and new password."
                      : notice ||
                        "Enter your Official/Login email and password to continue."
                }
              />
              <form onSubmit={submit} className={styles.form}>
                {!kind && (
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
                    autoComplete={kind ? "new-password" : "current-password"}
                    required
                    minLength={kind ? 12 : undefined}
                    maxLength={128}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                  />
                </FormField>
                {linkProblem || error ? (
                  <InlineNotice tone="error">
                    {linkProblem || error}
                  </InlineNotice>
                ) : null}
                <Button
                  type="submit"
                  size="large"
                  className={styles.submit}
                  loading={busy}
                  disabled={Boolean(linkProblem)}
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
