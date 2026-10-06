import { useState } from "react";
import {
  ConfirmationDialog,
  DatePicker,
  DestructiveConfirmationDialog,
  EmptyValue,
  FormField,
  InfoField,
  InfoGrid,
  InlineNotice,
  Stack,
  TextArea,
  dubaiTodayDateOnly,
} from "../../../design-system";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { ApiFailure } from "../../../app/api/http";
import type { DataRecord } from "../../../app/api/models";
import { useSession } from "../../../app/session/useSession";
import { assignmentCommand, profileCommand } from "../employeeCommands";
import {
  employeeCode,
  employeeName,
  type EmployeeDetailRecord,
} from "./employeePresentation";

export type EmployeeCommandKind =
  "profile" | "assignment" | "activate" | "offboard" | "lastWorkingDate";

function Fact({ label, value }: { label: string; value: string }) {
  return <InfoField label={label} value={value || <EmptyValue />} />;
}

export function EmployeeCommandDialog({
  kind,
  employee,
  branch,
  department,
  onClose,
  onSaved,
}: {
  kind: EmployeeCommandKind;
  employee: EmployeeDetailRecord;
  branch: string;
  department: string;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { api, session } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [lastWorkingDate, setLastWorkingDate] = useState("");
  const [dateError, setDateError] = useState("");
  const [reason, setReason] = useState("");
  const [reasonError, setReasonError] = useState("");
  const name = employeeName(employee);

  if (kind === "profile")
    return (
      <CommandFormDialog
        command={profileCommand(
          employee.id,
          session?.designation === "Owner" ||
            !["Owner", "Managing Director"].includes(
              employee.designation || "",
            ),
        )}
        record={employee as unknown as DataRecord}
        onClose={onClose}
        onSaved={() => onSaved("Profile saved.")}
      />
    );
  if (kind === "assignment")
    return (
      <CommandFormDialog
        command={assignmentCommand(employee, session?.designation === "Owner")}
        record={employee as unknown as DataRecord}
        onClose={onClose}
        onSaved={() => onSaved("Assignment change saved.")}
      />
    );

  const run = async () => {
    const needsDate = kind === "offboard" || kind === "lastWorkingDate";
    const missingReason = kind === "lastWorkingDate" && !reason.trim();
    if (needsDate && !lastWorkingDate)
      setDateError("Last working date is required");
    if (missingReason) setReasonError("Reason is required");
    if ((needsDate && !lastWorkingDate) || missingReason) return;
    setBusy(true);
    setError("");
    try {
      if (kind === "lastWorkingDate")
        await api.request(`/employees/${employee.id}/last-working-date`, {
          method: "POST",
          body: JSON.stringify({ lastWorkingDate, reason: reason.trim() }),
        });
      else
        await api.request(`/employees/${employee.id}/${kind}`, {
          method: "POST",
          body:
            kind === "offboard"
              ? JSON.stringify({ lastWorkingDate })
              : undefined,
        });
      onSaved(
        kind === "activate"
          ? "Employee activated."
          : kind === "offboard"
            ? "Employee offboarded."
            : "Last working date recorded.",
      );
    } catch (failure) {
      setError(
        failure instanceof ApiFailure
          ? failure.message
          : "The request could not be completed. Retry safely when the connection returns.",
      );
    } finally {
      setBusy(false);
    }
  };
  const facts = (
    <InfoGrid>
      <Fact label="Employee" value={name} />
      <Fact label="Employee code" value={employeeCode(employee)} />
      <Fact label="Designation" value={employee.designation || ""} />
      <Fact label="Branch" value={branch} />
      <Fact label="Department" value={department} />
    </InfoGrid>
  );
  const notice = error ? (
    <InlineNotice tone="error" title="Unable to continue">
      {error}
    </InlineNotice>
  ) : null;

  if (kind === "activate")
    return (
      <ConfirmationDialog
        open
        title="Activate Employee"
        confirmLabel="Activate employee"
        busy={busy}
        onClose={onClose}
        onConfirm={() => void run()}
      >
        <Stack>
          <p>
            Activation requires an assigned Branch and Department. The employee
            becomes Active for operational work.
          </p>
          {facts}
          {notice}
        </Stack>
      </ConfirmationDialog>
    );

  if (kind === "lastWorkingDate")
    return (
      <ConfirmationDialog
        open
        title="Record last working date"
        confirmLabel="Record date"
        busy={busy}
        onClose={onClose}
        onConfirm={() => void run()}
      >
        <Stack>
          {facts}
          <p>
            Records the missing last working date for this Offboarded employee.
            Status, closed assignments and history stay unchanged. The date can
            be recorded once and is kept in the audit history with the reason.
          </p>
          <FormField
            label="Last working date"
            htmlFor="record-last-working-date"
            hint="Dubai date. Cannot be in the future or before the joining date."
            required
            error={dateError || undefined}
          >
            <DatePicker
              id="record-last-working-date"
              value={lastWorkingDate}
              min={employee.dateOfJoining || undefined}
              max={dubaiTodayDateOnly()}
              required
              invalid={Boolean(dateError)}
              onChange={(value) => {
                setLastWorkingDate(value);
                setDateError("");
              }}
            />
          </FormField>
          <FormField
            label="Reason"
            htmlFor="record-last-working-date-reason"
            hint="For example, the source document the date was taken from."
            required
            error={reasonError || undefined}
          >
            <TextArea
              id="record-last-working-date-reason"
              maxLength={1000}
              value={reason}
              aria-invalid={Boolean(reasonError) || undefined}
              onChange={(event) => {
                setReason(event.target.value);
                setReasonError("");
              }}
            />
          </FormField>
          {notice}
        </Stack>
      </ConfirmationDialog>
    );

  return (
    <DestructiveConfirmationDialog
      open
      title="Offboard Employee"
      confirmLabel="Offboard employee"
      busy={busy}
      onClose={onClose}
      onConfirm={() => void run()}
    >
      <Stack>
        {facts}
        <p>
          Offboarding ends the employee’s active assignment and marks the
          employee as Offboarded. Existing login access is disabled. The
          employee record and assignment history are retained. Current
          protections can prevent this action until issued assets or reporting
          responsibilities are resolved.
        </p>
        <FormField
          label="Last working date"
          htmlFor="offboard-last-working-date"
          hint="Dubai date. Cannot be in the future or before the joining date."
          required
          error={dateError || undefined}
        >
          <DatePicker
            id="offboard-last-working-date"
            value={lastWorkingDate}
            min={employee.dateOfJoining || undefined}
            max={dubaiTodayDateOnly()}
            required
            invalid={Boolean(dateError)}
            onChange={(value) => {
              setLastWorkingDate(value);
              setDateError("");
            }}
          />
        </FormField>
        {notice}
      </Stack>
    </DestructiveConfirmationDialog>
  );
}
