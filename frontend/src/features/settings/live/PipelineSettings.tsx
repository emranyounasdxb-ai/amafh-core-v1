import { useEffect, useState } from "react";
import {
  Button,
  Combobox,
  DatePicker,
  Dialog,
  DropdownSelect,
  DsIcon,
  FormField,
  FormLayout,
  IconButton,
  InlineNotice,
  LoadingState,
  SectionCard,
  Stack,
  TextInput,
  Timeline,
  CompactDate,
  type AppliedFilter,
  type SelectOption,
} from "../../../design-system";
import { choices } from "../../../app/api/choices";
import { ApiFailure } from "../../../app/api/http";
import type { DataRecord } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import { roundWholeText } from "../../../app/numbers/wholeNumber";
import { useSession } from "../../../app/session/useSession";
import { filterQuery, useServerTable } from "../../../shared/table/serverTable";
import { SelectFilter } from "../../finance/live/financeCells";
import { stateAction } from "./settingsActions";
import { ActiveBadge, Text, WholeNumber } from "./settingsCells";
import { canManageSettings } from "./settingsRegistry";
import { SettingsTable } from "./SettingsTable";
import { useNamedRecords } from "./useNamedRecords";
import styles from "./SettingsPage.module.css";
import {
  recordImageSrc,
  type ImageRecord,
} from "../../../app/api/recordImages";
import { RecordImage } from "../../../shared/media/RecordImage";

type PipelineRecord = {
  id: string;
  bank_id: string;
  product_type_id: string;
  version: number;
  effective_date: string;
  active: boolean;
};

type StageRecord = {
  name: string;
  stage_order: number;
  expected_business_days: number;
  is_final: boolean;
  final_status: string | null;
};

const STATUSES = [
  { value: "true", label: "Active" },
  { value: "false", label: "Inactive" },
];
// Final outcomes are fixed case statuses, not configurable records.
const OUTCOMES: SelectOption[] = [
  { value: "", label: "Non-final" },
  { value: "Completed", label: "Completed" },
  { value: "Rejected", label: "Rejected" },
];
const EMPTY = { active: "", bankId: "", productTypeId: "" };

export function PipelineSettings() {
  const { session } = useSession();
  const manage = canManageSettings(session, "pipeline.write");
  const [refresh, setRefresh] = useState(0);
  const [creating, setCreating] = useState(false);
  const [notice, setNotice] = useState("");
  const [filters, setFilters] = useState(EMPTY);
  const set = (patch: Partial<typeof EMPTY>) =>
    setFilters((current) => ({ ...current, ...patch }));
  const table = useServerTable<PipelineRecord>(
    "settings-pipelines",
    "/pipelines",
    filterQuery(filters),
    refresh,
  );
  const banks = useNamedRecords("/catalog/banks", refresh);
  const products = useNamedRecords("/catalog/product-types", refresh);
  const name = (row: PipelineRecord) =>
    `${banks.label(row.bank_id)} · ${products.label(row.product_type_id)} · Version ${row.version}`;
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
  return (
    <>
      <SettingsTable
        table={table}
        tableId="settings-pipelines"
        ariaLabel="Pipelines"
        kind="Pipeline"
        loadingTitle="Loading pipelines"
        emptyTitle="No pipelines"
        emptyDescription="A pipeline version defines the case stages for a bank product."
        notice={notice}
        onNotice={setNotice}
        filters={
          <>
            <SelectFilter
              id="settings-pipeline-status"
              label="Status"
              placeholder="All statuses"
              value={filters.active}
              options={STATUSES}
              onChange={(active) => set({ active })}
            />
            <SelectFilter
              id="settings-pipeline-bank"
              label="Bank"
              placeholder="All banks"
              value={filters.bankId}
              options={banks.options()}
              loading={banks.loading}
              onChange={(bankId) => set({ bankId })}
            />
            <SelectFilter
              id="settings-pipeline-product"
              label="Product"
              placeholder="All products"
              value={filters.productTypeId}
              options={products.options()}
              loading={products.loading}
              onChange={(productTypeId) => set({ productTypeId })}
            />
          </>
        }
        applied={applied}
        onClearFilters={() => setFilters(EMPTY)}
        columns={[
          {
            key: "bank_id",
            label: "Bank",
            width: 180,
            render: (row) => <Text value={banks.label(row.bank_id)} />,
          },
          {
            key: "product_type_id",
            label: "Product",
            width: 170,
            render: (row) => (
              <Text value={products.label(row.product_type_id)} />
            ),
          },
          {
            key: "version",
            label: "Version",
            width: 100,
            kind: "number",
            render: (row) => <WholeNumber value={row.version} />,
          },
          {
            key: "effective_date",
            label: "Effective",
            width: 120,
            kind: "date",
            render: (row) => <CompactDate value={row.effective_date} />,
          },
          {
            key: "active",
            label: "Status",
            width: 110,
            render: (row) => <ActiveBadge active={row.active} />,
          },
        ]}
        rowLabel={name}
        title={name}
        facts={(row) => [
          { label: "Bank", value: <Text value={banks.label(row.bank_id)} /> },
          {
            label: "Product",
            value: <Text value={products.label(row.product_type_id)} />,
          },
          {
            label: "Version",
            value: <WholeNumber value={row.version} />,
            numeric: true,
          },
          {
            label: "Effective",
            value: <CompactDate value={row.effective_date} />,
          },
          { label: "Status", value: <ActiveBadge active={row.active} /> },
        ]}
        detail={(row) => <PipelineStages id={row.id} />}
        extraActions={
          manage ? (
            <Button size="compact" onClick={() => setCreating(true)}>
              Add Pipeline Version
            </Button>
          ) : null
        }
        actions={
          manage
            ? (row) => [
                stateAction(
                  "pipeline",
                  `/pipelines/${row.id}`,
                  row.active,
                  "This pipeline version stops being used for new cases. Cases that already use it keep their stages.",
                ),
              ]
            : undefined
        }
        onSaved={() => setRefresh((value) => value + 1)}
      />
      {creating ? (
        <PipelineCreateDialog
          onClose={() => setCreating(false)}
          onSaved={() => {
            setCreating(false);
            setNotice("Pipeline version added.");
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}
    </>
  );
}

function PipelineStages({ id }: { id: string }) {
  const detail = useResource<DataRecord>(`/pipelines/${id}`);
  const stages = (detail.data?.stages as StageRecord[] | undefined) ?? [];
  return (
    <SectionCard title="Stages" compact>
      {detail.loading && !detail.data ? (
        <LoadingState title="Loading stages" />
      ) : detail.error ? (
        <InlineNotice tone="error">{detail.error}</InlineNotice>
      ) : stages.length ? (
        <Timeline
          items={stages.map((stage) => ({
            id: `${stage.stage_order}`,
            time: `Stage ${stage.stage_order}`,
            title: stage.name,
            description: `${stage.expected_business_days} expected business ${
              stage.expected_business_days === 1 ? "day" : "days"
            }`,
            status: stage.is_final
              ? `Final · ${stage.final_status ?? "No outcome"}`
              : "In progress",
            tone: stage.is_final ? "success" : "neutral",
          }))}
        />
      ) : (
        <p className={styles.support}>No retained stages are available.</p>
      )}
    </SectionCard>
  );
}

type StageDraft = { name: string; days: string; outcome: string };

function PipelineCreateDialog({
  onClose,
  onSaved,
}: {
  onClose: () => void;
  onSaved: () => void;
}) {
  const { api } = useSession();
  const [bankId, setBankId] = useState("");
  const [productTypeId, setProductTypeId] = useState("");
  const [effectiveDate, setEffectiveDate] = useState("");
  const [stages, setStages] = useState<StageDraft[]>([
    { name: "", days: "1", outcome: "" },
    { name: "", days: "0", outcome: "Completed" },
  ]);
  const [banks, setBanks] = useState<SelectOption[]>([]);
  const [offered, setOffered] = useState<{
    bankId: string;
    options: SelectOption[];
  }>({ bankId: "", options: [] });
  const products = offered.bankId === bankId ? offered.options : [];
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  useEffect(() => {
    const controller = new AbortController();
    choices<DataRecord>(api, "/catalog/banks?active=true", controller.signal)
      .then((rows) =>
        setBanks(
          rows.map((row) => ({
            value: String(row.id),
            label: String(row.name),
            leading: recordImageSrc("banks", row as ImageRecord) ? (
              <RecordImage
                src={recordImageSrc("banks", row as ImageRecord)}
                label={String(row.name)}
              />
            ) : undefined,
          })),
        ),
      )
      .catch(() => {
        if (!controller.signal.aborted) setError("Banks are unavailable.");
      });
    return () => controller.abort();
  }, [api]);

  useEffect(() => {
    if (!bankId) return;
    const controller = new AbortController();
    choices<DataRecord>(
      api,
      `/catalog/product-types?active=true&bankId=${encodeURIComponent(bankId)}`,
      controller.signal,
    )
      .then((rows) => {
        const options = rows.map((row) => ({
          value: String(row.id),
          label: String(row.name),
          leading: recordImageSrc("product-types", row as ImageRecord) ? (
            <RecordImage
              src={recordImageSrc("product-types", row as ImageRecord)}
              label={String(row.name)}
            />
          ) : undefined,
        }));
        setOffered({ bankId, options });
        setProductTypeId((current) =>
          options.some((option) => option.value === current) ? current : "",
        );
      })
      .catch(() => {
        if (!controller.signal.aborted) setError("Products are unavailable.");
      });
    return () => controller.abort();
  }, [api, bankId]);

  const updateStage = (index: number, patch: Partial<StageDraft>) =>
    setStages((current) =>
      current.map((stage, position) =>
        position === index ? { ...stage, ...patch } : stage,
      ),
    );

  const submit = async () => {
    const local: Record<string, string> = {};
    if (!bankId) local.bankId = "Bank is required";
    if (!productTypeId) local.productTypeId = "Product is required";
    if (!effectiveDate) local.effectiveDate = "Effective date is required";
    stages.forEach((stage, index) => {
      if (!stage.name.trim()) local[`stage-${index}`] = "Stage name is required";
      const days = roundWholeText(stage.days);
      if (days === null || Number(days) < 0)
        local[`days-${index}`] = "Enter zero or a whole number of days";
    });
    if (!stages.some((stage) => stage.outcome))
      local.stages = "Add at least one final stage with an outcome.";
    setFieldErrors(local);
    if (Object.keys(local).length) return;
    setBusy(true);
    setError("");
    try {
      await api.request("/pipelines", {
        method: "POST",
        body: JSON.stringify({
          bankId,
          productTypeId,
          effectiveDate,
          stages: stages.map((stage, index) => ({
            name: stage.name.trim(),
            stageOrder: index + 1,
            expectedBusinessDays: Number(roundWholeText(stage.days)),
            isFinal: Boolean(stage.outcome),
            finalStatus: stage.outcome || null,
          })),
        }),
      });
      onSaved();
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

  return (
    <Dialog
      open
      size="lg"
      title="Add Pipeline Version"
      description="A new version applies to cases created on or after its effective date."
      busy={busy}
      onClose={onClose}
      closeOnOutside={!busy}
      footer={
        <>
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
          <Button loading={busy} onClick={() => void submit()}>
            Save
          </Button>
        </>
      }
    >
      <Stack>
        <FormLayout columns={3}>
          <FormField label="Bank" htmlFor="pipeline-bank" required error={fieldErrors.bankId}>
            <Combobox
              id="pipeline-bank"
              options={banks}
              value={bankId}
              onChange={(next) => {
                if (next !== bankId) setProductTypeId("");
                setBankId(next);
              }}
              invalid={Boolean(fieldErrors.bankId)}
              placeholder="Select"
              emptyLabel="No matching records"
            />
          </FormField>
          <FormField
            label="Product"
            htmlFor="pipeline-product"
            required
            error={fieldErrors.productTypeId}
            hint={bankId ? undefined : "Select a bank first"}
          >
            <Combobox
              id="pipeline-product"
              options={products}
              value={productTypeId}
              onChange={setProductTypeId}
              disabled={!bankId}
              invalid={Boolean(fieldErrors.productTypeId)}
              placeholder="Select"
              emptyLabel="This bank offers no active products"
            />
          </FormField>
          <FormField
            label="Effective date"
            htmlFor="pipeline-effective"
            required
            error={fieldErrors.effectiveDate}
          >
            <DatePicker
              id="pipeline-effective"
              value={effectiveDate}
              onChange={setEffectiveDate}
              invalid={Boolean(fieldErrors.effectiveDate)}
            />
          </FormField>
        </FormLayout>
        <div className={styles.stages}>
          {stages.map((stage, index) => (
            <div className={styles.stageRow} key={index}>
              <FormField
                label={`Stage ${index + 1}`}
                htmlFor={`pipeline-stage-${index}`}
                required
                error={fieldErrors[`stage-${index}`]}
              >
                <TextInput
                  id={`pipeline-stage-${index}`}
                  value={stage.name}
                  maxLength={150}
                  invalid={Boolean(fieldErrors[`stage-${index}`])}
                  onChange={(event) => updateStage(index, { name: event.target.value })}
                />
              </FormField>
              <FormField
                label="Expected business days"
                htmlFor={`pipeline-days-${index}`}
                required
                error={fieldErrors[`days-${index}`]}
              >
                <TextInput
                  id={`pipeline-days-${index}`}
                  inputMode="numeric"
                  value={stage.days}
                  invalid={Boolean(fieldErrors[`days-${index}`])}
                  onChange={(event) => updateStage(index, { days: event.target.value })}
                  onBlur={(event) => {
                    const whole = roundWholeText(event.target.value);
                    if (whole !== null) updateStage(index, { days: whole });
                  }}
                />
              </FormField>
              <FormField label="Outcome" htmlFor={`pipeline-outcome-${index}`}>
                <DropdownSelect
                  id={`pipeline-outcome-${index}`}
                  label="Outcome"
                  options={OUTCOMES}
                  value={stage.outcome}
                  onChange={(next) =>
                    updateStage(index, {
                      outcome: Array.isArray(next) ? (next[0] ?? "") : next,
                    })
                  }
                />
              </FormField>
              <IconButton
                label={`Remove stage ${index + 1}`}
                variant="ghost"
                disabled={stages.length <= 2}
                onClick={() =>
                  setStages((current) =>
                    current.filter((_, position) => position !== index),
                  )
                }
              >
                <DsIcon name="delete" />
              </IconButton>
            </div>
          ))}
        </div>
        <div>
          <Button
            variant="secondary"
            onClick={() =>
              setStages((current) => [
                ...current,
                { name: "", days: "1", outcome: "" },
              ])
            }
          >
            Add stage
          </Button>
        </div>
        {fieldErrors.stages ? (
          <InlineNotice tone="error">{fieldErrors.stages}</InlineNotice>
        ) : null}
        {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}
      </Stack>
    </Dialog>
  );
}
