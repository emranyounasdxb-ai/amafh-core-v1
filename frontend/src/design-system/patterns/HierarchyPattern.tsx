import { useMemo, useState, type ReactNode } from "react";
import { Button } from "../components/Button";
import { DsIcon } from "../icons";
import { EmptyState } from "../components/EmptyState";
import {
  HierarchyToolbar,
  HierarchyTree,
  type HierarchyNodeData,
} from "../components/Hierarchy";
import { IconButton } from "../components/IconButton";
import { SectionCard } from "../components/SectionCard";

function collectIds(nodes: HierarchyNodeData[]): string[] {
  return nodes.flatMap((node) => [
    node.id,
    ...(node.children ? collectIds(node.children) : []),
  ]);
}

export function HierarchyPattern({
  title = "Organization",
  description = "Expand nodes to review reporting lines. Structure comes from supplied data.",
  nodes,
  empty,
  unavailable,
}: {
  title?: string;
  description?: string;
  nodes: HierarchyNodeData[];
  empty?: ReactNode;
  unavailable?: boolean;
}) {
  const allIds = useMemo(() => collectIds(nodes), [nodes]);
  const [expanded, setExpanded] = useState<string[]>(
    nodes[0] ? [nodes[0].id] : [],
  );
  const [selected, setSelected] = useState<string | undefined>(nodes[0]?.id);
  const [scale, setScale] = useState(1);

  const toggle = (id: string, siblings: HierarchyNodeData[]) => {
    setExpanded((current) => {
      const isOpen = current.includes(id);
      if (isOpen) return current.filter((item) => item !== id);
      const siblingIds = siblings.map((item) => item.id);
      return [...current.filter((item) => !siblingIds.includes(item)), id];
    });
  };

  return (
    <SectionCard title={title} description={description}>
      <HierarchyToolbar>
        <Button
          size="compact"
          variant="secondary"
          onClick={() => setExpanded(allIds)}
        >
          Expand all
        </Button>
        <Button size="compact" variant="ghost" onClick={() => setExpanded([])}>
          Collapse
        </Button>
        <IconButton
          label="Zoom out"
          variant="ghost"
          size="compact"
          onClick={() => setScale((current) => Math.max(0.75, current - 0.1))}
        >
          <DsIcon name="skipped" size={16} />
        </IconButton>
        <IconButton
          label="Zoom in"
          variant="ghost"
          size="compact"
          onClick={() => setScale((current) => Math.min(1.25, current + 0.1))}
        >
          <DsIcon name="add" size={16} />
        </IconButton>
      </HierarchyToolbar>
      <div className="ds-h-overflow">
        {unavailable ? (
          <EmptyState
            title="Hierarchy unavailable"
            description="This structure cannot be shown with the current prerequisites."
          />
        ) : (
          <div className="ds-h-scale" style={{ transform: `scale(${scale})` }}>
            <HierarchyTree
              nodes={nodes}
              expandedIds={expanded}
              selectedId={selected}
              singleOpen
              onToggle={toggle}
              onSelect={setSelected}
              empty={
                empty ?? (
                  <EmptyState
                    title="No hierarchy"
                    description="No authorized nodes are available."
                  />
                )
              }
            />
          </div>
        )}
      </div>
    </SectionCard>
  );
}
