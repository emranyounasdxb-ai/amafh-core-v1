import { useState } from "react";
import {
  FileUpload,
  InlineNotice,
  SectionCard,
  Stack,
  type AppliedFilter,
} from "../../../design-system";
import {
  bankField,
  offeredProductField,
  productField,
  type Field,
} from "../../../app/api/commands";
import { ApiFailure } from "../../../app/api/http";
import { useSession } from "../../../app/session/useSession";
import {
  filterQuery,
  useServerTable,
  type ServerColumn,
} from "../../../shared/table/serverTable";
import { SelectFilter } from "../../finance/live/financeCells";
import {
  stateAction,
  type SettingsAction,
  type SettingsFact,
} from "./settingsActions";
import { ActiveBadge, Text } from "./settingsCells";
import { canManageSettings } from "./settingsRegistry";
import { SettingsTable } from "./SettingsTable";
import { useNamedRecords } from "./useNamedRecords";
import styles from "./SettingsPage.module.css";
import {
  recordImageSrc,
  uploadRecordImage,
  type ImageKind,
} from "../../../app/api/recordImages";
import {
  RecordImage,
  RecordImageLabel,
} from "../../../shared/media/RecordImage";

export type CatalogKind =
  "banks" | "product-types" | "bank-product-mappings" | "product-variants";

type CatalogRecord = {
  id: string;
  name?: string;
  code?: string;
  bank_code?: string;
  bank_id?: string;
  product_type_id?: string;
  logo_file_id?: string | null;
  image_file_id?: string | null;
  active: boolean;
};

const STATUSES = [
  { value: "true", label: "Active" },
  { value: "false", label: "Inactive" },
];
const nameField: Field = {
  key: "name",
  label: "Name",
  required: true,
  max: 150,
};

const COPY: Record<
  CatalogKind,
  { noun: string; kind: string; plural: string; add: string; empty: string }
> = {
  banks: {
    noun: "bank",
    kind: "Bank",
    plural: "Banks",
    add: "Add Bank",
    empty: "Banks are offered on cases, rules, and pipelines.",
  },
  "product-types": {
    noun: "product",
    kind: "Product",
    plural: "Products",
    add: "Add Product",
    empty: "Products are offered by banks through bank products.",
  },
  "bank-product-mappings": {
    noun: "bank product",
    kind: "Bank product",
    plural: "Bank products",
    add: "Add Bank Product",
    empty: "A bank product links a bank to a product it offers.",
  },
  "product-variants": {
    noun: "product variant",
    kind: "Product variant",
    plural: "Product variants",
    add: "Add Product Variant",
    empty: "Variants belong to an active bank product.",
  },
};

export function CatalogSettings({ kind }: { kind: CatalogKind }) {
  const { session } = useSession();
  const manage = canManageSettings(session, "pipeline.write");
  const copy = COPY[kind];
  const linked = kind === "bank-product-mappings" || kind === "product-variants";
  const [refresh, setRefresh] = useState(0);
  const empty = { active: "", bankId: "", productTypeId: "" };
  const [filters, setFilters] = useState(empty);
  const set = (patch: Partial<typeof empty>) =>
    setFilters((current) => ({ ...current, ...patch }));
  const tableId = `settings-${kind}`;
  const table = useServerTable<CatalogRecord>(
    tableId,
    `/catalog/${kind}`,
    filterQuery(filters),
    refresh,
  );
  const banks = useNamedRecords(linked ? "/catalog/banks" : null, refresh);
  const products = useNamedRecords(
    linked ? "/catalog/product-types" : null,
    refresh,
  );
  const applied = [
    filters.active && {
      id: "status",
      label: "Status",
      field: "Status",
      value: filters.active === "true" ? "Active" : "Inactive",
      onRemove: () => set({ active: "" }),
    },
    filters.bankId && {
      id: "bank",
      label: "Bank",
      field: "Bank",
      value: banks.label(filters.bankId, "Selected bank"),
      onRemove: () => set({ bankId: "" }),
    },
    filters.productTypeId && {
      id: "product",
      label: "Product",
      field: "Product",
      value: products.label(filters.productTypeId, "Selected product"),
      onRemove: () => set({ productTypeId: "" }),
    },
  ].filter(Boolean) as AppliedFilter[];

  const label = (row: CatalogRecord) =>
    kind === "bank-product-mappings"
      ? `${banks.label(row.bank_id)} · ${products.label(row.product_type_id)}`
      : row.name || copy.kind;
  const imageLabel = (row: CatalogRecord) => (
    <RecordImageLabel
      src={recordImageSrc(kind as ImageKind, row)}
      label={label(row)}
    />
  );
  const status: ServerColumn<CatalogRecord> = {
    key: "active",
    label: "Status",
    width: 110,
    render: (row) => <ActiveBadge active={row.active} />,
  };
  const bankColumn: ServerColumn<CatalogRecord> = {
    key: "bank_id",
    label: "Bank",
    width: 180,
    render: (row) => (
      <RecordImageLabel
        label={banks.label(row.bank_id)}
        src={banks.image(row.bank_id)}
      />
    ),
  };
  const productColumn: ServerColumn<CatalogRecord> = {
    key: "product_type_id",
    label: "Product",
    width: 180,
    render: (row) => (
      <RecordImageLabel
        label={products.label(row.product_type_id)}
        src={products.image(row.product_type_id)}
      />
    ),
  };
  const columns: ServerColumn<CatalogRecord>[] =
    kind === "banks"
      ? [
          { key: "name", label: "Bank", width: 220, render: imageLabel },
          {
            key: "bank_code",
            label: "Bank code",
            width: 140,
            render: (row) => <Text value={row.bank_code} />,
          },
          status,
        ]
      : kind === "product-types"
        ? [
            { key: "name", label: "Product", width: 220, render: imageLabel },
            {
              key: "code",
              label: "Product code",
              width: 140,
              render: (row) => <Text value={row.code} />,
            },
            status,
          ]
        : kind === "product-variants"
          ? [
              { key: "name", label: "Variant", width: 220, render: imageLabel },
              bankColumn,
              productColumn,
              status,
            ]
          : [bankColumn, productColumn, status];

  const facts = (row: CatalogRecord): SettingsFact[] => [
    ...(row.name ? [{ label: copy.kind, value: <Text value={row.name} /> }] : []),
    ...(kind === "banks"
      ? [{ label: "Bank code", value: <Text value={row.bank_code} /> }]
      : []),
    ...(kind === "product-types"
      ? [{ label: "Product code", value: <Text value={row.code} /> }]
      : []),
    ...(linked
      ? [
          { label: "Bank", value: <Text value={banks.label(row.bank_id)} /> },
          {
            label: "Product",
            value: <Text value={products.label(row.product_type_id)} />,
          },
        ]
      : []),
    { label: "Status", value: <ActiveBadge active={row.active} /> },
  ];

  const createFields: Field[] =
    kind === "banks"
      ? [nameField]
      : kind === "product-types"
        ? [
            { key: "code", label: "Product code", required: true, max: 20 },
            nameField,
          ]
        : kind === "product-variants"
          ? [bankField, offeredProductField, nameField]
          : [bankField, productField];

  const actions = (row: CatalogRecord): SettingsAction[] => [
    ...(kind !== "bank-product-mappings"
      ? [
          {
            id: "rename",
            label: "Rename",
            success: `${copy.kind} renamed.`,
            command: {
              title: `Rename ${copy.kind}`,
              path: `/catalog/${kind}/${row.id}`,
              method: "PATCH" as const,
              fields: [nameField],
              imageUpload: {
                kind: kind as ImageKind,
                label: kind === "banks" ? "Bank logo" : `${copy.kind} image`,
              },
            },
            record: row,
          },
        ]
      : []),
    stateAction(copy.noun, `/catalog/${kind}/${row.id}`, row.active),
  ];

  return (
    <SettingsTable
      table={table}
      tableId={tableId}
      ariaLabel={copy.plural}
      kind={copy.kind}
      loadingTitle={`Loading ${copy.plural.toLowerCase()}`}
      emptyTitle={`No ${copy.plural.toLowerCase()}`}
      emptyDescription={copy.empty}
      filters={
        <>
          <SelectFilter
            id={`${tableId}-status`}
            label="Status"
            placeholder="All statuses"
            value={filters.active}
            options={STATUSES}
            onChange={(active) => set({ active })}
          />
          {linked ? (
            <>
              <SelectFilter
                id={`${tableId}-bank`}
                label="Bank"
                placeholder="All banks"
                value={filters.bankId}
                options={banks.options()}
                loading={banks.loading}
                onChange={(bankId) => set({ bankId })}
              />
              <SelectFilter
                id={`${tableId}-product`}
                label="Product"
                placeholder="All products"
                value={filters.productTypeId}
                options={products.options()}
                loading={products.loading}
                onChange={(productTypeId) => set({ productTypeId })}
              />
            </>
          ) : null}
        </>
      }
      applied={applied}
      onClearFilters={() => setFilters(empty)}
      columns={columns}
      rowLabel={label}
      title={label}
      facts={facts}
      detail={
        kind === "bank-product-mappings"
          ? undefined
          : (row) => (
              <CatalogImage
                key={row.id}
                kind={kind as ImageKind}
                row={row}
                title={kind === "banks" ? "Logo" : "Image"}
                canWrite={manage}
                onSaved={() => setRefresh((value) => value + 1)}
              />
            )
      }
      create={
        manage
          ? {
              label: copy.add,
              success: `${copy.kind} added.`,
              command: {
                title: copy.add,
                path: `/catalog/${kind}`,
                fields: createFields,
                imageUpload:
                  kind === "bank-product-mappings"
                    ? undefined
                    : {
                        kind: kind as ImageKind,
                        label:
                          kind === "banks" ? "Bank logo" : `${copy.kind} image`,
                      },
              },
            }
          : undefined
      }
      actions={manage ? actions : undefined}
      onSaved={() => setRefresh((value) => value + 1)}
    />
  );
}

function CatalogImage({
  kind,
  row,
  title,
  canWrite,
  onSaved,
}: {
  kind: ImageKind;
  row: CatalogRecord;
  title: string;
  canWrite: boolean;
  onSaved: () => void;
}) {
  const { api } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [fileId, setFileId] = useState<string | null>(null);
  const [files, setFiles] = useState<FileList | null>(null);
  const upload = async (next: FileList | null) => {
    setFiles(next);
    const file = next?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setSaved(false);
    try {
      const uploaded = await uploadRecordImage(api, kind, row.id, file);
      setFileId(uploaded.fileId);
      setSaved(true);
      onSaved();
    } catch (failure) {
      setError(
        failure instanceof ApiFailure
          ? failure.message
          : "The image could not be uploaded. Retry when the connection returns.",
      );
    } finally {
      setBusy(false);
    }
  };
  const src = recordImageSrc(
    kind,
    fileId ? { ...row, logo_file_id: fileId, image_file_id: fileId } : row,
  );
  return (
    <SectionCard title={title} compact>
      <Stack gap={8}>
        {src ? (
          <RecordImage src={src} label={title} preview />
        ) : (
          <p className={styles.support}>No {title.toLowerCase()} uploaded.</p>
        )}
        {canWrite ? (
          <FileUpload
            id={`catalog-${row.id}-upload`}
            label={
              src
                ? `Replace ${title.toLowerCase()}`
                : `Upload ${title.toLowerCase()}`
            }
            hint="JPEG, PNG, or WebP"
            accept="image/jpeg,image/png,image/webp"
            files={files}
            busy={busy}
            error={error || undefined}
            onChange={(next) => void upload(next)}
            compact
          />
        ) : null}
        {saved ? (
          <InlineNotice tone="success">{title} saved.</InlineNotice>
        ) : null}
      </Stack>
    </SectionCard>
  );
}
