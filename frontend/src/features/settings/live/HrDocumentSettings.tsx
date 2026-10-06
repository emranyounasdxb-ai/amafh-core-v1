import { useState } from "react";
import {
  Button,
  CompactDateTime,
  ConfirmationDialog,
  DataTable,
  Dialog,
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
  Switch,
  TruncatedText,
  type DataTableColumn,
  type MenuItem,
} from "../../../design-system";
import type { Command } from "../../../app/api/commands";
import type { DataRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { CommandFormDialog } from "../../../app/commands/CommandFormDialog";
import { useSession } from "../../../app/session/useSession";
import {
  failureMessage,
  type DocumentType,
  type HrDocumentSettings as Settings,
  type HrTemplate,
} from "../../employees/live/hr/hrRecords";
import styles from "./SettingsPage.module.css";

type TemplateRow = Settings["templates"][number];
type Pending =
  | { kind: "company" }
  | { kind: "draft"; row: TemplateRow }
  | { kind: "approve"; row: TemplateRow; template: HrTemplate }
  | { kind: "view"; row: TemplateRow };

const SALARY_FREE = new Set(["experience_certificate"]);

const TEMPLATE_TONE = {
  Draft: "warning",
  Approved: "success",
  Retired: "neutral",
} as const;

function Value({ value }: { value: string | null }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function Wording({ template }: { template: HrTemplate }) {
  return (
    <Stack>
      <InfoGrid>
        <InfoField label="Title" value={template.title} />
        <InfoField
          label="Status"
          value={
            <StatusBadge tone={TEMPLATE_TONE[template.status]}>
              {`${template.status} · version ${template.version}`}
            </StatusBadge>
          }
        />
      </InfoGrid>
      <p className={styles.wording}>{template.body}</p>
    </Stack>
  );
}

export function HrDocumentSettings() {
  const { api, session } = useSession();
  const [refresh, setRefresh] = useState(0);
  const [pending, setPending] = useState<Pending | null>(null);
  const [busy, setBusy] = useState("");
  const [notice, setNotice] = useState("");
  const [error, setError] = useState("");
  const settings = useResource<Settings>("/hr-document-settings", refresh);
  const types = useResource<DocumentType[]>("/employee-document-types", refresh);
  if (session?.designation !== "Owner") return null;
  const data = settings.data;

  const saved = (message: string) => {
    setPending(null);
    setError("");
    setNotice(message);
    setRefresh((value) => value + 1);
  };

  const approve = async (template: HrTemplate) => {
    setBusy(template.id);
    setError("");
    try {
      await api.request(`/hr-document-templates/${template.id}/approve`, {
        method: "POST",
      });
      saved(`Wording version ${template.version} approved.`);
    } catch (failure) {
      setError(failureMessage(failure));
      setPending(null);
    } finally {
      setBusy("");
    }
  };

  const toggle = async (type: DocumentType, required: boolean) => {
    setBusy(type.id);
    setError("");
    setNotice("");
    try {
      await api.request(`/employee-document-types/${type.id}`, {
        method: "PATCH",
        body: JSON.stringify({ requiredAtOnboarding: required }),
      });
      saved(
        `${type.name} is ${required ? "now" : "no longer"} required at onboarding.`,
      );
    } catch (failure) {
      setError(failureMessage(failure));
    } finally {
      setBusy("");
    }
  };

  const companyCommand: Command = {
    title: "Edit company details",
    path: "/hr-document-settings/company",
    method: "PUT",
    fields: [
      { key: "companyLegalName", label: "Company legal name", max: 200 },
      {
        key: "companyAddress",
        label: "Company address",
        type: "textarea",
        max: 500,
      },
      { key: "tradeLicenseNumber", label: "Trade licence number", max: 80 },
      { key: "signatoryName", label: "Authorized signatory name", max: 200 },
      {
        key: "signatoryDesignation",
        label: "Authorized signatory designation",
        max: 120,
      },
    ],
    confirmation: {
      description:
        "These details print on every official letter and certificate. Enter only approved company information.",
      facts: [],
    },
  };

  const draftCommand = (row: TemplateRow): Command => ({
    title: `Draft wording · ${row.label}`,
    path: `/hr-document-templates/${row.documentType}/drafts`,
    submitLabel: "Save draft",
    fields: [
      { key: "title", label: "Document title", required: true, max: 200 },
      {
        key: "body",
        label: "Wording",
        type: "textarea",
        required: true,
        max: 8000,
      },
    ],
    confirmation: {
      description: SALARY_FREE.has(row.documentType)
        ? "Use {{placeholder}} values below. Salary placeholders are not allowed for this document. A new draft is not used until approved."
        : "Use {{placeholder}} values below. Salary placeholders are allowed; every letter issued with salary or package details requires Owner approval. A new draft is not used until approved.",
      facts: (data?.placeholders ?? [])
        .filter((item) => !SALARY_FREE.has(row.documentType) || !item.salary)
        .map((item) => ({
          label: `{{${item.key}}}`,
          value: item.description,
        })),
    },
  });

  const actionsFor = (row: TemplateRow): MenuItem[] => {
    const items: MenuItem[] = [];
    if (row.latest)
      items.push({
        id: "view",
        label: "View wording",
        onSelect: () => setPending({ kind: "view", row }),
      });
    items.push({
      id: "draft",
      label: "Draft new wording",
      onSelect: () => {
        setNotice("");
        setPending({ kind: "draft", row });
      },
    });
    if (row.latest?.status === "Draft")
      items.push({
        id: "approve",
        label: `Approve version ${row.latest.version}`,
        onSelect: () => {
          setNotice("");
          setPending({ kind: "approve", row, template: row.latest! });
        },
      });
    return items;
  };

  const templateColumns: DataTableColumn<TemplateRow>[] = [
    {
      key: "document",
      header: "Document",
      width: "220px",
      render: (row) => <TruncatedText value={row.label} />,
    },
    {
      key: "approval",
      header: "Issued by",
      width: "160px",
      render: (row) => (row.requiresApproval ? "Owner approval" : "HR"),
    },
    {
      key: "approved",
      header: "Approved wording",
      width: "160px",
      render: (row) =>
        row.approved ? (
          <StatusBadge tone="success">{`Version ${row.approved.version}`}</StatusBadge>
        ) : (
          <StatusBadge tone="warning">Not approved</StatusBadge>
        ),
    },
    {
      key: "latest",
      header: "Latest version",
      width: "160px",
      render: (row) =>
        row.latest ? (
          <StatusBadge tone={TEMPLATE_TONE[row.latest.status]}>
            {`${row.latest.status} · v${row.latest.version}`}
          </StatusBadge>
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "updated",
      header: "Last change",
      kind: "datetime",
      width: "150px",
      render: (row) =>
        row.latest ? (
          <CompactDateTime
            value={row.latest.approvedAt || row.latest.createdAt}
          />
        ) : (
          <EmptyValue />
        ),
    },
    {
      key: "actions",
      header: "Actions",
      width: "80px",
      fixed: true,
      render: (row) => (
        <OverflowMenu label={`Actions for ${row.label}`} items={actionsFor(row)} />
      ),
    },
  ];

  if (settings.loading && !data)
    return <LoadingState title="Loading HR document settings" />;
  if (settings.error && !data)
    return <ErrorState description={settings.error} retry={settings.reload} />;
  if (!data) return null;

  return (
    <Stack>
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

      <SectionCard
        compact
        title="Company details"
        description="Printed on official HR letters and certificates."
        actions={
          <Button
            size="compact"
            variant="secondary"
            onClick={() => {
              setNotice("");
              setPending({ kind: "company" });
            }}
          >
            Edit details
          </Button>
        }
      >
        <Stack>
          {data.missingCompanyDetails.length ? (
            <InlineNotice tone="warning" title="Official issuance blocked">
              Missing: {data.missingCompanyDetails.join(", ")}. Drafts can be
              previewed but cannot be issued.
            </InlineNotice>
          ) : null}
          <InfoGrid>
            <InfoField
              label="Company legal name"
              value={<Value value={data.company.companyLegalName} />}
            />
            <InfoField
              label="Company address"
              value={<Value value={data.company.companyAddress} />}
            />
            <InfoField
              label="Trade licence number"
              value={<Value value={data.company.tradeLicenseNumber} />}
            />
            <InfoField
              label="Authorized signatory"
              value={<Value value={data.company.signatoryName} />}
            />
            <InfoField
              label="Signatory designation"
              value={<Value value={data.company.signatoryDesignation} />}
            />
            <InfoField
              label="Last updated"
              value={
                data.company.updatedAt ? (
                  <CompactDateTime value={data.company.updatedAt} />
                ) : (
                  <EmptyValue />
                )
              }
            />
          </InfoGrid>
        </Stack>
      </SectionCard>

      <SectionCard
        compact
        title="Letter and certificate wording"
        description="Wording is versioned. Only approved wording is used for official issue."
      >
        <DataTable
          ariaLabel="Letter and certificate wording"
          density="compact"
          stackOnNarrow
          columns={templateColumns}
          rows={data.templates}
          rowKey={(row) => row.documentType}
        />
      </SectionCard>

      <SectionCard
        compact
        title="Required employee documents"
        description="Shown as a checklist on employee records. Missing documents do not block activation."
      >
        {types.loading && !types.data ? (
          <LoadingState title="Loading document types" />
        ) : types.error && !types.data ? (
          <ErrorState description={types.error} retry={types.reload} />
        ) : (
          <Stack>
            {(types.data ?? []).map((type) => (
              <Switch
                key={type.id}
                id={`document-required-${type.code}`}
                label={type.name}
                checked={type.requiredAtOnboarding}
                disabled={Boolean(busy)}
                onChange={(checked) => void toggle(type, checked)}
              />
            ))}
          </Stack>
        )}
      </SectionCard>

      {pending?.kind === "company" ? (
        <CommandFormDialog
          command={companyCommand}
          record={data.company as unknown as DataRecord}
          onClose={() => setPending(null)}
          onSaved={() => saved("Company details saved.")}
        />
      ) : null}
      {pending?.kind === "draft" ? (
        <CommandFormDialog
          command={draftCommand(pending.row)}
          record={(pending.row.latest ?? {}) as unknown as DataRecord}
          onClose={() => setPending(null)}
          onSaved={() => saved(`Draft wording saved for ${pending.row.label}.`)}
        />
      ) : null}
      {pending?.kind === "approve" ? (
        <ConfirmationDialog
          open
          title={`Approve wording · ${pending.row.label}`}
          confirmLabel="Approve wording"
          busy={busy === pending.template.id}
          onClose={() => {
            if (!busy) setPending(null);
          }}
          onConfirm={() => void approve(pending.template)}
        >
          <Stack>
            <p>
              Approved wording is used for every official issue of this
              document. Any earlier approved version is retired.
            </p>
            <Wording template={pending.template} />
          </Stack>
        </ConfirmationDialog>
      ) : null}
      {pending?.kind === "view" && pending.row.latest ? (
        <Dialog
          open
          size="lg"
          title={`Wording · ${pending.row.label}`}
          onClose={() => setPending(null)}
          footer={
            <Button variant="secondary" onClick={() => setPending(null)}>
              Close
            </Button>
          }
        >
          <Stack>
            <Wording template={pending.row.latest} />
            {pending.row.approved &&
            pending.row.approved.id !== pending.row.latest.id ? (
              <>
                <InlineNotice tone="info" title="Currently approved">
                  Version {pending.row.approved.version} stays in use until the
                  newer draft is approved.
                </InlineNotice>
                <Wording template={pending.row.approved} />
              </>
            ) : null}
          </Stack>
        </Dialog>
      ) : null}
    </Stack>
  );
}
