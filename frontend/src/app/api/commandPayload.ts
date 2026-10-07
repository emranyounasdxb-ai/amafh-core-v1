import { roundWholeText } from "../numbers/wholeNumber.ts";
import type { Command, Field } from "./commands";
import type { DataRecord } from "./models";

export function initialField(field: Field, record: DataRecord): unknown {
  const snake = field.key.replace(/[A-Z]/g, (c) => `_${c.toLowerCase()}`);
  const value =
    record[field.key] ??
    record[snake] ??
    field.initial ??
    (field.type === "checkbox" ? false : "");
  if (
    field.type === "datetime-local" &&
    typeof value === "string" &&
    value &&
    /Z|[+-]\d\d:\d\d$/.test(value)
  ) {
    return new Intl.DateTimeFormat("sv-SE", {
      timeZone: "Asia/Dubai",
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    })
      .format(new Date(value))
      .replace(" ", "T");
  }
  if (field.type === "month" && typeof value === "string")
    return value.slice(0, 7);
  return value;
}
export function commandPayload(command: Command, values: DataRecord): string {
  const body: DataRecord = { ...command.fixed };
  for (const field of command.fields) {
    if (field.show && !field.show(values)) continue;
    const value = values[field.key];
    if (value === "" || value === undefined) {
      if (field.emptyAsNull) body[field.key] = null;
      continue;
    }
    body[field.key] =
      field.type === "number"
        ? Number(roundWholeText(value) ?? value)
        : field.type === "decimal"
          ? (roundWholeText(value) ?? value)
          : field.type === "datetime-local"
          ? `${String(value).slice(0, 16)}:00+04:00`
          : field.type === "month"
            ? `${value}-01`
            : value;
  }
  return JSON.stringify(command.transform ? command.transform(body) : body);
}
