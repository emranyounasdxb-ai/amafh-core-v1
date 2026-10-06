import type { KeyboardEvent, ReactNode } from "react";
import { DsIcon, type DsIconName } from "../icons";
import { cx } from "../lib/cx";
import { Avatar } from "./Avatar";
import { TruncatedText } from "./Display";
import { IconButton } from "./IconButton";
import { StatusBadge, type StatusTone } from "./StatusBadge";

export type HierarchyKind = "person" | "group";

export type HierarchyNodeData = {
  id: string;
  name: string;
  subtitle?: string;
  kind?: HierarchyKind;
  avatarSrc?: string;
  status?: string;
  statusTone?: StatusTone;
  count?: number;
  root?: boolean;
  loadingChildren?: boolean;
  activateLabel?: string;
  actionLabel?: string;
  actionIcon?: DsIconName;
  children?: HierarchyNodeData[];
};

export function HierarchyNode({
  node,
  expanded,
  selected,
  onToggle,
  onSelect,
  onAction,
}: {
  node: HierarchyNodeData;
  expanded?: boolean;
  selected?: boolean;
  onToggle?: () => void;
  onSelect?: () => void;
  onAction?: () => void;
}) {
  const kind = node.kind ?? "person";
  const expandable = Boolean(node.children?.length || node.loadingChildren);
  const onKey = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.target !== event.currentTarget) return;
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      onSelect?.();
    }
    if (
      (event.key === "ArrowRight" || event.key === "ArrowLeft") &&
      expandable
    ) {
      event.preventDefault();
      onToggle?.();
    }
  };
  return (
    <div
      className={cx(
        "ds-h-node",
        kind === "group" && "ds-h-node--group",
        node.root && "ds-h-node--root",
        selected && "ds-h-node--selected",
      )}
      role="treeitem"
      aria-expanded={expandable ? expanded : undefined}
      aria-selected={selected}
      aria-label={node.activateLabel}
      data-hierarchy-id={node.id}
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={onKey}
    >
      {expandable ? (
        <button
          type="button"
          className="ds-h-node__toggle"
          aria-label={
            expanded ? `Collapse ${node.name}` : `Expand ${node.name}`
          }
          onClick={(event) => {
            event.stopPropagation();
            onToggle?.();
          }}
        >
          {expanded ? (
            <DsIcon name="expand" size={14} />
          ) : (
            <DsIcon name="next" size={14} />
          )}
        </button>
      ) : (
        <span className="ds-h-node__toggle" />
      )}
      {kind === "person" ? (
        <Avatar name={node.name} src={node.avatarSrc} size="sm" />
      ) : null}
      <div className="ds-h-node__copy">
        <div className="ds-h-node__name">
          <TruncatedText value={node.name} />
        </div>
        {node.subtitle ? (
          <div className="ds-h-node__subtitle">
            <TruncatedText value={node.subtitle} />
          </div>
        ) : null}
      </div>
      {node.count != null ? <em>{node.count}</em> : null}
      {node.status ? (
        <StatusBadge tone={node.statusTone ?? "neutral"}>
          {node.status}
        </StatusBadge>
      ) : null}
      {node.actionLabel && onAction ? (
        <span
          className="ds-h-node__action"
          onClick={(event) => event.stopPropagation()}
          onKeyDown={(event) => event.stopPropagation()}
        >
          <IconButton
            label={node.actionLabel}
            variant="ghost"
            size="compact"
            onClick={onAction}
          >
            <DsIcon name={node.actionIcon ?? "forward"} size={16} />
          </IconButton>
        </span>
      ) : null}
    </div>
  );
}

export function HierarchyBranch({
  nodes,
  expandedIds,
  selectedId,
  singleOpen = false,
  onToggle,
  onSelect,
  onAction,
}: {
  nodes: HierarchyNodeData[];
  expandedIds: string[];
  selectedId?: string;
  singleOpen?: boolean;
  onToggle: (id: string, siblings: HierarchyNodeData[]) => void;
  onSelect?: (id: string) => void;
  onAction?: (id: string) => void;
}) {
  return (
    <div className="ds-h-row" role="group">
      {nodes.map((node) => {
        const expanded = expandedIds.includes(node.id);
        return (
          <div key={node.id} className="ds-h-unit">
            <div className="ds-h-connector" aria-hidden="true" />
            <HierarchyNode
              node={node}
              expanded={expanded}
              selected={selectedId === node.id}
              onToggle={() => onToggle(node.id, singleOpen ? nodes : [node])}
              onSelect={() => onSelect?.(node.id)}
              onAction={onAction ? () => onAction(node.id) : undefined}
            />
            {expanded ? (
              <div className="ds-h-children">
                {node.loadingChildren ? (
                  <p className="ds-h-loading">Loading…</p>
                ) : node.children?.length ? (
                  <HierarchyBranch
                    nodes={node.children}
                    expandedIds={expandedIds}
                    selectedId={selectedId}
                    singleOpen={singleOpen}
                    onToggle={onToggle}
                    onSelect={onSelect}
                    onAction={onAction}
                  />
                ) : null}
              </div>
            ) : null}
          </div>
        );
      })}
    </div>
  );
}

export function HierarchyTree({
  nodes,
  expandedIds,
  selectedId,
  singleOpen,
  connected = false,
  onToggle,
  onSelect,
  onAction,
  empty,
}: {
  nodes: HierarchyNodeData[];
  expandedIds: string[];
  selectedId?: string;
  singleOpen?: boolean;
  connected?: boolean;
  onToggle: (id: string, siblings: HierarchyNodeData[]) => void;
  onSelect?: (id: string) => void;
  onAction?: (id: string) => void;
  empty?: ReactNode;
}) {
  if (!nodes.length) return <>{empty}</>;
  return (
    <div
      className={cx("ds-h-tree", connected && "ds-h-tree--connected")}
      role="tree"
    >
      <HierarchyBranch
        nodes={nodes}
        expandedIds={expandedIds}
        selectedId={selectedId}
        singleOpen={singleOpen}
        onToggle={onToggle}
        onSelect={onSelect}
        onAction={onAction}
      />
    </div>
  );
}

export function HierarchyToolbar({ children }: { children: ReactNode }) {
  return <div className="ds-h-toolbar">{children}</div>;
}
