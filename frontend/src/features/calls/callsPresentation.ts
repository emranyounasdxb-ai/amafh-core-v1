/** PBX numbering rule confirmed by the Owner: external numbers start with 0. */
export function callType(
  first: string,
  second: string,
): "Internal" | "External" {
  return first.startsWith("0") || second.startsWith("0")
    ? "External"
    : "Internal";
}

export function playbackTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
