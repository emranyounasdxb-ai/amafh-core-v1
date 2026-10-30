/** Local external numbers start with 0; a recorded + also identifies an external number. */
export function callType(
  first: string,
  second: string,
  filename = "",
): "Internal" | "External" {
  // Searchable values are digits only. Retain the original filename's explicit
  // international marker for the badge, without guessing from number length.
  const participants =
    /^auto-[0-9]+-([+]?[0-9]{1,32})-(?:##)?([+]?[0-9]{1,32})\.wav$/i.exec(
      filename,
    );
  const hasPlus =
    participants?.[1].startsWith("+") || participants?.[2].startsWith("+");
  return first.startsWith("0") || second.startsWith("0") || hasPlus
    ? "External"
    : "Internal";
}

export function playbackTime(seconds: number): string {
  if (!Number.isFinite(seconds) || seconds < 0) return "0:00";
  const whole = Math.floor(seconds);
  return `${Math.floor(whole / 60)}:${String(whole % 60).padStart(2, "0")}`;
}
