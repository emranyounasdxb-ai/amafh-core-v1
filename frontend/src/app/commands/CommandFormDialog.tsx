import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ReactNode,
} from "react";
import {
  Button,
  Checkbox,
  Combobox,
  DatePicker,
  DateTimePicker,
  Dialog,
  DropdownSelect,
  FormField,
  FormLayout,
  FormSection,
  InfoField,
  InfoGrid,
  InlineNotice,
  MonthPicker,
  NationalitySelect,
  PersonSelect,
  TextArea,
  TextInput,
  useDebouncedValue,
  type DateTimeValue,
  type PersonOption,
  type SelectOption,
} from "../../design-system";
import { choices } from "../api/choices";
import { commandPayload, initialField } from "../api/commandPayload";
import type { Command, Field } from "../api/commands";
import { ApiFailure } from "../api/http";
import type { DataRecord, Page } from "../api/models";
import { roundWholeText } from "../numbers/wholeNumber";
import { isUuid } from "../presentation/labels";
import { useSession } from "../session/useSession";
import {
  imageFileError,
  recordImageSrc,
  uploadRecordImage,
  type ImageRecord,
  type ImageKind,
} from "../api/recordImages";
import { ImageUploadField, RecordImage } from "../../shared/media/RecordImage";

function choicePath(field: Field, values: DataRecord) {
  const source = field.source!;
  const params = new URLSearchParams();
  for (const [query, key] of Object.entries(source.queryFrom || {}))
    if (values[key]) params.set(query, String(values[key]));
  return (
    source.path +
    (params.size ? (source.path.includes("?") ? "&" : "?") + params : "")
  );
}

function blockedChoice(field: Field, values: DataRecord) {
  const prerequisite = field.source?.requires;
  return prerequisite && !values[prerequisite.key]
    ? prerequisite.placeholder
    : "";
}

type ChoiceStatus = "loading" | "ready" | "error";

function toDateTimeValue(value: unknown): DateTimeValue {
  const raw = String(value ?? "");
  if (raw.includes("T")) {
    const [date, time] = raw.split("T");
    return { date, time: (time || "").slice(0, 5) };
  }
  return { date: "", time: "" };
}

function fromDateTimeValue(value: DateTimeValue) {
  if (!value.date) return "";
  return `${value.date}T${value.time || "00:00"}`;
}

/** Fields whose choices or values depend on `key`, directly or transitively. */
function dependentKeys(fields: Field[], key: string): string[] {
  const found: string[] = [];
  const visit = (changed: string) => {
    const field = fields.find((item) => item.key === changed);
    const direct = [
      ...(field?.clearOnChange ?? []),
      ...fields
        .filter((item) =>
          [
            ...Object.values(item.source?.queryFrom ?? {}),
            ...Object.values(item.source?.matchFrom ?? {}),
            ...(item.source?.requires ? [item.source.requires.key] : []),
          ].includes(changed),
        )
        .map((item) => item.key),
    ];
    for (const next of direct)
      if (next !== key && !found.includes(next)) {
        found.push(next);
        visit(next);
      }
  };
  visit(key);
  return found;
}

function friendlyFieldError(
  key: string,
  label: string,
  messages: string[],
  type?: Field["type"],
) {
  const text = messages.filter(Boolean).join(" ");
  if (type === "number" || type === "decimal") {
    if (/greater than or equal to 0/i.test(text))
      return `${label} must be zero or greater`;
    if (/greater than 0/i.test(text))
      return `${label} must be greater than zero`;
    if (/input should be|valid number/i.test(text))
      return `Enter a valid whole number for ${label}`;
  }
  if (/uuid|invalid character|valid uuid|input should be/i.test(text)) {
    return key === "relatedId"
      ? "Select a related record"
      : "Select a valid option";
  }
  return text || `${label} is required`;
}

function ChoiceControl({
  field,
  values,
  change,
  ready,
  invalid,
}: {
  field: Field;
  values: DataRecord;
  change: (key: string, value: string) => void;
  ready: (key: string, path: string, status?: ChoiceStatus) => void;
  invalid?: string;
}) {
  const { api, session } = useSession();
  const [rows, setRows] = useState<DataRecord[]>([]);
  const [branches, setBranches] = useState<DataRecord[]>([]);
  const initializedChoice = useRef("");
  const [query, setQuery] = useState("");
  const [picked, setPicked] = useState<SelectOption | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [attempt, setAttempt] = useState(0);
  const source = field.source!;
  const blocked = blockedChoice(field, values);
  const debouncedQuery = useDebouncedValue(query, 250);
  const path = choicePath(field, values);
  const requestPath = source.search
    ? `${path}${path.includes("?") ? "&" : "?"}q=${encodeURIComponent(debouncedQuery)}&page=1&pageSize=25`
    : path;
  useEffect(() => {
    setQuery("");
    setError("");
  }, [path]);
  useEffect(() => {
    if (blocked) return;
    const controller = new AbortController();
    setRows([]);
    setError("");
    setLoading(true);
    ready(field.key, path, "loading");
    const read = source.search
      ? api
          .request<Page<DataRecord>>(requestPath, { signal: controller.signal })
          .then((page) => page.items)
      : source.paged
        ? choices<DataRecord>(api, path, controller.signal)
        : api.request<DataRecord[]>(path, { signal: controller.signal });
    read
      .then((items) => {
        if (controller.signal.aborted) return;
        if (
          !Array.isArray(items) ||
          items.some((row) => !row || typeof row !== "object")
        )
          throw new Error(
            "Choices response is invalid. Retry loading the records.",
          );
        setRows(items);
        setLoading(false);
        ready(field.key, path);
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return;
        setError(
          failure instanceof Error ? failure.message : "Choices unavailable",
        );
        setLoading(false);
        ready(field.key, path, "error");
      });
    return () => controller.abort();
  }, [
    api,
    attempt,
    blocked,
    field.key,
    path,
    ready,
    requestPath,
    source.paged,
    source.search,
  ]);
  useEffect(() => {
    if (field.choiceLabel !== "departmentWithBranch") return;
    const controller = new AbortController();
    api
      .request<DataRecord[]>("/branches", { signal: controller.signal })
      .then((items) => {
        if (!controller.signal.aborted) setBranches(items);
      })
      .catch(() => {
        if (!controller.signal.aborted) setBranches([]);
      });
    return () => controller.abort();
  }, [api, field.choiceLabel]);
  const filtered = rows.filter(
    (row) =>
      (field.key !== "branchId" ||
        session?.designation !== "Admin Staff" ||
        row.id === session.branchId) &&
      ((source.keepSelected &&
        values[field.key] &&
        String(row[source.value || "id"]) === String(values[field.key])) ||
        Object.entries(source.where || {}).every(
          ([key, value]) => String(row[key]) === value,
        )) &&
      Object.entries(source.matchFrom || {}).every(
        ([key, valueKey]) =>
          Boolean(values[valueKey]) &&
          String(row[key] ?? "") === String(values[valueKey]),
      ) &&
      !(source.exclude || []).includes(String(row[source.value || "id"])) &&
      Object.entries(source.allowed || {}).every(([key, allowed]) =>
        allowed.includes(String(row[key])),
      ),
  );
  const branchName = (row: DataRecord) => {
    const name = branches.find(
      (branch) =>
        String(branch.id) === String(row.branch_id || row.branchId || ""),
    )?.name;
    return typeof name === "string" && name.trim() ? name : "Unavailable";
  };
  const options: SelectOption[] = filtered.map((row) => {
    const value = String(row[source.value || "id"] ?? "");
    const rawLabel = String(
      row[source.label] || row.fullName || row.name || row.label || "",
    );
    const baseLabel =
      rawLabel && !isUuid(rawLabel) ? rawLabel : "Related record";
    const label =
      field.choiceLabel === "departmentWithBranch"
        ? `${baseLabel} · ${branchName(row)}`
        : field.choiceLabel === "nameWithCode"
          ? `${baseLabel} (${String(row.code)})${row.active === false ? " · Inactive" : ""}`
          : baseLabel;
    const subtitle = String(
      row.subtitle || row.employeeCode || row.companyEmployeeCode || "",
    );
    const imageSrc = source.path.startsWith("/catalog/")
      ? recordImageSrc(
          source.path.split("/")[2]?.split("?")[0] as ImageKind,
          row as ImageRecord,
        )
      : undefined;
    return {
      value,
      label,
      description: subtitle && !isUuid(subtitle) ? subtitle : undefined,
      leading: imageSrc ? (
        <RecordImage src={imageSrc} label={label} />
      ) : undefined,
    };
  });
  const currentValue = String(values[field.key] ?? "");
  useEffect(() => {
    const initializationKey = `${field.key}:${field.initialChoiceLabel ?? ""}`;
    if (
      initializedChoice.current === initializationKey ||
      !field.initialChoiceLabel ||
      !rows.length
    )
      return;
    initializedChoice.current = initializationKey;
    if (currentValue) return;
    const match = rows.find(
      (row) => String(row[source.label]) === field.initialChoiceLabel,
    );
    if (match) change(field.key, String(match[source.value || "id"]));
  }, [
    change,
    currentValue,
    field.initialChoiceLabel,
    field.key,
    rows,
    source.label,
    source.value,
  ]);
  useEffect(() => {
    if (!currentValue) setPicked(null);
  }, [currentValue]);
  const context = field.choiceContext;
  const contextValue = context
    ? String(
        rows.find(
          (row) => String(row[source.value || "id"]) === currentValue,
        )?.[context.from] ?? "",
      )
    : "";
  useEffect(() => {
    if (context) change(context.key, contextValue);
  }, [change, context, contextValue]);
  const mergedOptions =
    picked &&
    currentValue === picked.value &&
    !options.some((option) => option.value === currentValue)
      ? [picked, ...options]
      : options;
  const people: PersonOption[] = filtered.map((row) => {
    const code = String(row.companyEmployeeCode || row.employeeCode || "");
    const subtitle = [
      typeof row.designation === "string" ? row.designation : "",
      code && !isUuid(code) ? code : "",
    ]
      .filter(Boolean)
      .join(" · ");
    return {
      value: String(row[source.value || "id"] ?? ""),
      name: String(row[source.label] || row.fullName || row.name || ""),
      subtitle: subtitle || undefined,
      src: recordImageSrc("employee", row as ImageRecord),
    };
  });
  const personField =
    !source.search &&
    (source.path.startsWith("/employees") ||
      field.key.toLowerCase().includes("employee"));
  if (personField) {
    return (
      <FormField
        label={field.label}
        htmlFor={field.key}
        required={field.required}
        error={invalid || error}
      >
        <PersonSelect
          id={field.key}
          label=""
          people={people}
          value={String(values[field.key] ?? "")}
          onChange={(value) => change(field.key, value)}
        />
      </FormField>
    );
  }
  return (
    <FormField
      label={field.label}
      htmlFor={field.key}
      required={field.required}
      error={[invalid, error].filter(Boolean).join(" ") || undefined}
      hint={blocked || field.hint}
    >
      <Combobox
        id={field.key}
        options={mergedOptions}
        value={currentValue}
        onChange={(value) => {
          const option = options.find((item) => item.value === value) || null;
          setPicked(option);
          change(field.key, value);
        }}
        required={field.required}
        disabled={Boolean(blocked || error)}
        unavailable={Boolean(error)}
        loading={loading}
        invalid={Boolean(invalid || error)}
        query={source.search ? query : undefined}
        onQueryChange={source.search ? setQuery : undefined}
        placeholder={
          blocked ||
          (error
            ? `${field.label} unavailable`
            : loading
              ? `Loading ${field.label}…`
              : source.search
                ? "Search records"
                : "Select")
        }
        emptyLabel={
          options.length
            ? "No matching records"
            : source.emptyLabel || "No matching records"
        }
      />
      {error ? (
        <Button
          size="compact"
          variant="ghost"
          onClick={() => setAttempt((value) => value + 1)}
        >
          Retry {field.label}
        </Button>
      ) : null}
    </FormField>
  );
}

export function CommandFormDialog({
  command,
  record = {},
  onClose,
  onSaved,
  reference,
}: {
  command: Command;
  record?: DataRecord;
  onClose: () => void;
  onSaved: (value: unknown) => void;
  /** Read-only context derived from the current values; never submitted. */
  reference?: (values: DataRecord) => ReactNode;
}) {
  const { api } = useSession();
  const [values, setValues] = useState<DataRecord>(() => {
    const next: DataRecord = {};
    for (const field of command.fields)
      next[field.key] = initialField(field, record);
    return next;
  });
  const [readyFields, setReadyFields] = useState<
    Record<string, { path: string; status: ChoiceStatus }>
  >({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [fields, setFields] = useState<Record<string, string[]>>({});
  const [imageFiles, setImageFiles] = useState<FileList | null>(null);
  const [imageError, setImageError] = useState("");
  // A failed upload retries against the already saved record, never creates it again.
  const [savedRecord, setSavedRecord] = useState<{
    id: string;
    value: unknown;
  } | null>(null);
  const finishOrClose = () =>
    savedRecord ? onSaved(savedRecord.value) : onClose();
  const replay = useRef({ payload: "", key: "" });
  const ready = useCallback(
    (key: string, path: string, status: ChoiceStatus = "ready") => {
      setReadyFields((current) =>
        current[key]?.path === path && current[key]?.status === status
          ? current
          : { ...current, [key]: { path, status } },
      );
    },
    [],
  );
  const latestValues = useRef(values);
  latestValues.current = values;
  const change = useCallback(
    (key: string, value: unknown) => {
      if (latestValues.current[key] === value) return;
      const cleared = dependentKeys(command.fields, key);
      const stale = [key, ...cleared];
      setValues((current) => {
        const next = { ...current, [key]: value };
        for (const clear of cleared) next[clear] = "";
        return next;
      });
      setFields((current) =>
        stale.some((name) => name in current)
          ? Object.fromEntries(
              Object.entries(current).filter(([name]) => !stale.includes(name)),
            )
          : current,
      );
      setError("");
    },
    [command.fields],
  );
  const visible = useMemo(
    () => command.fields.filter((field) => !field.show || field.show(values)),
    [command.fields, values],
  );
  const sections = visible.reduce<{ title: string; fields: Field[] }[]>(
    (groups, field) => {
      const title = field.section ?? "";
      const group = groups.find((item) => item.title === title);
      if (group) group.fields.push(field);
      else groups.push({ title, fields: [field] });
      return groups;
    },
    [],
  );
  const waiting = visible.some(
    (field) =>
      field.source &&
      !blockedChoice(field, values) &&
      (readyFields[field.key]?.path !== choicePath(field, values) ||
        readyFields[field.key]?.status !== "ready"),
  );
  const choicesFailed = visible.some(
    (field) =>
      field.source &&
      !blockedChoice(field, values) &&
      readyFields[field.key]?.path === choicePath(field, values) &&
      readyFields[field.key]?.status === "error",
  );
  const submit = async () => {
    if (busy || waiting) return;
    const image = imageFiles?.[0];
    if (image && command.imageUpload) {
      const invalid = imageFileError(image);
      if (invalid) {
        setImageError(invalid);
        return;
      }
    }
    const localErrors: Record<string, string[]> = {};
    for (const field of visible) {
      const raw = values[field.key];
      const empty = raw === "" || raw == null;
      if (field.required && empty) {
        localErrors[field.key] = [
          field.key === "relatedId"
            ? "Select a related record"
            : `${field.label} is required`,
        ];
      } else if (
        field.nonNegative &&
        !empty &&
        (String(raw).trim().startsWith("-") || roundWholeText(raw) === null)
      ) {
        localErrors[field.key] = [
          `${field.label} must be a non-negative whole AED amount`,
        ];
      } else if (
        field.key === "relatedId" &&
        values.relatedType &&
        !isUuid(String(raw ?? ""))
      ) {
        localErrors[field.key] = ["Select a related record"];
      }
    }
    if (!savedRecord && Object.keys(localErrors).length) {
      setError("");
      setFields(localErrors);
      return;
    }
    const payload = commandPayload(command, values);
    if (replay.current.payload !== payload)
      replay.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setImageError("");
    setFields({});
    try {
      const value = savedRecord
        ? savedRecord.value
        : await api.request(command.path, {
            method: command.method || "POST",
            body: payload,
            headers: command.idempotent
              ? { "Idempotency-Key": replay.current.key }
              : undefined,
          });
      if (command.imageUpload && image) {
        const id =
          savedRecord?.id ||
          String((value as DataRecord | undefined)?.id || record.id || "");
        if (!id) throw new Error("Saved record identity unavailable");
        setSavedRecord({ id, value });
        try {
          await uploadRecordImage(api, command.imageUpload.kind, id, image);
        } catch (failure) {
          setImageError(
            failure instanceof ApiFailure
              ? failure.message
              : "Image upload failed. Retry when the connection returns.",
          );
          setError(
            "The record was saved, but its image was not. Retry the image upload or close this form and replace it later.",
          );
          return;
        }
      }
      onSaved(value);
    } catch (failure) {
      if (failure instanceof ApiFailure) {
        setError(
          /uuid|invalid character|valid uuid/i.test(failure.message)
            ? "The form could not be saved. Check the highlighted fields."
            : failure.message,
        );
        const next: Record<string, string[]> = {};
        for (const [key, messages] of Object.entries(failure.fieldErrors)) {
          const field = command.fields.find((item) => item.key === key);
          next[key] = [
            friendlyFieldError(key, field?.label || key, messages, field?.type),
          ];
        }
        setFields(next);
      } else {
        setError(
          "The request could not be completed. Retry safely when the connection returns.",
        );
      }
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open
      title={command.title}
      size={sections.length > 1 ? "xl" : "lg"}
      busy={busy}
      onClose={finishOrClose}
      closeOnOutside={!busy}
      footer={
        <>
          <Button variant="secondary" disabled={busy} onClick={finishOrClose}>
            {savedRecord ? "Close" : "Cancel"}
          </Button>
          <Button
            loading={busy}
            disabled={waiting}
            onClick={() => void submit()}
          >
            {choicesFailed
              ? "Choices unavailable"
              : waiting
                ? "Loading choices…"
                : savedRecord
                  ? "Retry image upload"
                  : command.submitLabel || "Save"}
          </Button>
        </>
      }
    >
      {command.confirmation ? (
        <>
          <p>{command.confirmation.description}</p>
          <InfoGrid>
            {command.confirmation.facts.map((fact) => (
              <InfoField
                key={fact.label}
                label={fact.label}
                value={fact.value}
              />
            ))}
          </InfoGrid>
        </>
      ) : null}
      {command.imageUpload ? (
        <fieldset
          disabled={busy || Boolean(savedRecord)}
          style={{ border: 0, padding: 0, margin: 0, minWidth: 0 }}
        >
          {renderFields()}
        </fieldset>
      ) : (
        renderFields()
      )}
      {command.imageUpload ? (
        <ImageUploadField
          upload={command.imageUpload}
          record={record.id ? (record as ImageRecord) : undefined}
          files={imageFiles}
          busy={busy}
          error={imageError || undefined}
          onChange={(next) => {
            setImageFiles(next);
            setImageError("");
          }}
        />
      ) : null}
      {reference?.(values)}
      {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}
      {Object.entries(fields)
        .filter(([key]) => !command.fields.some((field) => field.key === key))
        .map(([key, messages]) => (
          <InlineNotice key={key} tone="error">
            {friendlyFieldError(key, "This field", messages)}
          </InlineNotice>
        ))}
    </Dialog>
  );

  function renderFields() {
    return sections.length > 1 || sections[0]?.title ? (
      <div
        className={["ds-command-sections", command.formClassName]
          .filter(Boolean)
          .join(" ")}
      >
        {sections.map((section) => (
          <FormSection key={section.title} title={section.title} columns={2}>
            {section.fields.map(renderField)}
          </FormSection>
        ))}
      </div>
    ) : (
      <FormLayout
        columns={2}
        className={["ds-command-fields", command.formClassName]
          .filter(Boolean)
          .join(" ")}
      >
        {visible.map(renderField)}
      </FormLayout>
    );
  }

  function renderField(field: Field) {
    const invalid = fields[field.key]?.join(" ");
    if (field.control === "nationality") {
      return (
        <FormField
          key={field.key}
          label={field.label}
          htmlFor={field.key}
          required={field.required}
          error={invalid}
        >
          <NationalitySelect
            id={field.key}
            label=""
            value={String(values[field.key] ?? "")}
            onChange={(value) => change(field.key, value)}
            invalid={Boolean(invalid)}
          />
        </FormField>
      );
    }
    if (field.source) {
      return (
        <ChoiceControl
          key={choicePath(field, values)}
          field={field}
          values={values}
          change={change}
          ready={ready}
          invalid={invalid}
        />
      );
    }
    if (field.options) {
      return (
        <FormField
          key={field.key}
          label={field.label}
          htmlFor={field.key}
          required={field.required}
          error={invalid}
        >
          <DropdownSelect
            id={field.key}
            options={field.options.map((option) => ({
              value: option,
              label: field.optionLabels?.[option] || option,
            }))}
            value={String(values[field.key] ?? "")}
            onChange={(value) =>
              change(field.key, Array.isArray(value) ? (value[0] ?? "") : value)
            }
            required={field.required}
            invalid={Boolean(invalid)}
            clearable={!field.required}
          />
        </FormField>
      );
    }
    if (field.type === "datetime-local") {
      return (
        <FormField
          key={field.key}
          label={field.label}
          htmlFor={field.key}
          required={field.required}
          error={invalid}
        >
          <DateTimePicker
            id={field.key}
            value={toDateTimeValue(values[field.key])}
            onChange={(value) => change(field.key, fromDateTimeValue(value))}
            invalid={Boolean(invalid)}
          />
        </FormField>
      );
    }
    if (field.type === "date") {
      return (
        <FormField
          key={field.key}
          label={field.label}
          htmlFor={field.key}
          required={field.required}
          error={invalid}
        >
          <DatePicker
            id={field.key}
            value={String(values[field.key] ?? "")}
            onChange={(value) => change(field.key, value)}
            invalid={Boolean(invalid)}
          />
        </FormField>
      );
    }
    if (field.type === "month") {
      return (
        <FormField
          key={field.key}
          label={field.label}
          htmlFor={field.key}
          required={field.required}
          error={invalid}
        >
          <MonthPicker
            id={field.key}
            label={field.label}
            value={String(values[field.key] ?? "")}
            onChange={(value) => change(field.key, value)}
            invalid={Boolean(invalid)}
          />
        </FormField>
      );
    }
    if (field.type === "textarea") {
      return (
        <FormField
          key={field.key}
          label={field.label}
          htmlFor={field.key}
          required={field.required}
          error={invalid}
        >
          <TextArea
            id={field.key}
            required={field.required}
            maxLength={field.max}
            value={String(values[field.key] ?? "")}
            onChange={(event) => change(field.key, event.target.value)}
          />
        </FormField>
      );
    }
    if (field.type === "checkbox") {
      return (
        <div key={field.key}>
          <Checkbox
            id={field.key}
            label={field.label}
            checked={Boolean(values[field.key])}
            onChange={(event) => change(field.key, event.currentTarget.checked)}
          />
          {invalid ? <InlineNotice tone="error">{invalid}</InlineNotice> : null}
        </div>
      );
    }
    return (
      <FormField
        key={field.key}
        label={field.label}
        htmlFor={field.key}
        required={field.required}
        error={invalid}
      >
        <TextInput
          id={field.key}
          required={field.required}
          type={
            field.type === "decimal" || field.type === "number"
              ? "text"
              : field.type || "text"
          }
          inputMode={
            field.type === "decimal" || field.type === "number"
              ? "numeric"
              : undefined
          }
          maxLength={field.max}
          value={String(values[field.key] ?? "")}
          onChange={(event) => change(field.key, event.target.value)}
          onBlur={
            field.type === "decimal" || field.type === "number"
              ? (event) => {
                  const whole = roundWholeText(event.target.value);
                  if (
                    field.nonNegative &&
                    event.target.value.trim().startsWith("-")
                  )
                    return;
                  if (whole !== null && whole !== event.target.value)
                    change(field.key, whole);
                }
              : undefined
          }
          invalid={Boolean(invalid)}
        />
      </FormField>
    );
  }
}
