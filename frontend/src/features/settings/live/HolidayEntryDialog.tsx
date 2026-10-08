import { useRef, useState } from "react";
import {
  Button,
  CompactDate,
  DatePicker,
  DataTable,
  Dialog,
  FormField,
  InlineNotice,
  TextInput,
} from "../../../design-system";
import { ApiFailure } from "../../../app/api/http";
import { useSession } from "../../../app/session/useSession";
import {
  reviewHolidayRows,
  type ExpandedHoliday,
  type HolidayRow,
} from "./holidayRanges";
import styles from "./HolidayEntryDialog.module.css";

const emptyRow = (): HolidayRow => ({
  name: "",
  startDate: "",
  endDate: "",
  sourceReference: "",
});
const fields = [
  ["name", "Holiday name"],
  ["startDate", "Start date"],
  ["endDate", "End date"],
  ["sourceReference", "Official source reference"],
] as const;

export function HolidayEntryDialog({
  bulk,
  onClose,
  onSaved,
}: {
  bulk: boolean;
  onClose: () => void;
  onSaved: (count: number) => void;
}) {
  const { api } = useSession();
  const sequence = useRef(1);
  const [rows, setRows] = useState([{ key: 0, values: emptyRow() }]);
  const [errors, setErrors] = useState<Record<string, string[]>>({});
  const [error, setError] = useState("");
  const [review, setReview] = useState<ExpandedHoliday[] | null>(null);
  const [busy, setBusy] = useState(false);
  const changed = () => {
    setReview(null);
    setErrors({});
    setError("");
  };
  const update = (key: number, field: keyof HolidayRow, value: string) => {
    changed();
    setRows((current) =>
      current.map((row) =>
        row.key === key
          ? { ...row, values: { ...row.values, [field]: value } }
          : row,
      ),
    );
  };
  const submit = async () => {
    if (busy) return;
    const checked = reviewHolidayRows(rows.map((row) => row.values));
    if (Object.keys(checked.errors).length) {
      setErrors(checked.errors);
      setError("Review the affected rows. No holidays have been saved.");
      setReview(null);
      return;
    }
    if (!review) {
      setReview(checked.dates);
      setError("");
      return;
    }
    setBusy(true);
    setError("");
    try {
      const result = await api.request<unknown[]>(
        "/performance/uae-holidays/bulk",
        {
          method: "POST",
          body: JSON.stringify({ rows: rows.map((row) => row.values) }),
        },
      );
      onSaved(result.length);
    } catch (failure) {
      setErrors(failure instanceof ApiFailure ? failure.fieldErrors : {});
      setError(
        failure instanceof ApiFailure
          ? failure.message
          : "Unable to save. Your entered values are retained.",
      );
      setReview(null);
    } finally {
      setBusy(false);
    }
  };
  const renderField = (
    row: (typeof rows)[number],
    field: (typeof fields)[number][0],
    label: string,
  ) => {
    const index = rows.findIndex((entry) => entry.key === row.key);
    const id = `holiday-${row.key}-${field}`;
    const fieldError = errors[`rows.${index}.${field}`];
    return (
      <FormField
        label={label}
        htmlFor={id}
        required
        error={fieldError?.join(" ")}
      >
        {field === "startDate" || field === "endDate" ? (
          <DatePicker
            id={id}
            value={row.values[field]}
            compact
            required
            disabled={busy}
            invalid={Boolean(fieldError)}
            onChange={(value) => update(row.key, field, value)}
          />
        ) : (
          <TextInput
            id={id}
            compact
            required
            disabled={busy}
            invalid={Boolean(fieldError)}
            maxLength={field === "name" ? 200 : 1000}
            value={row.values[field]}
            onChange={(event) => update(row.key, field, event.target.value)}
          />
        )}
      </FormField>
    );
  };
  return (
    <Dialog
      open
      title={bulk ? "Bulk Add Holidays" : "Add Holiday"}
      description="Single-day holidays use the same start and end date. Review every expanded date before saving."
      size={bulk ? "xl" : "lg"}
      busy={busy}
      onClose={onClose}
      closeOnOutside={false}
      footer={
        <>
          <Button variant="secondary" disabled={busy} onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" form="holiday-entry" loading={busy}>
            {review ? "Save Holidays" : "Review Dates"}
          </Button>
        </>
      }
    >
      <form
        id="holiday-entry"
        className={`${styles.form} ${styles.controls}`}
        noValidate
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        {error ? (
          <InlineNotice tone="error" title="Holidays not saved">
            {error}
          </InlineNotice>
        ) : null}
        {errors.rows ? (
          <p role="alert" className={styles.error}>
            {errors.rows.join(" ")}
          </p>
        ) : null}
        {bulk ? (
          <DataTable
            tableId="holiday-entry"
            ariaLabel="Holiday entry rows"
            className={styles.entryTable}
            rows={rows}
            rowKey={(row) => String(row.key)}
            columns={[
              ...fields.map(([field, label]) => ({
                key: field,
                header: label,
                width:
                  field === "startDate" || field === "endDate"
                    ? "190px"
                    : field === "name"
                      ? "200px"
                      : "220px",
                minWidth:
                  field === "startDate" || field === "endDate" ? 190 : 96,
                render: (row: (typeof rows)[number]) => (
                  <>
                    {renderField(row, field, label)}
                    {field === "name" &&
                    errors[
                      `rows.${rows.findIndex((entry) => entry.key === row.key)}`
                    ] ? (
                      <p className={styles.error} role="alert">
                        Row{" "}
                        {rows.findIndex((entry) => entry.key === row.key) + 1}:{" "}
                        {errors[
                          `rows.${rows.findIndex((entry) => entry.key === row.key)}`
                        ].join(" ")}
                      </p>
                    ) : null}
                  </>
                ),
              })),
              {
                key: "actions",
                header: "Actions",
                width: "96px",
                fixed: true,
                render: (row) => (
                  <Button
                    size="compact"
                    variant="ghost"
                    disabled={busy}
                    aria-label={`Remove holiday row ${rows.findIndex((entry) => entry.key === row.key) + 1}`}
                    onClick={() => {
                      changed();
                      setRows((current) =>
                        current.filter((item) => item.key !== row.key),
                      );
                    }}
                  >
                    Remove
                  </Button>
                ),
              },
            ]}
          />
        ) : (
          <div className={styles.single}>
            {fields.map(([field, label]) => (
              <div key={field}>{renderField(rows[0], field, label)}</div>
            ))}
            {errors["rows.0"] ? (
              <p className={styles.error} role="alert">
                Row 1: {errors["rows.0"].join(" ")}
              </p>
            ) : null}
          </div>
        )}
        {bulk ? (
          <Button
            size="compact"
            variant="secondary"
            disabled={busy || rows.length >= 366}
            onClick={() => {
              changed();
              setRows((current) => [
                ...current,
                { key: sequence.current++, values: emptyRow() },
              ]);
            }}
          >
            Add Row
          </Button>
        ) : null}
        {review ? (
          <section
            className={styles.review}
            aria-label="Expanded holiday dates"
          >
            <h3>
              Review {review.length} holiday{" "}
              {review.length === 1 ? "date" : "dates"}
            </h3>
            <p>
              All dates below will be saved together. Editing any row requires a
              new review.
            </p>
            <DataTable
              tableId="holiday-date-review"
              ariaLabel="Expanded holiday dates review"
              className={styles.reviewTable}
              rows={review}
              rowKey={(day) => `${day.row}-${day.holidayDate}`}
              columns={[
                {
                  key: "row",
                  header: "Source row",
                  width: "96px",
                  kind: "number",
                },
                {
                  key: "holidayDate",
                  header: "Date",
                  width: "140px",
                  kind: "date",
                  render: (day) => <CompactDate value={day.holidayDate} />,
                },
                { key: "name", header: "Holiday name", width: "220px" },
                {
                  key: "sourceReference",
                  header: "Official reference",
                  width: "300px",
                },
              ]}
            />
          </section>
        ) : null}
      </form>
    </Dialog>
  );
}
