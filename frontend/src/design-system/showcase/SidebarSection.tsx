import { useState } from "react";
import {
  Button,
  SectionCard,
  Sidebar,
  SidebarBrand,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMobileDrawer,
  SidebarMobileTrigger,
  SidebarNavigation,
  SidebarProfile,
  SidebarScrollArea,
  SidebarToggle,
  type SidebarNavGroup,
} from "../index";

const approvedGroups: SidebarNavGroup[] = [
  {
    id: "main",
    label: "Main",
    items: [
      { id: "dashboard", label: "Dashboard", icon: "dashboard" },
      {
        id: "notifications",
        label: "Notifications",
        icon: "notification",
        badge: { count: 12, tone: "danger", label: "12 unread notifications" },
      },
      { id: "tasks", label: "Tasks", icon: "tasks" },
    ],
  },
  {
    id: "sales",
    label: "Sales",
    items: [
      { id: "cases", label: "Cases", icon: "cases" },
      { id: "customers", label: "Customers", icon: "customers" },
    ],
  },
  {
    id: "administration",
    label: "Administration",
    items: [
      { id: "employees", label: "Employees", icon: "employees" },
      { id: "organization", label: "Organization", icon: "organization" },
      { id: "teams", label: "Teams", icon: "team" },
      { id: "attendance", label: "Attendance", icon: "attendance" },
      { id: "assets", label: "Assets", icon: "assets" },
      { id: "imports", label: "Imports", icon: "import" },
    ],
  },
  {
    id: "performance",
    label: "Performance",
    items: [{ id: "performance", label: "Performance", icon: "performance" }],
  },
  {
    id: "finance",
    label: "Finance",
    items: [{ id: "finance", label: "Finance", icon: "finance" }],
  },
  {
    id: "reports",
    label: "Reports",
    items: [{ id: "reports", label: "Reports", icon: "reports" }],
  },
  {
    id: "settings",
    label: "Settings",
    items: [{ id: "settings", label: "Settings", icon: "settings" }],
  },
];

const componentStateGroups: SidebarNavGroup[] = [
  {
    id: "states",
    label: "Component states",
    items: [
      { id: "default", label: "Default item", icon: "dashboard" },
      {
        id: "badge",
        label: "Badge item",
        icon: "notification",
        badge: { count: 9, label: "9 items" },
      },
      {
        id: "nested",
        label: "Nested parent",
        icon: "cases",
        children: [
          { id: "nested-a", label: "Nested child A" },
          { id: "nested-b", label: "Nested child B" },
        ],
      },
      {
        id: "long",
        label: "Long label truncation example for overflow",
        icon: "reports",
      },
      {
        id: "disabled",
        label: "Disabled item",
        icon: "locked",
        disabled: true,
        tooltip: "Not available in the current authorized scope",
      },
    ],
  },
];

const showcaseProfile = {
  name: "A. Rahman",
  designation: "Operations manager",
};

function SidebarPreview({
  collapsed,
  onCollapsedChange,
  activeId,
  onSelect,
  short,
  pageTitle,
  groups = approvedGroups,
  environment,
}: {
  collapsed: boolean;
  onCollapsedChange: (collapsed: boolean) => void;
  activeId: string;
  onSelect: (id: string) => void;
  short?: boolean;
  pageTitle: string;
  groups?: SidebarNavGroup[];
  environment?: string;
}) {
  return (
    <div
      className={
        short ? "ds-sidebar-shell ds-sidebar-shell--short" : "ds-sidebar-shell"
      }
    >
      <Sidebar collapsed={collapsed} label="AMAFH navigation preview">
        <SidebarHeader>
          <SidebarBrand environment={environment} />
          <SidebarToggle
            collapsed={collapsed}
            onClick={() => onCollapsedChange(!collapsed)}
          />
        </SidebarHeader>
        <SidebarContent>
          <SidebarScrollArea>
            <SidebarNavigation
              groups={groups}
              activeId={activeId}
              onSelect={onSelect}
            />
          </SidebarScrollArea>
        </SidebarContent>
        <SidebarFooter>
          <SidebarProfile
            name={showcaseProfile.name}
            designation={showcaseProfile.designation}
          />
        </SidebarFooter>
      </Sidebar>
      <div className="ds-sidebar-shell__page">
        <h3>{pageTitle}</h3>
        <p>
          Framed preview only. Application routes and permissions stay outside
          the design system. Profile identity is supplied by the caller.
        </p>
      </div>
    </div>
  );
}

export function SidebarSection() {
  const [expandedCollapsed, setExpandedCollapsed] = useState(false);
  const [collapsed, setCollapsed] = useState(true);
  const [activeId, setActiveId] = useState("dashboard");
  const [collapsedActive, setCollapsedActive] = useState("dashboard");
  const [stateActive, setStateActive] = useState("nested-a");
  const [mobileOpen, setMobileOpen] = useState(false);
  const [mobileActive, setMobileActive] = useState("dashboard");

  return (
    <section id="sidebar" className="ds-stack-20">
      <SectionCard
        title="Approved navigation"
        description="Showcase structure only. Audit stays inside Settings. Payroll, placeholder originations, and duplicate Administration items are not part of the approved navigation. Routes stay in the application."
      >
        <div className="ds-sidebar-examples">
          <strong>Expanded</strong>
          <SidebarPreview
            collapsed={expandedCollapsed}
            onCollapsedChange={setExpandedCollapsed}
            activeId={activeId}
            onSelect={setActiveId}
            pageTitle="Dashboard"
            environment={expandedCollapsed ? undefined : "Dev"}
          />
          <strong>Collapsed</strong>
          <SidebarPreview
            collapsed={collapsed}
            onCollapsedChange={setCollapsed}
            activeId={collapsedActive}
            onSelect={setCollapsedActive}
            pageTitle="Dashboard"
          />
          <strong>Narrow height / internal scroll</strong>
          <SidebarPreview
            collapsed={false}
            onCollapsedChange={() => undefined}
            activeId="attendance"
            onSelect={setActiveId}
            short
            pageTitle="Attendance"
          />
          <strong>Mobile drawer</strong>
          <SidebarMobileTrigger onClick={() => setMobileOpen(true)} />
          <Button variant="secondary" onClick={() => setMobileOpen(true)}>
            Open mobile navigation
          </Button>
        </div>
      </SectionCard>
      <SectionCard
        title="Component states"
        description="Long labels, disabled items, badges, nested menus, and tooltips are component demonstrations only. They are not approved production navigation."
      >
        <SidebarPreview
          collapsed={false}
          onCollapsedChange={() => undefined}
          activeId={stateActive}
          onSelect={setStateActive}
          short
          pageTitle="Component states"
          groups={componentStateGroups}
        />
      </SectionCard>
      <SidebarMobileDrawer
        open={mobileOpen}
        onClose={() => setMobileOpen(false)}
      >
        <Sidebar collapsed={false} label="Mobile navigation">
          <SidebarHeader>
            <SidebarBrand environment="Dev" />
            <SidebarToggle
              collapsed={false}
              onClick={() => setMobileOpen(false)}
            />
          </SidebarHeader>
          <SidebarContent>
            <SidebarScrollArea>
              <SidebarNavigation
                groups={approvedGroups}
                activeId={mobileActive}
                onSelect={(id) => {
                  setMobileActive(id);
                  setMobileOpen(false);
                }}
              />
            </SidebarScrollArea>
          </SidebarContent>
          <SidebarFooter>
            <SidebarProfile
              name={showcaseProfile.name}
              designation={showcaseProfile.designation}
            />
          </SidebarFooter>
        </Sidebar>
      </SidebarMobileDrawer>
    </section>
  );
}
