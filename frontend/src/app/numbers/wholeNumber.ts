/**
 * Application-wide whole-number rule (DEC-051). Business amounts, points,
 * targets and percentages are whole numbers: a fraction rounds to the nearest
 * whole number and an exact half rounds away from zero (750.50 → 751,
 * -750.50 → -751). Rounding works on the decimal text so it never depends on
 * binary floating point.
 */

const NUMERIC = /^([+-]?)(\d*)(?:\.(\d*))?$/;

function incrementDigits(digits: string): string {
  const chars = digits.split("");
  for (let index = chars.length - 1; index >= 0; index -= 1) {
    if (chars[index] !== "9") {
      chars[index] = String(Number(chars[index]) + 1);
      return chars.join("");
    }
    chars[index] = "0";
  }
  return `1${chars.join("")}`;
}

/** Whole-number text for a typed or received value, or null when it is not a number. */
export function roundWholeText(value: unknown): string | null {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return null;
    return roundWholeText(String(value).includes("e") ? value.toFixed(20) : String(value));
  }
  if (typeof value !== "string") return null;
  const text = value.trim().replace(/,/g, "");
  const match = NUMERIC.exec(text);
  if (!match || (!match[2] && !match[3])) return null;
  const [, sign, rawWhole, fraction = ""] = match;
  let whole = rawWhole.replace(/^0+(?=\d)/, "") || "0";
  if (fraction && Number(fraction[0]) >= 5) whole = incrementDigits(whole);
  return whole === "0" || sign !== "-" ? whole : `-${whole}`;
}

/** Whole number for display and calculation, or null when not numeric. */
export function roundWhole(value: unknown): number | null {
  const text = roundWholeText(value);
  return text === null ? null : Number(text);
}
