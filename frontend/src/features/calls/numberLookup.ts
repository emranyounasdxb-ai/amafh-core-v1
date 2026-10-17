export const NUMBER_SUGGESTION_DELAY_MS = 300;

export function numberSuggestionPrefix(value: string): string | null {
  const prefix = value.trim();
  return /^[0-9]{3,32}$/.test(prefix) ? prefix : null;
}
