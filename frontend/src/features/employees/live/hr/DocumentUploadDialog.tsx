import { useRef, useState } from "react";
import {
  Button,
  CountrySelect,
  DatePicker,
  Dialog,
  DropdownSelect,
  EmiratesIdInput,
  FileUpload,
  FormField,
  FormLayout,
  InlineNotice,
  TextArea,
  TextInput,
} from "../../../../design-system";
import { useSession } from "../../../../app/session/useSession";
import {
  DOCUMENT_ACCEPT,
  DOCUMENT_MAX_BYTES,
  failureMessage,
  type DocumentSeries,
  type DocumentType,
  type FieldMode,
} from "./hrRecords";

type Values = {
  documentNumber: string;
  issueDate: string;
  expiryDate: string;
  issuingCountry: string;
  notes: string;
};

const EMPTY: Values = {
  documentNumber: "",
  issueDate: "",
  expiryDate: "",
  issuingCountry: "",
  notes: "",
};

const MULTIPLE_SERIES = new Set(["educational_certificate", "other"]);

export function DocumentUploadDialog({
  employeeId,
  types,
  documents,
  replacing,
  onClose,
  onSaved,
}: {
  employeeId: string;
  types: DocumentType[];
  documents: DocumentSeries[];
  replacing?: DocumentSeries;
  onClose: () => void;
  onSaved: (message: string) => void;
}) {
  const { api } = useSession();
  const [typeId, setTypeId] = useState(replacing?.typeId ?? "");
  const [values, setValues] = useState<Values>(
    replacing
      ? {
          documentNumber: replacing.latest.documentNumber ?? "",
          issueDate: "",
          expiryDate: "",
          issuingCountry: replacing.latest.issuingCountry ?? "",
          notes: "",
        }
      : EMPTY,
  );
  const [files, setFiles] = useState<FileList | null>(null);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const replay = useRef({ signature: "", key: "" });

  const type = types.find((item) => item.id === typeId);
  const currentTypes = new Set(
    documents
      .filter((item) => item.status === "Current")
      .map((item) => item.typeId),
  );
  const typeOptions = types.map((item) => ({
    value: item.id,
    label: item.name,
    description:
      currentTypes.has(item.id) && !MULTIPLE_SERIES.has(item.code)
        ? "On file. Replace the current version instead."
        : item.requiredAtOnboarding
          ? "Required at onboarding"
          : undefined,
    disabled: currentTypes.has(item.id) && !MULTIPLE_SERIES.has(item.code),
  }));

  const set = (key: keyof Values, value: string) => {
    setValues((current) => ({ ...current, [key]: value }));
    setErrors((current) => {
      const next = { ...current };
      delete next[key];
      return next;
    });
    setError("");
  };
  const shown = (mode: FieldMode | undefined) => Boolean(mode) && mode !== "none";
  const required = (mode: FieldMode | undefined) => mode === "required";

  const submit = async () => {
    if (busy) return;
    const local: Record<string, string> = {};
    const file = files?.[0];
    if (!type) local.typeId = "Select a document type";
    if (!file) local.file = "Select a PDF, JPEG, or PNG file";
    else if (file.size > DOCUMENT_MAX_BYTES)
      local.file = "The file must be 5 MB (5,000,000 bytes) or smaller";
    if (type) {
      if (required(type.numberMode) && !values.documentNumber.trim())
        local.documentNumber = "Document number is required";
      if (required(type.issueDateMode) && !values.issueDate)
        local.issueDate = "Issue date is required";
      if (required(type.expiryDateMode) && !values.expiryDate)
        local.expiryDate = "Expiry date is required";
      if (required(type.countryMode) && !values.issuingCountry)
        local.issuingCountry = "Issuing country is required";
    }
    if (
      values.issueDate &&
      values.expiryDate &&
      values.expiryDate < values.issueDate
    )
      local.expiryDate = "Expiry date cannot be before the issue date";
    if (Object.keys(local).length || !type || !file) {
      setErrors(local);
      return;
    }
    const body = new FormData();
    body.append("file", file);
    const fields: [keyof Values, FieldMode][] = [
      ["documentNumber", type.numberMode],
      ["issueDate", type.issueDateMode],
      ["expiryDate", type.expiryDateMode],
      ["issuingCountry", type.countryMode],
    ];
    for (const [key, mode] of fields)
      if (mode !== "none" && values[key].trim())
        body.append(key, values[key].trim());
    if (values.notes.trim()) body.append("notes", values.notes.trim());
    if (replacing) body.append("replacesVersion", String(replacing.latest.version));
    else body.append("documentTypeId", type.id);
    const signature = JSON.stringify([
      typeId,
      values,
      file.name,
      file.size,
      file.lastModified,
    ]);
    if (replay.current.signature !== signature)
      replay.current = { signature, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      await api.request(
        replacing
          ? `/employee-documents/${replacing.seriesId}/versions`
          : `/employees/${employeeId}/documents`,
        {
          method: "POST",
          body,
          headers: { "Idempotency-Key": replay.current.key },
        },
      );
      onSaved(
        replacing
          ? `${type.name} replaced. The previous version is kept as Superseded.`
          : `${type.name} uploaded.`,
      );
    } catch (failure) {
      setError(failureMessage(failure));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      title={replacing ? `Replace ${replacing.typeName}` : "Upload document"}
      busy={busy}
      onClose={onClose}
      closeOnOutside={!busy}
      footer={
        <>
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
          <Button loading={busy} onClick={() => void submit()}>
            {replacing ? "Upload new version" : "Upload document"}
          </Button>
        </>
      }
    >
      <FormLayout columns={2}>
        {replacing ? (
          <InlineNotice tone="info" title="New version">
            Version {replacing.latest.version} becomes Superseded and stays
            available as read-only history.
          </InlineNotice>
        ) : (
          <FormField
            label="Document type"
            htmlFor="employee-document-type"
            required
            error={errors.typeId}
          >
            <DropdownSelect
              id="employee-document-type"
              options={typeOptions}
              value={typeId}
              onChange={(value) => {
                setTypeId(Array.isArray(value) ? (value[0] ?? "") : value);
                setErrors({});
                setError("");
              }}
              required
              clearable={false}
              invalid={Boolean(errors.typeId)}
            />
          </FormField>
        )}
        {type && shown(type.numberMode) ? (
          <FormField
            label="Document number"
            htmlFor="employee-document-number"
            required={required(type.numberMode)}
            error={errors.documentNumber}
          >
            {type.code === "emirates_id" ? (
              <EmiratesIdInput
                id="employee-document-number"
                value={values.documentNumber}
                onValueChange={(value) => set("documentNumber", value)}
                invalid={Boolean(errors.documentNumber)}
              />
            ) : (
              <TextInput
                id="employee-document-number"
                maxLength={100}
                value={values.documentNumber}
                onChange={(event) => set("documentNumber", event.target.value)}
                invalid={Boolean(errors.documentNumber)}
              />
            )}
          </FormField>
        ) : null}
        {type && shown(type.issueDateMode) ? (
          <FormField
            label="Issue date"
            htmlFor="employee-document-issue"
            required={required(type.issueDateMode)}
            error={errors.issueDate}
          >
            <DatePicker
              id="employee-document-issue"
              value={values.issueDate}
              onChange={(value) => set("issueDate", value)}
              invalid={Boolean(errors.issueDate)}
            />
          </FormField>
        ) : null}
        {type && shown(type.expiryDateMode) ? (
          <FormField
            label="Expiry date"
            htmlFor="employee-document-expiry"
            required={required(type.expiryDateMode)}
            error={errors.expiryDate}
          >
            <DatePicker
              id="employee-document-expiry"
              value={values.expiryDate}
              onChange={(value) => set("expiryDate", value)}
              invalid={Boolean(errors.expiryDate)}
            />
          </FormField>
        ) : null}
        {type && shown(type.countryMode) ? (
          <FormField
            label="Issuing country"
            htmlFor="employee-document-country"
            required={required(type.countryMode)}
            error={errors.issuingCountry}
          >
            <CountrySelect
              id="employee-document-country"
              label=""
              value={values.issuingCountry}
              onChange={(value) => set("issuingCountry", value)}
              invalid={Boolean(errors.issuingCountry)}
            />
          </FormField>
        ) : null}
        {type ? (
          <FormField label="Notes" htmlFor="employee-document-notes">
            <TextArea
              id="employee-document-notes"
              maxLength={1000}
              value={values.notes}
              onChange={(event) => set("notes", event.target.value)}
            />
          </FormField>
        ) : null}
        <FileUpload
          id="employee-document-file"
          label="File"
          hint="PDF, JPEG, or PNG. Maximum 5 MB."
          accept={DOCUMENT_ACCEPT}
          files={files}
          busy={busy}
          error={errors.file}
          onChange={(next) => {
            setFiles(next);
            setErrors((current) => {
              const copy = { ...current };
              delete copy.file;
              return copy;
            });
          }}
        />
        {error ? (
          <InlineNotice tone="error" title="Unable to upload">
            {error}
          </InlineNotice>
        ) : null}
      </FormLayout>
    </Dialog>
  );
}
