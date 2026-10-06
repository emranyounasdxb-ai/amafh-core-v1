import { cx } from "../lib/cx";

export function Skeleton({
  width,
  height,
  className,
}: {
  width?: string;
  height?: string;
  className?: string;
}) {
  return (
    <span
      className={cx("ds-skeleton", className)}
      style={{ width, height }}
      aria-hidden="true"
    />
  );
}

export function SkeletonText({ lines = 2 }: { lines?: number }) {
  return (
    <div className="ds-skeleton-stack">
      {Array.from({ length: lines }, (_, index) => (
        <Skeleton
          key={index}
          height="12px"
          width={index === lines - 1 ? "64%" : "100%"}
        />
      ))}
    </div>
  );
}

export function SkeletonControl() {
  return <Skeleton className="ds-skeleton--control" />;
}
