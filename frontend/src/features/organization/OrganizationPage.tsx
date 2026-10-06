import { useLayoutEffect, useMemo, useRef, useState } from "react";
import {
  EmptyState,
  ErrorState,
  HierarchyTree,
  KpiSummary,
  LoadingState,
  OfflineState,
  PageContainer,
  PageHeader,
  PermissionDeniedState,
  SectionCard,
  type HierarchyNodeData,
} from "../../design-system";
import type { AuthenticatedSession } from "../../app/api/contracts";
import { useResource } from "../../app/api/useResource";
import { useSession } from "../../app/session/useSession";
import {
  activeContextId,
  collapsed,
  expandedIds,
  hierarchyEmployeeId,
  organizationHierarchy,
  toggleExpansion,
  type Expansion,
} from "./organizationHierarchy";
import {
  readOrganizationChart,
  type OrganizationChart,
} from "./organizationRead";
import { organizationCounts } from "./organizationTree";
import styles from "./OrganizationPage.module.css";

// Preserve a Performance round trip only for the same in-memory session.
// A page refresh or a new sign-in always starts with a folded chart.
const performanceReturn = new WeakMap<AuthenticatedSession, Expansion>();

function isOrganizationReturnEntry() {
  const state = window.history.state;
  return (
    Boolean(state) &&
    typeof state === "object" &&
    (state as { organizationReturn?: unknown }).organizationReturn === true
  );
}

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function indexNodes(
  nodes: HierarchyNodeData[],
  index = new Map<string, HierarchyNodeData>(),
) {
  for (const node of nodes) {
    index.set(node.id, node);
    if (node.children) indexNodes(node.children, index);
  }
  return index;
}

export function OrganizationPage({
  openPerformance,
}: {
  openPerformance: (id: string) => void;
}) {
  const { session } = useSession();
  const resource = useResource<OrganizationChart>(
    "/organization/hierarchy",
    0,
    readOrganizationChart,
    "organization-chart",
  );
  const [expansion, setExpansion] = useState<Expansion>(() =>
    session && isOrganizationReturnEntry()
      ? performanceReturn.get(session) || collapsed
      : collapsed,
  );
  const viewport = useRef<HTMLDivElement>(null);
  const chart = resource.data;
  const nodes = useMemo(
    () => (chart ? organizationHierarchy(chart.employees, chart) : []),
    [chart],
  );
  const index = useMemo(() => indexNodes(nodes), [nodes]);
  const activeContext = activeContextId(expansion);

  useLayoutEffect(() => {
    const element = viewport.current;
    if (!element || !activeContext) return;
    const frame = window.requestAnimationFrame(() => {
      const target = element.querySelector<HTMLElement>(
        `[data-hierarchy-id="${CSS.escape(activeContext)}"]`,
      );
      if (!target) return;
      const bounds = element.getBoundingClientRect();
      const targetBounds = target.getBoundingClientRect();
      element.scrollLeft +=
        targetBounds.left +
        targetBounds.width / 2 -
        (bounds.left + bounds.width / 2);
    });
    return () => window.cancelAnimationFrame(frame);
  }, [activeContext, nodes]);

  const viewPerformance = (employeeId: string) => {
    if (session) {
      performanceReturn.set(session, expansion);
      const currentState = window.history.state;
      window.history.replaceState(
        {
          ...(currentState && typeof currentState === "object"
            ? currentState
            : {}),
          organizationReturn: true,
        },
        "",
        window.location.href,
      );
    }
    openPerformance(employeeId);
  };
  const toggle = (id: string) =>
    setExpansion((current) => toggleExpansion(current, id));
  const select = (id: string) => {
    const node = index.get(id);
    const employeeId = hierarchyEmployeeId(id);
    if (node?.children?.length || !employeeId) toggle(id);
    else viewPerformance(employeeId);
  };
  const action = (id: string) => {
    const employeeId = hierarchyEmployeeId(id);
    if (employeeId) viewPerformance(employeeId);
  };

  if (!session) return null;

  return (
    <PageContainer>
      <div className={styles.page}>
        <PageHeader
          title="Organization"
          subtitle="Current reporting relationships and Team assignments"
        />
        {resource.denied ? (
          <PermissionDeniedState />
        ) : resource.error && !chart ? (
          isOffline(resource.error) ? (
            <OfflineState />
          ) : (
            <ErrorState description={resource.error} retry={resource.reload} />
          )
        ) : resource.loading && !chart ? (
          <LoadingState title="Loading Organization" />
        ) : chart ? (
          <>
            <KpiSummary
              compact
              items={organizationCounts(chart.employees).map((item) => ({
                id: item.label,
                label:
                  item.label === "Managers" ? "Sales Managers" : item.label,
                value: item.count,
                accent: "none",
              }))}
            />
            <SectionCard
              compact
              title="Reporting structure"
              description="Open a Branch, then a Sales Manager, Teams, and a Team Leader. Select an employee to open Performance."
            >
              <div
                ref={viewport}
                className={styles.viewport}
                role="region"
                aria-label="Organization overview"
                tabIndex={0}
              >
                <HierarchyTree
                  connected
                  nodes={nodes}
                  expandedIds={expandedIds(nodes, expansion)}
                  onToggle={toggle}
                  onSelect={select}
                  onAction={action}
                  empty={
                    <EmptyState
                      title="No active hierarchy"
                      description="No active employees are available in this hierarchy."
                    />
                  }
                />
              </div>
            </SectionCard>
          </>
        ) : null}
      </div>
    </PageContainer>
  );
}
