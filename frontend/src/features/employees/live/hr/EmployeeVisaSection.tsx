import { useState } from "react";
import {
  Button,
  CompactDate,
  CompactDateTime,
  DataTable,
  EmptyValue,
  ErrorState,
  InfoField,
  InfoGrid,
  InlineNotice,
  LoadingState,
  SectionCard,
  StatusBadge,
  Timeline,
  TruncatedText,
  type DataTableColumn,
  type TimelineItem,
} from "../../../../design-system";
import type { Command, Field } from "../../../../app/api/commands";
import type { DataRecord } from "../../../../app/api/models";
import { useResource } from "../../../../app/api/useResource";
import { CommandFormDialog } from "../../../../app/commands/CommandFormDialog";
import { useSession } from "../../../../app/session/useSession";
import {
  VISA_TYPES,
  failureMessage,
  visaStatusTone,
  type DocumentList,
  type VisaList,
  type VisaRecord,
  type VisaStatus,
} from "./hrRecords";
import styles from "./hrRecords.module.css";

const FIELD_LABELS: Record<string, string> = {
  visaType: "Visa type",
  sponsor: "Sponsor",
  visaNumber: "Visa or permit number",
  fileNumber: "File number",
  issueDate: "Issue date",
  expiryDate: "Expiry date",
  workPermitNumber: "Work permit number",
  workPermitExpiryDate: "Work permit expiry",
  medicalFitnessDate: "Medical fitness date",
  insuranceExpiryDate: "Insurance expiry",
  notes: "Notes",
};

const TRANSITION_LABELS: Record<string, string> = {
  "In Progress": "Start processing",
  Active: "Mark active",
  "Renewal In Progress": "Start renewal",
  "Cancellation In Progress": "Start cancellation",
  Cancelled: "Mark cancelled",
};

function visaFields(creating: boolean): Field[] {
  const section = "Visa";
  return [
    {
      key: "visaType",
      label: "Visa type",
      options: VISA_TYPES,
      required: creating,
      section,
    },
    { key: "sponsor", label: "Sponsor", required: creating, max: 160, section },
    { key: "visaNumber", label: "Visa or permit number", max: 80, section },
    { key: "fileNumber", label: "File number", max: 80, section },
    { key: "issueDate", label: "Issue date", type: "date", section },
    { key: "expiryDate", label: "Expiry date", type: "date", section },
    {
      key: "workPermitNumber",
      label: "Work permit number",
      max: 80,
      section: "Work permit, medical and insurance",
    },
    {
      key: "workPermitExpiryDate",
      label: "Work permit expiry",
      type: "date",
      section: "Work permit, medical and insurance",
    },
    {
      key: "medicalFitnessDate",
      label: "Medical fitness date",
      type: "date",
      section: "Work permit, medical and insurance",
    },
    {
      key: "insuranceExpiryDate",
      label: "Insurance expiry",
      type: "date",
      section: "Work permit, medical and insurance",
    },
    {
      key: "notes",
      label: "Notes",
      type: "textarea",
      max: 1000,
      section: "Notes",
    },
  ];
}

type VisaDialog =
  | { kind: "create" }
  | { kind: "edit"; record: VisaRecord }
  | { kind: "transition"; record: VisaRecord; to: VisaStatus }
  | { kind: "attach"; record: VisaRecord };

function DateValue({
  value,
  expired,
}: {
  value: string | null;
  expired?: boolean;
}) {
  if (!value) return <EmptyValue />;
  return (
    <span className={styles.inline}>
      <CompactDate value={value} />
      {expired ? <StatusBadge tone="danger">Expired</StatusBadge> : null}
    </span>
  );
}

function Text({ value }: { value: string | null }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function eventTitle(event: VisaRecord["events"][number]) {
  switch (event.eventType) {
    case "created":
      return "Visa record created";
    case "updated":
      return "Details updated";
    case "status_changed":
      return `${event.fromStatus} → ${event.toStatus}`;
    case "document_attached":
      return "Supporting document attached";
    case "document_detached":
      return "Supporting document detached";
    default:
      return "Visa record changed";
  }
}

function eventDescription(event: VisaRecord["events"][number]) {
  if (event.eventType === "updated" && event.changes)
    return Object.keys(event.changes)
      .map((key) => FIELD_LABELS[key] || "Detail")
      .join(", ");
  return event.note || undefined;
}

export function EmployeeVisaSection({
  employeeId,
  employeeStatus,
  canReadDocuments,
}: {
  employeeId: string;
  employeeStatus: string;
  canReadDocuments: boolean;
}) {
  const { api } = useSession();
  const [refresh, setRefresh] = useState(0);
  const [dialog, setDialog] = useState<VisaDialog | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [busyLink, setBusyLink] = useState("");
  const resource = useResource<VisaList>(
    `/employees/${employeeId}/visa-records`,
    refresh,
  );
  const data = resource.data;
  const current = data?.current ?? null;
  const manage = Boolean(data?.canManage);
  const documents = useResource<DocumentList>(
    manage && canReadDocuments && current
      ? `/employees/${employeeId}/documents`
      : null,
    refresh,
  );

  const saved = (message: string) => {
    setDialog(null);
    setError("");
    setNotice(message);
    setRefresh((value) => value + 1);
  };

  const detach = async (record: VisaRecord, linkId: string) => {
    setBusyLink(linkId);
    setError("");
    try {
      await api.request(`/visa-records/${record.id}/documents/${linkId}/detach`, {
        method: "POST",
      });
      saved("Supporting document detached.");
    } catch (failure) {
      setError(failureMessage(failure));
    } finally {
      setBusyLink("");
    }
  };

  const command = (state: VisaDialog): Command => {
    if (state.kind === "create")
      return {
        title: "Create visa record",
        path: `/employees/${employeeId}/visa-records`,
        submitLabel: "Create record",
        fields: visaFields(true),
      };
    if (state.kind === "edit")
      return {
        title: "Edit visa record",
        path: `/visa-records/${state.record.id}`,
        method: "PATCH",
        fields: visaFields(false),
      };
    if (state.kind === "transition")
      return {
        title: TRANSITION_LABELS[state.to] || "Change status",
        path: `/visa-records/${state.record.id}/transitions`,
        submitLabel: TRANSITION_LABELS[state.to] || "Change status",
        fixed: { fromStatus: state.record.status, toStatus: state.to },
        fields: [{ key: "note", label: "Note", type: "textarea", max: 1000 }],
        confirmation: {
          description:
            state.to === "Active"
              ? "An active visa requires the visa or permit number, issue date and expiry date."
              : "The status change is recorded in the visa history.",
          facts: [
            { label: "Current status", value: state.record.status },
            { label: "New status", value: state.to },
          ],
        },
      };
    const attached = new Set(state.record.documents.map((item) => item.documentId));
    const options = (documents.data?.documents ?? [])
      .filter(
        (item) => item.status === "Current" && !attached.has(item.latest.id),
      )
      .map((item) => ({
        value: item.latest.id,
        label: `${item.typeName} · version ${item.latest.version}`,
      }));
    return {
      title: "Attach supporting document",
      path: `/visa-records/${state.record.id}/documents`,
      submitLabel: "Attach document",
      fields: [
        {
          key: "documentId",
          label: "Employee document",
          required: true,
          options: options.map((option) => option.value),
          optionLabels: Object.fromEntries(
            options.map((option) => [option.value, option.label]),
          ),
        },
      ],
    };
  };

  const linkColumns: DataTableColumn<VisaRecord["documents"][number]>[] = [
    {
      key: "type",
      header: "Document",
      width: "200px",
      render: (row) => <TruncatedText value={row.typeName} />,
    },
    {
      key: "version",
      header: "Version",
      kind: "number",
      width: "88px",
      render: (row) => row.version,
    },
    {
      key: "status",
      header: "Document status",
      width: "140px",
      render: (row) => (
        <StatusBadge tone={row.documentStatus === "Current" ? "success" : "neutral"}>
          {row.documentStatus}
        </StatusBadge>
      ),
    },
    {
      key: "attached",
      header: "Attached",
      kind: "datetime",
      width: "150px",
      render: (row) => <CompactDateTime value={row.attachedAt} />,
    },
    ...(manage && current?.status !== "Cancelled"
      ? [
          {
            key: "actions",
            header: "Actions",
            width: "104px",
            fixed: true,
            render: (row: VisaRecord["documents"][number]) => (
              <Button
                size="compact"
                variant="ghost"
                loading={busyLink === row.linkId}
                onClick={() => current && void detach(current, row.linkId)}
              >
                Detach
              </Button>
            ),
          },
        ]
      : []),
  ];

  const historyColumns: DataTableColumn<VisaRecord>[] = [
    {
      key: "type",
      header: "Visa type",
      width: "150px",
      render: (row) => <TruncatedText value={row.visaType} />,
    },
    {
      key: "sponsor",
      header: "Sponsor",
      width: "180px",
      render: (row) => <TruncatedText value={row.sponsor} />,
    },
    {
      key: "number",
      header: "Visa number",
      width: "150px",
      render: (row) => <Text value={row.visaNumber} />,
    },
    {
      key: "expiry",
      header: "Expiry date",
      kind: "date",
      width: "120px",
      render: (row) => <DateValue value={row.expiryDate} />,
    },
    {
      key: "status",
      header: "Status",
      width: "120px",
      render: (row) => (
        <StatusBadge tone={visaStatusTone(row.status)}>{row.status}</StatusBadge>
      ),
    },
    {
      key: "updated",
      header: "Last updated",
      kind: "datetime",
      width: "150px",
      render: (row) => <CompactDateTime value={row.updatedAt} />,
    },
  ];

  const timeline: TimelineItem[] = (current?.events ?? []).map((event) => ({
    id: event.id,
    time: <CompactDateTime value={event.occurredAt} />,
    title: eventTitle(event),
    description: eventDescription(event),
    actor: event.actorName || "Team member",
    tone: event.eventType === "status_changed" ? "info" : "neutral",
  }));

  const canCreate =
    manage && !current && employeeStatus !== "Offboarded";
  return (
    <SectionCard
      compact
      title="Visa / PRO"
      description="Employee visa and work permit tracking. Expiry is shown as an indicator only; no reminders are sent."
      actions={
        canCreate ? (
          <Button
            size="compact"
            variant="secondary"
            onClick={() => {
              setNotice("");
              setDialog({ kind: "create" });
            }}
          >
            Create visa record
          </Button>
        ) : undefined
      }
    >
      <div className={`${styles.stack} ${styles.sectionStack}`}>
        {notice ? (
          <InlineNotice tone="success" title="Saved">
            {notice}
          </InlineNotice>
        ) : null}
        {error ? (
          <InlineNotice tone="error" title="Unable to continue">
            {error}
          </InlineNotice>
        ) : null}
        {resource.loading && !data ? (
          <LoadingState title="Loading visa records" />
        ) : resource.error && !data ? (
          <ErrorState description={resource.error} retry={resource.reload} />
        ) : current ? (
          <>
            <InfoGrid>
              <InfoField
                label="Status"
                value={
                  <span className={styles.inline}>
                    <StatusBadge tone={visaStatusTone(current.status)}>
                      {current.status}
                    </StatusBadge>
                    {current.expired ? (
                      <StatusBadge tone="danger">Expired</StatusBadge>
                    ) : null}
                  </span>
                }
              />
              <InfoField label="Visa type" value={<Text value={current.visaType} />} />
              <InfoField label="Sponsor" value={<Text value={current.sponsor} />} />
              <InfoField
                label="Visa or permit number"
                value={<Text value={current.visaNumber} />}
              />
              <InfoField
                label="File number"
                value={<Text value={current.fileNumber} />}
              />
              <InfoField
                label="Issue date"
                value={<DateValue value={current.issueDate} />}
              />
              <InfoField
                label="Expiry date"
                value={
                  <DateValue
                    value={current.expiryDate}
                    expired={current.expired}
                  />
                }
              />
              <InfoField
                label="Work permit number"
                value={<Text value={current.workPermitNumber} />}
              />
              <InfoField
                label="Work permit expiry"
                value={
                  <DateValue
                    value={current.workPermitExpiryDate}
                    expired={current.workPermitExpired}
                  />
                }
              />
              <InfoField
                label="Medical fitness date"
                value={<DateValue value={current.medicalFitnessDate} />}
              />
              <InfoField
                label="Insurance expiry"
                value={<DateValue value={current.insuranceExpiryDate} />}
              />
              <InfoField label="Notes" value={<Text value={current.notes} />} />
            </InfoGrid>
            {manage ? (
              <div className={styles.actions}>
                <Button
                  size="compact"
                  variant="secondary"
                  onClick={() => {
                    setNotice("");
                    setDialog({ kind: "edit", record: current });
                  }}
                >
                  Edit details
                </Button>
                {current.allowedTransitions.map((to) => (
                  <Button
                    key={to}
                    size="compact"
                    variant={to === "Cancelled" ? "danger" : "secondary"}
                    onClick={() => {
                      setNotice("");
                      setDialog({ kind: "transition", record: current, to });
                    }}
                  >
                    {TRANSITION_LABELS[to] || to}
                  </Button>
                ))}
                {canReadDocuments ? (
                  <Button
                    size="compact"
                    variant="secondary"
                    disabled={!documents.data}
                    onClick={() => {
                      setNotice("");
                      setDialog({ kind: "attach", record: current });
                    }}
                  >
                    Attach document
                  </Button>
                ) : null}
              </div>
            ) : null}
            {current.documents.length ? (
              <DataTable
                ariaLabel="Supporting documents"
                density="compact"
                stackOnNarrow
                columns={linkColumns}
                rows={current.documents}
                rowKey={(row) => row.linkId}
              />
            ) : (
              <InlineNotice tone="info" title="No supporting documents">
                Attach visa, permit, or medical documents from the employee’s
                document records.
              </InlineNotice>
            )}
            {timeline.length ? <Timeline compact items={timeline} /> : null}
          </>
        ) : (
          <p className={styles.empty}>
            No current visa or work permit record exists for this employee.
          </p>
        )}
        {data?.history.length ? (
          <DataTable
            ariaLabel="Previous visa records"
            density="compact"
            stackOnNarrow
            columns={historyColumns}
            rows={data.history}
            rowKey={(row) => row.id}
          />
        ) : null}
      </div>

      {dialog ? (
        <CommandFormDialog
          command={command(dialog)}
          record={
            dialog.kind === "edit"
              ? (dialog.record as unknown as DataRecord)
              : undefined
          }
          onClose={() => setDialog(null)}
          onSaved={() =>
            saved(
              dialog.kind === "create"
                ? "Visa record created as Draft."
                : dialog.kind === "edit"
                  ? "Visa details saved."
                  : dialog.kind === "transition"
                    ? `Visa status changed to ${dialog.to}.`
                    : "Supporting document attached.",
            )
          }
        />
      ) : null}
    </SectionCard>
  );
}
