import { useState } from "react";
import {
  Button,
  CompactDate,
  CompactDateTime,
  DataTable,
  Dialog,
  EmptyState,
  EmptyValue,
  ErrorState,
  InfoField,
  InfoGrid,
  InlineNotice,
  LoadingState,
  OverflowMenu,
  SectionCard,
  StatusBadge,
  TruncatedText,
  type DataTableColumn,
  type MenuItem,
} from "../../../../design-system";
import { reasonField } from "../../../../app/api/commands";
import { download } from "../../../../app/api/download";
import { useResource } from "../../../../app/api/useResource";
import { CommandFormDialog } from "../../../../app/commands/CommandFormDialog";
import { useSession } from "../../../../app/session/useSession";
import { DocumentUploadDialog } from "./DocumentUploadDialog";
import {
  documentStatusTone,
  failureMessage,
  fileSizeLabel,
  type DocumentList,
  type DocumentSeries,
  type DocumentVersion,
} from "./hrRecords";
import styles from "./hrRecords.module.css";

function Expiry({ version }: { version: DocumentVersion }) {
  if (!version.expiryDate) return <EmptyValue />;
  return (
    <span className={styles.inline}>
      <CompactDate value={version.expiryDate} />
      {version.expired && version.status === "Current" ? (
        <StatusBadge tone="danger">Expired</StatusBadge>
      ) : null}
    </span>
  );
}

export function EmployeeDocumentsSection({
  employeeId,
  employeeStatus,
}: {
  employeeId: string;
  employeeStatus: string;
}) {
  const { api } = useSession();
  const [refresh, setRefresh] = useState(0);
  const [uploading, setUploading] = useState(false);
  const [replacing, setReplacing] = useState<DocumentSeries | null>(null);
  const [withdrawing, setWithdrawing] = useState<DocumentSeries | null>(null);
  const [versionsOf, setVersionsOf] = useState<DocumentSeries | null>(null);
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const resource = useResource<DocumentList>(
    `/employees/${employeeId}/documents`,
    refresh,
  );
  const data = resource.data;
  const active = employeeStatus !== "Offboarded";
  const canUpload = Boolean(data?.canUpload) && active;

  const saved = (message: string) => {
    setUploading(false);
    setReplacing(null);
    setWithdrawing(null);
    setError("");
    setNotice(message);
    setRefresh((value) => value + 1);
  };
  const fetchVersion = async (version: DocumentVersion) => {
    setError("");
    try {
      await download(api, `/employee-document-versions/${version.id}/file`);
    } catch (failure) {
      setError(failureMessage(failure));
    }
  };

  const actionsFor = (row: DocumentSeries): MenuItem[] => {
    const items: MenuItem[] = [
      {
        id: "download",
        label: `Download version ${row.latest.version}`,
        onSelect: () => void fetchVersion(row.latest),
      },
      {
        id: "versions",
        label: "View versions",
        onSelect: () => setVersionsOf(row),
      },
    ];
    if (canUpload && row.status === "Current")
      items.push({
        id: "replace",
        label: "Replace with new version",
        onSelect: () => {
          setNotice("");
          setReplacing(row);
        },
      });
    if (data?.canWithdraw && row.status === "Current")
      items.push({
        id: "withdraw",
        label: "Withdraw document",
        danger: true,
        separator: true,
        onSelect: () => {
          setNotice("");
          setWithdrawing(row);
        },
      });
    return items;
  };

  const columns: DataTableColumn<DocumentSeries>[] = [
    {
      key: "type",
      header: "Document",
      width: "200px",
      render: (row) => <TruncatedText value={row.typeName} />,
    },
    {
      key: "status",
      header: "Status",
      width: "112px",
      render: (row) => (
        <StatusBadge tone={documentStatusTone(row.status)}>
          {row.status}
        </StatusBadge>
      ),
    },
    {
      key: "number",
      header: "Number",
      width: "160px",
      render: (row) =>
        row.latest.documentNumber ? (
          <TruncatedText value={row.latest.documentNumber} />
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "issue",
      header: "Issue date",
      kind: "date",
      width: "120px",
      render: (row) =>
        row.latest.issueDate ? (
          <CompactDate value={row.latest.issueDate} />
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "expiry",
      header: "Expiry date",
      kind: "date",
      width: "170px",
      render: (row) => <Expiry version={row.latest} />,
    },
    {
      key: "version",
      header: "Version",
      kind: "number",
      width: "88px",
      render: (row) => row.latest.version,
    },
    {
      key: "uploaded",
      header: "Uploaded",
      kind: "datetime",
      width: "150px",
      render: (row) => <CompactDateTime value={row.latest.uploadedAt} />,
    },
    {
      key: "actions",
      header: "Actions",
      width: "80px",
      fixed: true,
      render: (row) => (
        <OverflowMenu
          label={`Actions for ${row.typeName}`}
          items={actionsFor(row)}
        />
      ),
    },
  ];

  const versionColumns: DataTableColumn<DocumentVersion>[] = [
    {
      key: "version",
      header: "Version",
      kind: "number",
      width: "88px",
      render: (row) => row.version,
    },
    {
      key: "status",
      header: "Status",
      width: "112px",
      render: (row) => (
        <StatusBadge tone={documentStatusTone(row.status)}>
          {row.status}
        </StatusBadge>
      ),
    },
    {
      key: "file",
      header: "File",
      width: "220px",
      render: (row) => (
        <TruncatedText
          value={`${row.originalFilename} · ${fileSizeLabel(row.byteSize)}`}
        />
      ),
    },
    {
      key: "expiry",
      header: "Expiry date",
      kind: "date",
      width: "150px",
      render: (row) => <Expiry version={row} />,
    },
    {
      key: "uploadedBy",
      header: "Uploaded by",
      width: "150px",
      render: (row) => (
        <TruncatedText value={row.uploadedByName || "Team member"} />
      ),
    },
    {
      key: "uploadedAt",
      header: "Uploaded at",
      kind: "datetime",
      width: "150px",
      render: (row) => <CompactDateTime value={row.uploadedAt} />,
    },
    {
      key: "download",
      header: "File",
      width: "112px",
      fixed: true,
      render: (row) => (
        <Button
          size="compact"
          variant="ghost"
          onClick={() => void fetchVersion(row)}
        >
          Download
        </Button>
      ),
    },
  ];

  const missing = data?.checklist.filter((item) => !item.satisfied) ?? [];
  return (
    <SectionCard
      compact
      title="Documents"
      description="Protected employee documents. Replacements keep earlier versions as read-only history."
      actions={
        canUpload ? (
          <Button
            size="compact"
            variant="secondary"
            onClick={() => {
              setNotice("");
              setUploading(true);
            }}
          >
            Upload document
          </Button>
        ) : undefined
      }
    >
      <div className={styles.stack}>
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
          <LoadingState title="Loading documents" />
        ) : resource.error && !data ? (
          <ErrorState description={resource.error} retry={resource.reload} />
        ) : data ? (
          <>
            {data.checklist.length ? (
              <InfoGrid>
                {data.checklist.map((item) => (
                  <InfoField
                    key={item.typeId}
                    label={item.typeName}
                    value={
                      <StatusBadge
                        tone={item.satisfied ? "success" : "warning"}
                      >
                        {item.satisfied ? "On file" : "Missing"}
                      </StatusBadge>
                    }
                  />
                ))}
              </InfoGrid>
            ) : null}
            {missing.length ? (
              <InlineNotice tone="warning" title="Required documents missing">
                {missing.map((item) => item.typeName).join(", ")}. Missing
                documents do not block activation.
              </InlineNotice>
            ) : null}
            {data.documents.length ? (
              <DataTable
                ariaLabel="Employee documents"
                density="compact"
                stackOnNarrow
                columns={columns}
                rows={data.documents}
                rowKey={(row) => row.seriesId}
              />
            ) : (
              <EmptyState
                title="No documents"
                description="No documents have been uploaded for this employee."
              />
            )}
          </>
        ) : null}
      </div>

      {data && (uploading || replacing) ? (
        <DocumentUploadDialog
          employeeId={employeeId}
          types={data.types}
          documents={data.documents}
          replacing={replacing ?? undefined}
          onClose={() => {
            setUploading(false);
            setReplacing(null);
          }}
          onSaved={saved}
        />
      ) : null}

      {withdrawing ? (
        <CommandFormDialog
          command={{
            title: `Withdraw ${withdrawing.typeName}`,
            path: `/employee-documents/${withdrawing.seriesId}/withdraw`,
            submitLabel: "Withdraw document",
            fields: [reasonField],
            confirmation: {
              description:
                "The current version becomes Withdrawn and read-only. The file and its history are kept; nothing is deleted.",
              facts: [
                { label: "Document", value: withdrawing.typeName },
                {
                  label: "Version",
                  value: String(withdrawing.latest.version),
                },
              ],
            },
          }}
          onClose={() => setWithdrawing(null)}
          onSaved={() => saved(`${withdrawing.typeName} withdrawn.`)}
        />
      ) : null}

      {versionsOf ? (
        <Dialog
          open
          size="lg"
          title={`${versionsOf.typeName} versions`}
          onClose={() => setVersionsOf(null)}
          footer={
            <Button variant="secondary" onClick={() => setVersionsOf(null)}>
              Close
            </Button>
          }
        >
          <div className={styles.stack}>
            {versionsOf.latest.status === "Withdrawn" ? (
              <InlineNotice tone="info" title="Withdrawn">
                {versionsOf.latest.withdrawalReason || "Reason not recorded"}
                {versionsOf.latest.withdrawnByName
                  ? ` · ${versionsOf.latest.withdrawnByName}`
                  : ""}
              </InlineNotice>
            ) : null}
            <DataTable
              ariaLabel={`${versionsOf.typeName} versions`}
              density="compact"
              stackOnNarrow
              columns={versionColumns}
              rows={versionsOf.versions}
              rowKey={(row) => row.id}
            />
          </div>
        </Dialog>
      ) : null}
    </SectionCard>
  );
}
