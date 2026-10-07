import { useMemo, useRef, useState } from "react";
import {
  Button,
  Dialog,
  InlineNotice,
  PersonSelect,
  type PersonOption,
} from "../../../design-system";
import { ApiFailure } from "../../../app/api/http";
import type { CaseRecord, EmployeeSummary } from "../../../app/api/models";
import { useSession } from "../../../app/session/useSession";
import styles from "./CaseApprovalDialog.module.css";
import { recordImageSrc } from "../../../app/api/recordImages";

export function CaseApprovalDialog({
  item,
  people,
  label,
  onClose,
  onSaved,
}: {
  item: CaseRecord;
  people: EmployeeSummary[];
  label: (id: string | null) => string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const { api } = useSession();
  const [coordinator, setCoordinator] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const replay = useRef({ payload: "", key: "" });
  const coordinators: PersonOption[] = useMemo(
    () =>
      people
        .filter(
          (person) =>
            person.status === "Active" &&
            person.designation === "Coordinator" &&
            person.branchId === item.branchId &&
            person.departmentId === item.departmentId,
        )
        .map((person) => ({
          value: person.id,
          name: person.fullName,
          subtitle: person.employeeCode,
          src: recordImageSrc("employee", person),
        })),
    [item.branchId, item.departmentId, people],
  );

  const submit = async () => {
    if (!coordinator) {
      setError("Select a Coordinator from the same Branch and Department.");
      return;
    }
    const payload = JSON.stringify({ coordinatorEmployeeId: coordinator });
    if (replay.current.payload !== payload)
      replay.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      await api.request(`/cases/${item.id}/approval`, {
        method: "POST",
        body: payload,
        headers: { "Idempotency-Key": replay.current.key },
      });
      onSaved();
    } catch (failure) {
      setError(
        failure instanceof ApiFailure
          ? failure.message
          : "Unable to approve this Case. You can retry this request safely.",
      );
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      title="Approve and assign Coordinator"
      size="md"
      busy={busy}
      onClose={() => {
        if (!busy) onClose();
      }}
      footer={
        <>
          <Button
            variant="secondary"
            size="compact"
            disabled={busy}
            onClick={onClose}
          >
            Cancel
          </Button>
          <Button
            size="compact"
            loading={busy}
            disabled={busy || !coordinator}
            onClick={() => void submit()}
          >
            Approve and assign
          </Button>
        </>
      }
    >
      <div className={styles.body}>
        <p className={styles.summary}>
          {`${item.internalCaseId} · ${label(item.customerId)} · ${label(item.branchId)} · ${label(item.departmentId)}`}
        </p>
        <PersonSelect
          id="approval-coordinator"
          label="Coordinator"
          compact
          people={coordinators}
          value={coordinator}
          onChange={setCoordinator}
        />
        {coordinators.length === 0 ? (
          <InlineNotice tone="warning" title="No eligible Coordinator">
            There is no active Coordinator in the same Branch and Department.
          </InlineNotice>
        ) : null}
        {error ? (
          <InlineNotice tone="error" title="Unable to approve">
            {error}
          </InlineNotice>
        ) : null}
      </div>
    </Dialog>
  );
}
