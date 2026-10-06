import type { ReactNode } from "react";
import { StatusBadge, type StatusTone } from "../components/StatusBadge";
import { SectionCard } from "../components/SectionCard";

export type RelatedRecordItem = {
  id: string;
  title: ReactNode;
  meta?: ReactNode;
  status?: ReactNode;
  statusTone?: StatusTone;
  onOpen?: () => void;
};

export function RelatedRecordList({
  title,
  description,
  items,
}: {
  title: string;
  description?: string;
  items: RelatedRecordItem[];
}) {
  return (
    <SectionCard title={title} description={description}>
      <ul className="ds-related-list">
        {items.map((item) => {
          const body = (
            <>
              <div>
                <p className="ds-related-list__title">{item.title}</p>
                {item.meta ? (
                  <p className="ds-related-list__meta">{item.meta}</p>
                ) : null}
              </div>
              {item.status ? (
                <StatusBadge tone={item.statusTone}>{item.status}</StatusBadge>
              ) : null}
            </>
          );
          return (
            <li key={item.id}>
              {item.onOpen ? (
                <button
                  type="button"
                  className="ds-related-list__button"
                  onClick={item.onOpen}
                >
                  {body}
                </button>
              ) : (
                <div className="ds-related-list__item">{body}</div>
              )}
            </li>
          );
        })}
      </ul>
    </SectionCard>
  );
}
