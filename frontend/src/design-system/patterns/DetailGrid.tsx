import { InfoField } from "../components/InfoField";
import { InfoGrid } from "../components/InfoGrid";
import { SectionCard } from "../components/SectionCard";

export type DetailItem = {
  label: string;
  value: string | number;
  numeric?: boolean;
};

export function DetailGrid({
  title = "Details",
  description,
  items,
}: {
  title?: string;
  description?: string;
  items: DetailItem[];
}) {
  return (
    <SectionCard title={title} description={description}>
      <InfoGrid>
        {items.map((item) => (
          <InfoField
            key={item.label}
            label={item.label}
            value={item.value}
            numeric={item.numeric}
          />
        ))}
      </InfoGrid>
    </SectionCard>
  );
}
