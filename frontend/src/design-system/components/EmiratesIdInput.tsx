import { useRef, type ComponentProps } from "react";
import { TextInput } from "./TextInput";

const digitsOnly = (value: string) => value.replace(/[^0-9]/g, "");
const allowedCharacters = /^[0-9\s-]*$/;

function displayValue(value: string): string {
  const digits = digitsOnly(value);
  // Keep legacy values intact: displaying a mask must never rewrite an ID.
  if (!allowedCharacters.test(value) || digits.length > 15) return value;
  return [
    digits.slice(0, 3),
    digits.slice(3, 7),
    digits.slice(7, 14),
    digits.slice(14),
  ]
    .filter(Boolean)
    .join("-");
}

function caretAtDigit(value: string, count: number, afterSeparator = true) {
  if (!count) return 0;
  let seen = 0;
  for (let index = 0; index < value.length; index++) {
    if (/[0-9]/.test(value[index]) && ++seen === count) {
      const position = index + 1;
      return afterSeparator && value[position] === "-" ? position + 1 : position;
    }
  }
  return value.length;
}

type Props = Omit<
  ComponentProps<typeof TextInput>,
  | "value"
  | "defaultValue"
  | "onChange"
  | "type"
  | "inputMode"
  | "maxLength"
  | "placeholder"
> & {
  value: string;
  /** The mask is presentation only; edited values remain numeric ID strings. */
  onValueChange: (value: string) => void;
};

export function EmiratesIdInput({
  value,
  onValueChange,
  onKeyDown,
  onBeforeInput,
  onPaste,
  ...props
}: Props) {
  const selection = useRef({ start: 0, end: 0 });
  const displayed = displayValue(value);

  function remember(input: HTMLInputElement) {
    selection.current = {
      start: input.selectionStart ?? 0,
      end: input.selectionEnd ?? 0,
    };
  }

  function update(
    input: HTMLInputElement,
    next: string,
    digitPosition: number,
    afterSeparator = true,
  ) {
    const formatted = displayValue(next);
    const caret = caretAtDigit(formatted, digitPosition, afterSeparator);
    // Normalize before React restores the controlled value, so it does not
    // replace the DOM value afterward and move the caret to the end.
    input.value = formatted;
    input.setSelectionRange(caret, caret);
    remember(input);
    onValueChange(next);
  }

  return (
    <TextInput
      {...props}
      type="text"
      inputMode="numeric"
      placeholder="784-XXXX-XXXXXXX-X"
      value={displayed}
      onBeforeInput={(event) => {
        onBeforeInput?.(event);
        remember(event.currentTarget);
      }}
      onKeyDown={(event) => {
        onKeyDown?.(event);
        const input = event.currentTarget;
        remember(input);
        if (event.defaultPrevented || input.readOnly || input.disabled) return;
        const { start, end } = selection.current;
        if (
          start !== end ||
          event.altKey ||
          event.ctrlKey ||
          event.metaKey ||
          !allowedCharacters.test(input.value)
        )
          return;
        const backward =
          event.key === "Backspace" && input.value[start - 1] === "-";
        const forward = event.key === "Delete" && input.value[start] === "-";
        if (!backward && !forward) return;
        event.preventDefault();
        const digits = digitsOnly(input.value);
        const position = digitsOnly(input.value.slice(0, start)).length;
        const remove = backward ? position - 1 : position;
        update(
          input,
          digits.slice(0, remove) + digits.slice(remove + 1),
          remove,
          false,
        );
      }}
      onPaste={(event) => {
        onPaste?.(event);
        const input = event.currentTarget;
        if (event.defaultPrevented || input.readOnly || input.disabled) return;
        event.preventDefault();
        const text = event.clipboardData.getData("text");
        if (!allowedCharacters.test(text)) return;
        const pasted = digitsOnly(text);
        // Reject the entire overlong paste, even if a selection could hide it.
        if (pasted.length > 15) return;
        const start = input.selectionStart ?? 0;
        const end = input.selectionEnd ?? start;
        const prefix = input.value.slice(0, start);
        const suffix = input.value.slice(end);
        if (!allowedCharacters.test(prefix + suffix)) return;
        const before = digitsOnly(prefix);
        const after = digitsOnly(suffix);
        const next = before + pasted + after;
        if (next.length > 15) return;
        update(input, next, before.length + pasted.length);
      }}
      onChange={(event) => {
        const input = event.currentTarget;
        const raw = input.value;
        const digits = digitsOnly(raw);
        const previous = digitsOnly(value);
        if (
          (!allowedCharacters.test(raw) &&
            (allowedCharacters.test(displayed) || raw.length >= displayed.length)) ||
          (digits.length > 15 && digits.length >= previous.length)
        ) {
          input.value = displayed;
          input.setSelectionRange(selection.current.start, selection.current.end);
          return;
        }
        if (!allowedCharacters.test(raw)) {
          // Allow correcting a legacy nonnumeric value without dropping its contents.
          onValueChange(raw);
          return;
        }
        const position = digitsOnly(
          raw.slice(0, input.selectionStart ?? 0),
        ).length;
        const inputType = (event.nativeEvent as InputEvent).inputType;
        const separatorPosition =
          inputType === "deleteContentBackward"
            ? selection.current.start - 1
            : selection.current.start;
        if (
          digits === previous &&
          (inputType === "deleteContentBackward" ||
            inputType === "deleteContentForward") &&
          selection.current.start === selection.current.end &&
          displayed[separatorPosition] === "-" &&
          raw ===
            displayed.slice(0, separatorPosition) +
              displayed.slice(separatorPosition + 1)
        ) {
          // Touch keyboards can delete a separator without emitting keydown.
          const remove =
            inputType === "deleteContentBackward" ? position - 1 : position;
          if (remove >= 0 && remove < digits.length) {
            update(
              input,
              digits.slice(0, remove) + digits.slice(remove + 1),
              remove,
              false,
            );
            return;
          }
        }
        update(input, digits, position);
      }}
      onSelect={(event) => {
        props.onSelect?.(event);
        remember(event.currentTarget);
      }}
    />
  );
}
