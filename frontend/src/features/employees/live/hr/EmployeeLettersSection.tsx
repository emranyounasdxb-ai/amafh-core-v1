import { useState } from "react";
import {
  Button,
  CompactDateTime,
  ConfirmationDialog,
  DataTable,
  EmptyValue,
  ErrorState,
  InfoField,
  InfoGrid,
  InlineNotice,
  LoadingState,
  OverflowMenu,
  SectionCard,
  Stack,
  StatusBadge,
  TruncatedText,
  type DataTableColumn,
  type MenuItem,
} from "../../../../design-system";
import { reasonField, type Command } from "../../../../app/api/commands";
import { download } from "../../../../app/api/download";
import { useResource } from "../../../../app/api/useResource";
import { CommandFormDialog } from "../../../../app/commands/CommandFormDialog";
import { useSession } from "../../../../app/session/useSession";
import {
  failureMessage,
  hrDocumentStatusTone,
  type HrDocumentItem,
  type HrDocumentList,
} from "./hrRecords";
import styles from "./hrRecords.module.css";

type Pending =
  | { kind: "prepare" }
  | { kind: "cancel" | "void"; item: HrDocumentItem }
  | { kind: "issue" | "approve" | "reissue"; item: HrDocumentItem; key: string };

const UNISSUED = new Set(["Prepared", "Pending Approval"]);

function title(item: HrDocumentItem) {
  return item.nocPurpose ? `${item.label} (${item.nocPurpose})` : item.label;
}

export function EmployeeLettersSection({
  employeeId,
  refreshKey = 0,
}: {
  employeeId: string;
  refreshKey?: number;
}) {
  const { api } = useSession();
  const [localRefresh, setRefresh] = useState(0);
  const refresh = localRefresh + refreshKey;
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState(false);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const [dialogError, setDialogError] = useState("");
  const resource = useResource<HrDocumentList>(
    `/employees/${employeeId}/hr-documents`,
    refresh,
  );
  const data = resource.data;

  const saved = (message: string) => {
    setPending(null);
    setError("");
    setDialogError("");
    setNotice(message);
    setRefresh((value) => value + 1);
  };
  const fetchPdf = async (path: string) => {
    setError("");
    try {
      await download(api, path);
    } catch (failure) {
      setError(failureMessage(failure));
    }
  };
  const open = (next: Pending) => {
    setNotice("");
    setDialogError("");
    setPending(next);
  };
  const keyed = (kind: "issue" | "approve" | "reissue", item: HrDocumentItem) =>
    open({ kind, item, key: crypto.randomUUID() });

  const confirm = async () => {
    if (!pending || busy || !("key" in pending)) return;
    setBusy(true);
    setDialogError("");
    try {
      const result = await api.request<{ documentNumber?: string }>(
        `/hr-documents/${pending.item.id}/${pending.kind}`,
        {
          method: "POST",
          headers:
            pending.kind === "reissue"
              ? { "Idempotency-Key": pending.key }
              : undefined,
        },
      );
      saved(
        pending.kind === "reissue"
          ? `${title(pending.item)} reissued as a new prepared document.`
          : `${title(pending.item)} issued${result?.documentNumber ? ` as ${result.documentNumber}` : ""}.`,
      );
    } catch (failure) {
      setDialogError(failureMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  const actionsFor = (item: HrDocumentItem): MenuItem[] => {
    const items: MenuItem[] = [];
    if (UNISSUED.has(item.status)) {
      items.push({
        id: "preview",
        label: "Preview draft PDF",
        onSelect: () => void fetchPdf(`/hr-documents/${item.id}/preview`),
      });
      if (
        item.status === "Prepared" &&
        !item.requiresApproval &&
        data?.canPrepare
      )
        items.push({
          id: "issue",
          label: "Issue document",
          onSelect: () => keyed("issue", item),
        });
      if (item.requiresApproval && data?.canApprove)
        items.push({
          id: "approve",
          label: "Approve and issue",
          onSelect: () => keyed("approve", item),
        });
      if (data?.canPrepare)
        items.push({
          id: "cancel",
          label: "Cancel request",
          danger: true,
          separator: true,
          onSelect: () => open({ kind: "cancel", item }),
        });
    } else if (item.status === "Issued" || item.status === "Voided") {
      items.push({
        id: "download",
        label: "Download PDF",
        onSelect: () => void fetchPdf(`/hr-documents/${item.id}/file`),
      });
      if (data?.canPrepare)
        items.push({
          id: "reissue",
          label: "Reissue with a new number",
          onSelect: () => keyed("reissue", item),
        });
      if (item.status === "Issued" && data?.canVoid)
        items.push({
          id: "void",
          label: "Void document",
          danger: true,
          separator: true,
          onSelect: () => open({ kind: "void", item }),
        });
    }
    return items;
  };

  const columns: DataTableColumn<HrDocumentItem>[] = [
    {
      key: "document",
      header: "Document",
      width: "220px",
      render: (item) => <TruncatedText value={title(item)} />,
    },
    {
      key: "number",
      header: "Number",
      width: "170px",
      render: (item) =>
        item.documentNumber ? (
          <TruncatedText value={item.documentNumber} />
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "status",
      header: "Status",
      width: "140px",
      render: (item) => (
        <StatusBadge tone={hrDocumentStatusTone(item.status)}>
          {item.status}
        </StatusBadge>
      ),
    },
    {
      key: "addressee",
      header: "Addressee",
      width: "180px",
      render: (item) =>
        item.addressee ? (
          <TruncatedText value={item.addressee} />
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "prepared",
      header: "Prepared",
      kind: "datetime",
      width: "150px",
      render: (item) => <CompactDateTime value={item.preparedAt} />,
    },
    {
      key: "issued",
      header: "Issued",
      kind: "datetime",
      width: "150px",
      render: (item) =>
        item.issuedAt ? (
          <CompactDateTime value={item.issuedAt} />
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "note",
      header: "Note",
      width: "200px",
      render: (item) => {
        const text =
          item.voidReason ||
          item.cancelReason ||
          (item.reissueOfNumber ? `Reissue of ${item.reissueOfNumber}` : "");
        return text ? <TruncatedText value={text} /> : <EmptyValue />;
      },
    },
    {
      key: "actions",
      header: "Actions",
      width: "80px",
      fixed: true,
      render: (item) => {
        const items = actionsFor(item);
        return items.length ? (
          <OverflowMenu label={`Actions for ${title(item)}`} items={items} />
        ) : (
          <EmptyValue />
        );
      },
    },
  ];

  const eligible = data?.eligibleTypes ?? [];
  const blocked = eligible.filter((kind) => kind.issuanceBlockers.length);
  const prepareCommand: Command = {
    title: "Prepare letter or certificate",
    path: `/employees/${employeeId}/hr-documents`,
    idempotent: true,
    submitLabel: "Prepare",
    fields: [
      {
        key: "documentType",
        label: "Document",
        required: true,
        options: eligible.map((kind) => kind.documentType),
        optionLabels: Object.fromEntries(
          eligible.map((kind) => [
            kind.documentType,
            kind.requiresApproval
              ? `${kind.label} (Owner approval)`
              : kind.label,
          ]),
        ),
        clearOnChange: ["nocPurpose"],
      },
      {
        key: "nocPurpose",
        label: "NOC purpose",
        required: true,
        options: ["Travel", "Bank", "Visa"],
        show: (values) => values.documentType === "noc",
      },
      {
        key: "addressee",
        label: "Addressee",
        required: true,
        max: 200,
        show: (values) =>
          Boolean(values.documentType) &&
          values.documentType !== "experience_certificate",
      },
      {
        key: "purpose",
        label: "Purpose",
        type: "textarea",
        required: true,
        max: 500,
        show: (values) =>
          Boolean(values.documentType) &&
          values.documentType !== "experience_certificate",
      },
    ],
    confirmation: {
      description:
        "Salary letters, salary transfer letters, experience certificates, and any letter whose wording includes salary or package details require Owner approval before issue. Other letters are issued by HR. Official numbers are assigned only at issue.",
      facts: [],
    },
  };

  return (
    <SectionCard
      compact
      title="Letters and certificates"
      description="Server-generated A4 PDFs. Official numbers are assigned at issue and never reused."
      actions={
        data?.canPrepare && eligible.length ? (
          <Button
            size="compact"
            variant="secondary"
            onClick={() => open({ kind: "prepare" })}
          >
            Prepare document
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
          <LoadingState title="Loading letters and certificates" />
        ) : resource.error && !data ? (
          <ErrorState description={resource.error} retry={resource.reload} />
        ) : data ? (
          <>
            {blocked.length ? (
              <div>
                <InlineNotice
                  tone="warning"
                  title={`Official issuance blocked (${blocked.length} document types)`}
                >
                  Resolve the existing restrictions before issuing these
                  documents.
                </InlineNotice>
                <details className={styles.warningDetails}>
                  <summary>View details</summary>
                  <ul className={styles.warningList}>
                    {blocked.map((kind) => (
                      <li key={kind.documentType}>
                        {kind.label}: {kind.issuanceBlockers.join("; ")}
                      </li>
                    ))}
                  </ul>
                </details>
              </div>
            ) : null}
            {!eligible.length ? (
              <InlineNotice tone="info" title="Not eligible">
                Letters are available for Active employees. The experience
                certificate is available after offboarding.
              </InlineNotice>
            ) : null}
            {data.items.length ? (
              <DataTable
                ariaLabel="Letters and certificates"
                density="compact"
                stackOnNarrow
                columns={columns}
                rows={data.items}
                rowKey={(item) => item.id}
              />
            ) : (
              <p className={styles.empty}>
                No letter or certificate has been prepared for this employee.
              </p>
            )}
          </>
        ) : null}
      </div>

      {pending?.kind === "prepare" ? (
        <CommandFormDialog
          command={prepareCommand}
          onClose={() => setPending(null)}
          onSaved={(value) =>
            saved(
              (value as { status?: string })?.status === "Pending Approval"
                ? "Prepared and sent to the Owner for approval."
                : "Prepared. Preview the draft before issuing.",
            )
          }
        />
      ) : null}

      {pending?.kind === "cancel" || pending?.kind === "void" ? (
        <CommandFormDialog
          command={{
            title:
              pending.kind === "void"
                ? `Void ${pending.item.documentNumber}`
                : `Cancel ${title(pending.item)}`,
            path: `/hr-documents/${pending.item.id}/${pending.kind}`,
            submitLabel:
              pending.kind === "void" ? "Void document" : "Cancel request",
            fields: [reasonField],
            confirmation: {
              description:
                pending.kind === "void"
                  ? "The issued PDF is kept and marked as voided. Its number is never reused."
                  : "The unissued request is closed. No number has been assigned.",
              facts: [
                { label: "Document", value: title(pending.item) },
                ...(pending.item.documentNumber
                  ? [{ label: "Number", value: pending.item.documentNumber }]
                  : []),
              ],
            },
          }}
          onClose={() => setPending(null)}
          onSaved={() =>
            saved(
              pending.kind === "void"
                ? `${pending.item.documentNumber} voided.`
                : "Request cancelled.",
            )
          }
        />
      ) : null}

      {pending && "key" in pending ? (
        <ConfirmationDialog
          open
          title={
            pending.kind === "reissue"
              ? "Reissue document"
              : pending.kind === "approve"
                ? "Approve and issue"
                : "Issue document"
          }
          confirmLabel={
            pending.kind === "reissue"
              ? "Prepare reissue"
              : pending.kind === "approve"
                ? "Approve and issue"
                : "Issue document"
          }
          busy={busy}
          onClose={() => {
            if (!busy) setPending(null);
          }}
          onConfirm={() => void confirm()}
        >
          <Stack>
            <p>
              {pending.kind === "reissue"
                ? "A new request is prepared from this document. It receives a new number when issued; the original stays unchanged."
                : "The official PDF is generated now with the approved wording and company details, and the next number is assigned permanently."}
            </p>
            <InfoGrid>
              <InfoField label="Document" value={title(pending.item)} />
              <InfoField
                label="Addressee"
                value={pending.item.addressee || <EmptyValue />}
              />
              {pending.item.documentNumber ? (
                <InfoField label="Number" value={pending.item.documentNumber} />
              ) : null}
            </InfoGrid>
            {dialogError ? (
              <InlineNotice tone="error" title="Unable to continue">
                {dialogError}
              </InlineNotice>
            ) : null}
          </Stack>
        </ConfirmationDialog>
      ) : null}
    </SectionCard>
  );
}
