import { moneyDisplaySymbol } from "../lib/money";

export function UaeDirhamSymbol({
  decorative = true,
}: {
  decorative?: boolean;
}) {
  return (
    <span
      className="ds-dirham"
      aria-hidden={decorative ? true : undefined}
    >
      {moneyDisplaySymbol()}
    </span>
  );
}
