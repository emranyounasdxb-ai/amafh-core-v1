import type { InputHTMLAttributes } from "react";
import { DsIcon } from "../icons";
import { NumberInput } from "./NumberInput";
import { TextArea } from "./TextArea";
import { TextInput } from "./TextInput";
import { Tag } from "./Display";

export function EmailInput(
  props: InputHTMLAttributes<HTMLInputElement> & {
    compact?: boolean;
    invalid?: boolean;
  },
) {
  return (
    <TextInput {...props} type="email" inputMode="email" autoComplete="email" />
  );
}

export function PercentageInput(
  props: Omit<InputHTMLAttributes<HTMLInputElement>, "type"> & {
    compact?: boolean;
    invalid?: boolean;
  },
) {
  return <NumberInput {...props} suffix="%" />;
}

export function TimePicker({
  id,
  value,
  onChange,
  compact,
  disabled,
  readOnly,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  compact?: boolean;
  disabled?: boolean;
  readOnly?: boolean;
}) {
  return (
    <TextInput
      id={id}
      type="time"
      compact={compact}
      disabled={disabled}
      readOnly={readOnly}
      value={value}
      onChange={(event) => onChange(event.target.value)}
    />
  );
}

export function CountedTextArea({
  id,
  value,
  onChange,
  maxLength = 240,
  rows = 3,
}: {
  id: string;
  value: string;
  onChange: (value: string) => void;
  maxLength?: number;
  rows?: number;
}) {
  return (
    <div className="ds-counted">
      <TextArea
        id={id}
        rows={rows}
        maxLength={maxLength}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
      <p className="ds-field__hint">
        {value.length} / {maxLength}
      </p>
    </div>
  );
}

export function TagsInput({
  values,
  onChange,
  placeholder = "Add tag",
}: {
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
}) {
  return (
    <div className="ds-combo ds-combo--multi">
      <div className="ds-combo__chips">
        {values.map((item) => (
          <Tag
            key={item}
            onRemove={() => onChange(values.filter((value) => value !== item))}
          >
            {item}
          </Tag>
        ))}
        <input
          className="ds-combo__input"
          placeholder={placeholder}
          onKeyDown={(event) => {
            if (event.key === "Enter") {
              event.preventDefault();
              const next = event.currentTarget.value.trim();
              if (next && !values.includes(next)) onChange([...values, next]);
              event.currentTarget.value = "";
            }
          }}
        />
      </div>
      {values.length ? (
        <button
          type="button"
          className="ds-combo__clear"
          aria-label="Clear tags"
          onClick={() => onChange([])}
        >
          <DsIcon name="close" size={14} />
        </button>
      ) : null}
    </div>
  );
}

export { NoResultsState, OfflineState } from "./FeedbackState";

