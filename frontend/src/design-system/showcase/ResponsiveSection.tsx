import { useState, type ReactNode } from "react";
import {
  AttendanceCalendar,
  AttendanceSummary,
  BarChart,
  Button,
  ChartCard,
  ExportButton,
  FormField,
  FormLayout,
  HorizontalStageTracker,
  ImportButton,
  KpiSummary,
  ProfileBannerActions,
  ProfileBannerIdentity,
  ProfileBannerPrimaryAction,
  ProfileBannerSecondaryAction,
  ProfileCoverBanner,
  SearchFilterToolbar,
  SectionCard,
  Select,
  Sidebar,
  SidebarBrand,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarNavigation,
  SidebarProfile,
  SidebarScrollArea,
  SidebarToggle,
  TableToolbar,
  TextInput,
  type AttendanceDayRecord,
  type DateOnly,
} from "../index";

const deskOptions = [
  { value: "all", label: "All desks" },
  { value: "north-harbour", label: "North operations — Harbour desk" },
];

const sortOptions = [
  { value: "recent", label: "Recent" },
  { value: "name", label: "Name" },
];

const records: AttendanceDayRecord[] = [
  {
    date: "2026-10-01",
    status: "present",
    checkIn: "08:04",
    checkOut: "17:12",
    worked: "8h 08m",
  },
  {
    date: "2026-10-02",
    status: "late",
    checkIn: "08:46",
    checkOut: "17:21",
    worked: "7h 35m",
    late: "16m",
  },
];

function Frame({
  width,
  caption,
  children,
}: {
  width: 1080 | 960 | 768 | 640;
  caption: string;
  children: ReactNode;
}) {
  return (
    <div className={`ds-content-frame ds-content-frame--${width}`}>
      <p className="ds-content-frame__caption">{caption}</p>
      {children}
    </div>
  );
}

function DemoToolbar({ idPrefix }: { idPrefix: string }) {
  const [search, setSearch] = useState("");
  const [desk, setDesk] = useState("north-harbour");
  const [sort, setSort] = useState("recent");
  const applied = [
    {
      id: "desk",
      field: "Desk",
      value: "North operations — Harbour desk",
      label: "Desk: North operations — Harbour desk",
      onRemove: () => setDesk("all"),
    },
  ];
  return (
    <SearchFilterToolbar
      searchId={`${idPrefix}-search`}
      searchLabel="Search"
      searchPlaceholder="Search records"
      searchValue={search}
      onSearchChange={setSearch}
      filters={[
        {
          id: `${idPrefix}-desk`,
          label: "Desk",
          value: desk,
          onChange: setDesk,
          options: deskOptions,
        },
      ]}
      sortId={`${idPrefix}-sort`}
      sortValue={sort}
      sortOptions={sortOptions}
      onSortChange={setSort}
      applied={applied}
      onClearFilters={() => setDesk("all")}
      onResetFilters={() => setDesk("all")}
      filterPanel={
        <FormField label="Owner" htmlFor={`${idPrefix}-owner`}>
          <Select
            id={`${idPrefix}-owner`}
            compact
            label="Owner"
            value="all"
            options={[{ value: "all", label: "All owners" }]}
            onChange={() => undefined}
          />
        </FormField>
      }
    />
  );
}

function LaptopKit({ idPrefix }: { idPrefix: string }) {
  const [month, setMonth] = useState<DateOnly>("2026-10-01");
  const [selected, setSelected] = useState<DateOnly>("2026-10-02");
  return (
    <div className="ds-stack-16">
      <DemoToolbar idPrefix={idPrefix} />
      <FormLayout columns={2}>
        <FormField label="Owner" htmlFor={`${idPrefix}-form-owner`}>
          <TextInput id={`${idPrefix}-form-owner`} defaultValue="A. Rahman" />
        </FormField>
        <FormField label="Desk" htmlFor={`${idPrefix}-form-desk`}>
          <TextInput
            id={`${idPrefix}-form-desk`}
            defaultValue="North operations — Harbour desk"
          />
        </FormField>
      </FormLayout>
      <ProfileCoverBanner
        identity={
          <ProfileBannerIdentity
            name="A. Rahman"
            designation="Operations manager"
            code="EMP-1182"
            status="Active"
            contextLabel="Employee profile"
            onEditAvatar={() => undefined}
          />
        }
        actions={
          <ProfileBannerActions
            onBack={() => undefined}
            primary={
              <ProfileBannerPrimaryAction>
                View profile
              </ProfileBannerPrimaryAction>
            }
            secondary={
              <ProfileBannerSecondaryAction>Message</ProfileBannerSecondaryAction>
            }
            overflow={[
              { id: "assign", label: "Assign" },
              { id: "disable", label: "Deactivate", danger: true },
            ]}
          />
        }
      />
      <AttendanceSummary
        present={18}
        late={3}
        absent={1}
        leave={1}
        off={4}
        holidays={1}
        percentage={94}
        overtimeHours="4h 12m"
      />
      <AttendanceCalendar
        month={month}
        onMonthChange={setMonth}
        records={records}
        selected={selected}
        onSelect={setSelected}
        today="2026-10-02"
      />
      <KpiSummary
        items={[
          { id: "a", label: "Open items", value: 24 },
          { id: "b", label: "Review", value: 8 },
          { id: "c", label: "Closed", value: 3 },
        ]}
      />
      <ChartCard
        title="Monthly performance"
        legend={[
          { id: "actual", label: "Actual", color: "var(--ds-chart-1)" },
        ]}
        actions={
          <Button size="compact" variant="ghost">
            Scope
          </Button>
        }
      >
        <BarChart
          labels={["Jun", "Jul", "Aug"]}
          series={[{ id: "actual", label: "Actual", values: [12, 18, 9] }]}
        />
      </ChartCard>
      <HorizontalStageTracker
        label="Case pipeline"
        items={[
          { id: "intake", title: "Intake", status: "completed" },
          { id: "review", title: "Review", status: "current" },
          { id: "close", title: "Close", status: "upcoming" },
        ]}
      />
      <TableToolbar title="Records">
        <Button size="compact" variant="secondary">
          Columns
        </Button>
        <Button size="compact">Export</Button>
      </TableToolbar>
      <div className="ds-button-row">
        <ExportButton size="compact" onClick={() => undefined} />
        <ImportButton onClick={() => undefined} />
      </div>
    </div>
  );
}

export function ResponsiveSection() {
  const [collapsed, setCollapsed] = useState(false);
  return (
    <section id="responsive" className="ds-stack-20">
      <SectionCard
        title="Laptop and container widths"
        description="Layouts respond to available container width, not only the browser viewport. An expanded Sidebar of 248px leaves about 960–1100px of page content on a 1280–1366 laptop."
      >
        <Frame
          width={1080}
          caption="1366 × 768 with expanded Sidebar · ~1080px content width"
        >
          <LaptopKit idPrefix="ds-w1080" />
        </Frame>
        <Frame
          width={960}
          caption="Approximately 960px available page-content width"
        >
          <LaptopKit idPrefix="ds-w960" />
        </Frame>
        <Frame
          width={768}
          caption="Approximately 768px available component width"
        >
          <LaptopKit idPrefix="ds-w768" />
        </Frame>
        <Frame width={640} caption="Narrow / mobile component width">
          <LaptopKit idPrefix="ds-w640" />
        </Frame>
      </SectionCard>
      <SectionCard
        title="Sidebar plus page content"
        description="The expanded Sidebar reduces usable content width without changing the browser breakpoint. Components inside the page column must wrap instead of overlapping."
      >
        <div className="ds-sidebar-shell">
          <Sidebar collapsed={collapsed} label="Laptop shell preview">
            <SidebarHeader>
              <SidebarBrand environment={collapsed ? undefined : "Dev"} />
              <SidebarToggle
                collapsed={collapsed}
                onClick={() => setCollapsed(!collapsed)}
              />
            </SidebarHeader>
            <SidebarContent>
              <SidebarScrollArea>
                <SidebarNavigation
                  groups={[
                    {
                      id: "main",
                      label: "Main",
                      items: [
                        {
                          id: "dashboard",
                          label: "Dashboard",
                          icon: "dashboard",
                        },
                      ],
                    },
                    {
                      id: "admin",
                      label: "Administration",
                      items: [
                        {
                          id: "attendance",
                          label: "Attendance",
                          icon: "attendance",
                        },
                      ],
                    },
                  ]}
                  activeId="attendance"
                  onSelect={() => undefined}
                />
              </SidebarScrollArea>
            </SidebarContent>
            <SidebarFooter>
              <SidebarProfile
                name="A. Rahman"
                designation="Operations manager"
              />
            </SidebarFooter>
          </Sidebar>
          <div className="ds-sidebar-shell__page">
            <DemoToolbar idPrefix="ds-shell" />
          </div>
        </div>
      </SectionCard>
    </section>
  );
}
