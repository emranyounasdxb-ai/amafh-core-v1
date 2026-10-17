import { Button, FormField, TextInput } from "../../../design-system";
import type { Field } from "../../../app/api/commands";
import type { DataRecord } from "../../../app/api/models";
import type { SalaryPoints } from "./salaryPoints";
import styles from "./FinancePage.module.css";

export function salaryPointsField({
  field,
  values,
  change,
  disabled,
  error,
}: {
  field: Field;
  values: DataRecord;
  change: (key: string, value: unknown) => void;
  disabled: boolean;
  error?: string;
}) {
  if (field.key !== "ccSalaryPoints") return undefined;
  const rows = (values.ccSalaryPoints || []) as SalaryPoints[];
  const set = (index: number, key: keyof SalaryPoints, value: string) =>
    change(
      field.key,
      rows.map((row, i) => (i === index ? { ...row, [key]: value } : row)),
    );
  return (
    <section
      className={styles.salaryEditor}
      aria-label="Salary ranges and points"
    >
      <div>
        <h3>Salary ranges and points</h3>
        <p className={styles.support}>
          Uses the salary saved when the case was created. Both limits are
          included; ranges must not overlap. Commission AED is configured
          separately and does not change with salary.
        </p>
      </div>
      {rows.map((row, index) => (
        <div className={styles.salaryRow} key={index}>
          {(
            [
              ["salaryMin", "Salary from AED"],
              ["salaryMax", "Salary to AED"],
              ["points", "Points"],
            ] as const
          ).map(([key, label]) => (
            <FormField
              key={key}
              label={label}
              htmlFor={`salary-points-${index}-${key}`}
              required
            >
              <TextInput
                id={`salary-points-${index}-${key}`}
                inputMode="numeric"
                autoComplete="off"
                value={String(row[key])}
                disabled={disabled}
                onChange={(event) => set(index, key, event.target.value)}
                aria-label={`Range ${index + 1} ${label}`}
              />
            </FormField>
          ))}
          <Button
            size="compact"
            variant="ghost"
            disabled={disabled || rows.length === 1}
            onClick={() =>
              change(
                field.key,
                rows.filter((_, i) => i !== index),
              )
            }
            aria-label={`Remove salary range ${index + 1}`}
          >
            Remove
          </Button>
        </div>
      ))}
      <Button
        size="compact"
        variant="secondary"
        disabled={disabled || rows.length >= 100}
        onClick={() =>
          change(field.key, [
            ...rows,
            { salaryMin: "", salaryMax: "", points: "" },
          ])
        }
      >
        Add salary range
      </Button>
      {error ? (
        <p className="ds-field__error" role="alert">
          {error}
        </p>
      ) : null}
    </section>
  );
}
