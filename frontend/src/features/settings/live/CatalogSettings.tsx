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

export type CatalogKind =
  | "banks"
  | "product-types"
  | "bank-product-mappings"
  | "product-variants";

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
const nameField: Field = { key: "name", label: "Name", required: true, max: 150 };

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
    render: (row) => <Text value={banks.label(row.bank_id)} />,
  };
  const productColumn: ServerColumn<CatalogRecord> = {
    key: "product_type_id",
    label: "Product",
    width: 180,
    render: (row) => <Text value={products.label(row.product_type_id)} />,
  };
  const columns: ServerColumn<CatalogRecord>[] =
    kind === "banks"
      ? [
          { key: "name", label: "Bank", width: 220, render: (row) => <Text value={row.name} /> },
          { key: "bank_code", label: "Bank code", width: 140, render: (row) => <Text value={row.bank_code} /> },
          status,
        ]
      : kind === "product-types"
        ? [
            { key: "name", label: "Product", width: 220, render: (row) => <Text value={row.name} /> },
            { key: "code", label: "Product code", width: 140, render: (row) => <Text value={row.code} /> },
            status,
          ]
        : kind === "product-variants"
          ? [
              { key: "name", label: "Variant", width: 220, render: (row) => <Text value={row.name} /> },
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
        ? [{ key: "code", label: "Product code", required: true, max: 20 }, nameField]
        : kind === "product-variants"
          ? [
              bankField,
              offeredProductField,
              nameField,
            ]
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
                path={`/catalog/${kind}/${row.id}/image`}
                title={kind === "banks" ? "Logo" : "Image"}
                present={Boolean(
                  kind === "banks" ? row.logo_file_id : row.image_file_id,
                )}
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
  path,
  title,
  present,
  canWrite,
  onSaved,
}: {
  path: string;
  title: string;
  present: boolean;
  canWrite: boolean;
  onSaved: () => void;
}) {
  const { api } = useSession();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const [version, setVersion] = useState(0);
  const [files, setFiles] = useState<FileList | null>(null);
  const upload = async (next: FileList | null) => {
    setFiles(next);
    const file = next?.[0];
    if (!file) return;
    setBusy(true);
    setError("");
    setSaved(false);
    const body = new FormData();
    body.append("file", file);
    try {
      await api.request(path, { method: "PUT", body });
      setVersion((value) => value + 1);
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
  return (
    <SectionCard title={title} compact>
      <Stack gap={8}>
        {present || version > 0 ? (
          <img
            className={styles.image}
            src={`/api/v1${path}?v=${version}`}
            alt={title}
          />
        ) : (
          <p className={styles.support}>No {title.toLowerCase()} uploaded.</p>
        )}
        {canWrite ? (
          <FileUpload
            id={`${path}-upload`}
            label={present || version > 0 ? `Replace ${title.toLowerCase()}` : `Upload ${title.toLowerCase()}`}
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
