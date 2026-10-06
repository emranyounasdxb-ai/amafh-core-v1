import { SectionCard } from "../components/SectionCard";
import { Timeline, type TimelineItem } from "../components/Timeline";

export function ActivityTimeline({
  title = "Activity",
  description,
  items,
  compact,
}: {
  title?: string;
  description?: string;
  items: TimelineItem[];
  compact?: boolean;
}) {
  return (
    <SectionCard title={title} description={description}>
      <Timeline items={items} compact={compact} />
    </SectionCard>
  );
}
