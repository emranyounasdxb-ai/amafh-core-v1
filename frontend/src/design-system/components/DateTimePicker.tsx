import type { DateOnly } from "../lib/dateOnly";
import { DatePicker } from "./DatePicker";
import { TextInput } from "./TextInput";

export type DateTimeValue = { date: DateOnly | ""; time: string };

export function DateTimePicker({
  id,
  value,
  onChange,
  disabled,
  readOnly,
  invalid,
  compact,
}: {
  id: string;
  value: DateTimeValue;
  onChange: (value: DateTimeValue) => void;
  disabled?: boolean;
  readOnly?: boolean;
  invalid?: boolean;
  compact?: boolean;
}) {
  return (
    <div className="ds-datetime">
      <DatePicker
        id={id}
        value={value.date}
        onChange={(date) => onChange({ ...value, date })}
        disabled={disabled}
        readOnly={readOnly}
        invalid={invalid}
        compact={compact}
      />
      <TextInput
        type="time"
        compact={compact}
        disabled={disabled}
        readOnly={readOnly}
        aria-label="Time"
        value={value.time}
        onChange={(event) => onChange({ ...value, time: event.target.value })}
      />
    </div>
  );
}
