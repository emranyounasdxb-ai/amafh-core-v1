import { useState } from "react";
import {
  Button,
  CopyButton,
  DestructiveConfirmationDialog,
  Dialog,
  EmptyValue,
  FormField,
  InfoField,
  InfoGrid,
  InlineNotice,
  RecordActions,
  SectionCard,
  Stack,
  StatusBadge,
  TextInput,
  type StatusTone,
} from "../../../design-system";
import { ApiFailure } from "../../../app/api/http";
import { useSession } from "../../../app/session/useSession";
import type { EmployeeAccountState } from "./employeePresentation";

type AccessAction =
  "code" | "provision" | "email" | "setup" | "reset" | "disable" | "enable";

const STATE_LABELS: Record<string, { label: string; tone: StatusTone }> = {
  none: { label: "Not provisioned", tone: "neutral" },
  "Not Provisioned": { label: "Awaiting password setup", tone: "warning" },
  Active: { label: "Active", tone: "success" },
  Disabled: { label: "Disabled", tone: "neutral" },
};

export function EmployeeAccessSection({
  employeeId,
  employeeName,
  personalEmail,
  employeeCode,
  employeeStatus,
  employeeDesignation,
  account,
  embedded = false,
  onChanged,
}: {
  employeeId: string;
  employeeName: string;
  personalEmail: string | null;
  employeeCode: string;
  employeeStatus: string;
  employeeDesignation: string | null;
  account: EmployeeAccountState | null | undefined;
  embedded?: boolean;
  onChanged: () => void;
}) {
  const { api, session } = useSession();
  const [success, setSuccess] = useState("");
  const [link, setLink] = useState("");
  const [code, setCode] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState<AccessAction | null>(null);
  const [confirmDisable, setConfirmDisable] = useState(false);
  const [disableError, setDisableError] = useState("");
  const [emailDialog, setEmailDialog] = useState<"provision" | "email" | null>(null);
  const [loginEmail, setLoginEmail] = useState("");
  const [emailError, setEmailError] = useState("");
  const [emailReviewed, setEmailReviewed] = useState(false);
  const designation = session?.designation;
  const manage = designation === "Owner" || designation === "HR";
  const privilegedTarget =
    employeeDesignation === "Owner" ||
    employeeDesignation === "Managing Director";
  const manageTarget = manage && (!privilegedTarget || designation === "Owner");
  const setup = manageTarget;
  const reset =
    (designation === "Owner" || designation === "Managing Director") &&
    (!privilegedTarget || designation === "Owner");
  const lockedReset = designation === "Owner";
  const disable = manageTarget && employeeDesignation !== "Owner";
  if (!manage && !reset) return null;

  const run = async (action: AccessAction) => {
    if (busy) return;
    setBusy(action);
    setError("");
    setSuccess("");
    setLink("");
    try {
      if (action === "setup" || action === "reset") {
        const value = await api.request<{ link: string }>(
          `/auth/${action}-links`,
          { method: "POST", body: JSON.stringify({ employeeId }) },
        );
        setLink(value.link);
      } else if (action === "code") {
        setCode(
          (
            await api.request<{ systemEmployeeCode: string }>(
              `/employees/${employeeId}/login-code`,
            )
          ).systemEmployeeCode,
        );
      } else {
        if (!account) throw new Error("Access has not been provisioned.");
        await api.request(
          `/users/${encodeURIComponent(account.id)}/${action}`,
          { method: "POST" },
        );
        setSuccess("Account action saved by the server.");
        onChanged();
      }
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Account action failed",
      );
    } finally {
      setBusy(null);
    }
  };
  const openEmail = (mode: "provision" | "email") => {
    setLoginEmail(mode === "email" ? account?.loginEmail ?? "" : "");
    setEmailError("");
    setEmailReviewed(false);
    setEmailDialog(mode);
  };
  const saveEmail = async () => {
    if (busy || !emailDialog) return;
    setBusy(emailDialog);
    setEmailError("");
    setLink("");
    setSuccess("");
    try {
      if (emailDialog === "provision") {
        const result = await api.request<{ id: string; link: string }>("/users", {
          method: "POST",
          body: JSON.stringify({ employeeId, loginEmail: loginEmail.trim() }),
        });
        setLink(result.link);
      } else {
        if (!account) throw new Error("Account unavailable.");
        await api.request(`/users/${encodeURIComponent(account.id)}/login-email`, {
          method: "PATCH",
          body: JSON.stringify({ loginEmail: loginEmail.trim() }),
        });
      }
      setEmailDialog(null);
      setSuccess("Official/Login email saved by the server.");
      onChanged();
    } catch (failure) {
      setEmailReviewed(false);
      setEmailError(failure instanceof ApiFailure
        ? failure.fieldErrors.loginEmail?.join(" ") || failure.message
        : "Official/Login email could not be saved. Please retry.");
    } finally {
      setBusy(null);
    }
  };
  const openDisable = () => {
    if (busy) return;
    setError("");
    setSuccess("");
    setLink("");
    setDisableError("");
    setConfirmDisable(true);
  };
  const closeDisable = () => {
    if (busy) return;
    setConfirmDisable(false);
    setDisableError("");
  };
  const disableAccess = async () => {
    if (busy || !account) return;
    setBusy("disable");
    setDisableError("");
    try {
      await api.request(`/users/${encodeURIComponent(account.id)}/disable`, {
        method: "POST",
      });
      setConfirmDisable(false);
      setSuccess("Account action saved by the server.");
      onChanged();
    } catch (failure) {
      setDisableError(
        failure instanceof ApiFailure
          ? failure.message
          : "Access could not be disabled. Retry safely when the connection returns.",
      );
    } finally {
      setBusy(null);
    }
  };
  const action = (key: AccessAction, label: string) => (
    <Button
      key={key}
      size="compact"
      variant="secondary"
      loading={busy === key}
      disabled={Boolean(busy)}
      onClick={() => key === "disable" ? openDisable()
        : key === "provision" || key === "email" ? openEmail(key) : void run(key)}
    >
      {label}
    </Button>
  );

  const eligible = employeeStatus === "Active";
  const stateKey =
    account === undefined
      ? ""
      : account === null
        ? "none"
        : account.accessStatus;
  const state = STATE_LABELS[stateKey];
  const actions: AccessAction[] = [];
  let guidance = "";
  if (!state) {
    guidance = "The current account state is unavailable.";
  } else if (stateKey === "none") {
    if (manageTarget && eligible) actions.push("provision");
    else
      guidance = manageTarget
        ? "Access can be provisioned once the employee is Active with a current assignment."
        : "No system account has been provisioned.";
  } else if (stateKey === "Not Provisioned") {
    if (setup) actions.push("setup");
    if (disable) actions.push("disable");
    if (!actions.length) guidance = "The account is awaiting password setup.";
  } else if (stateKey === "Active") {
    if (disable) actions.push("disable");
    if (reset && (!account?.locked || lockedReset)) actions.push("reset");
    else if (reset)
      guidance =
        "The account is locked. An Owner must generate the reset link.";
  } else if (stateKey === "Disabled") {
    if (manageTarget && eligible) actions.push("enable");
    else
      guidance = manageTarget
        ? `Access cannot be enabled while the employee is ${employeeStatus}.`
        : "Access is disabled.";
  }
  if (privilegedTarget && designation !== "Owner" && !actions.length)
    guidance = "Only the Owner can manage this account.";
  if (account && manageTarget) actions.push("email");
  const labels: Record<AccessAction, string> = {
    code: "Show System Employee Code",
    provision: "Provision access",
    email: account?.loginEmail ? "Change Login email" : "Configure Login email",
    setup: "Generate setup link",
    reset: "Generate reset link",
    disable: "Disable access",
    enable: "Enable access",
  };

  const content = (
    <>
      <Stack>
        <InfoGrid>
          {account ? <InfoField label="Official/Login email" value={account.loginEmail || "Not configured"} /> : null}
          <InfoField
            label="Account status"
            value={
              state ? (
                <StatusBadge tone={state.tone}>{state.label}</StatusBadge>
              ) : (
                "Unavailable"
              )
            }
          />
          {account?.locked ? (
            <InfoField
              label="Sign-in"
              value={<StatusBadge tone="warning">Locked</StatusBadge>}
            />
          ) : null}
          {code ? (
            <InfoField label="System Employee Code" value={code} />
          ) : null}
        </InfoGrid>
        {manage || actions.length ? (
          <RecordActions>
            {manage ? action("code", labels.code) : null}
            {actions.map((key) => action(key, labels[key]))}
          </RecordActions>
        ) : null}
        {guidance ? (
          <InlineNotice tone="info" title="System access">
            {guidance}
          </InlineNotice>
        ) : null}
        {link ? (
          <FormField
            label="One-use link"
            htmlFor="employee-access-link"
            hint="Share this link manually with the employee."
          >
            <TextInput
              id="employee-access-link"
              compact
              readOnly
              value={link}
              suffix={<CopyButton value={link} label="Copy link" />}
            />
          </FormField>
        ) : null}
        {success ? (
          <InlineNotice tone="success" title="Saved">
            {success}
          </InlineNotice>
        ) : null}
        {error ? (
          <InlineNotice tone="error" title="Unable to complete">
            {error}
          </InlineNotice>
        ) : null}
      </Stack>
      <Dialog
        open={emailDialog !== null}
        title={emailDialog === "provision" ? "Provision access" : "Configure Official/Login email"}
        size="md"
        busy={Boolean(busy)}
        onClose={() => { if (!busy) setEmailDialog(null); }}
        footer={<RecordActions>
          <Button variant="secondary" disabled={Boolean(busy)} onClick={() => setEmailDialog(null)}>Cancel</Button>
          <Button type="submit" form="employee-login-email" loading={busy === emailDialog}>
            {emailReviewed ? emailDialog === "provision" ? "Confirm provision access" : "Confirm Login email" : "Review"}
          </Button>
        </RecordActions>}
      >
        <form id="employee-login-email" onSubmit={(event) => {
          event.preventDefault();
          if (emailReviewed) void saveEmail();
          else { setLoginEmail(loginEmail.trim()); setEmailReviewed(true); }
        }}>
          <Stack>
            <InfoGrid>
              <InfoField label="Employee" value={employeeName} />
              <InfoField label="Personal email" value={personalEmail || <EmptyValue />} />
            </InfoGrid>
            <FormField label="Official/Login email" htmlFor="employee-login-email-input"
              required error={emailError || undefined} hint="This email will be used to sign in.">
              <TextInput id="employee-login-email-input" compact type="email" required maxLength={254}
                invalid={Boolean(emailError)}
                aria-describedby={emailError ? "employee-login-email-input-error" : "employee-login-email-input-hint"}
                value={loginEmail} disabled={Boolean(busy)} readOnly={emailReviewed}
                onChange={(event) => { setLoginEmail(event.target.value); setEmailError(""); }} />
            </FormField>
            {emailReviewed ? <>
              <InlineNotice tone="info" title="Confirm account identity">
                {emailDialog === "provision"
                  ? "This creates application access and a one-use password setup link. Share the link manually."
                  : "Changing the Login email signs out existing sessions and invalidates outstanding setup/reset links. The password, permissions and account status are preserved. An unchanged email has no effect."}
              </InlineNotice>
              <Button variant="secondary" disabled={Boolean(busy)} onClick={() => setEmailReviewed(false)}>Edit email</Button>
            </> : null}
          </Stack>
        </form>
      </Dialog>
      <DestructiveConfirmationDialog
        open={confirmDisable}
        title="Disable system access"
        confirmLabel="Disable access"
        busy={busy === "disable"}
        onClose={closeDisable}
        onConfirm={() => void disableAccess()}
      >
        <Stack>
          <InfoGrid>
            <InfoField label="Employee" value={employeeName} />
            <InfoField
              label="Employee code"
              value={employeeCode || <EmptyValue />}
            />
            <InfoField
              label="Account status"
              value={
                state ? (
                  <StatusBadge tone={state.tone}>{state.label}</StatusBadge>
                ) : (
                  "Unavailable"
                )
              }
            />
          </InfoGrid>
          <p>
            The employee will no longer be able to sign in to AMAFH Core. The
            Employee record and its history are retained.
          </p>
          {disableError ? (
            <InlineNotice tone="error" title="Unable to disable access">
              {disableError}
            </InlineNotice>
          ) : null}
        </Stack>
      </DestructiveConfirmationDialog>
    </>
  );
  return embedded ? (
    <section aria-label="System access">
      <h3>System access</h3>
      {content}
    </section>
  ) : (
    <SectionCard compact title="System access">
      {content}
    </SectionCard>
  );
}
