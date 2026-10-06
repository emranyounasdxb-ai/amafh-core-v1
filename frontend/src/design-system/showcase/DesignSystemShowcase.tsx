import { useMemo, useState, type ReactNode } from "react";
import {
  ActionToolbar,
  ActivityTimeline,
  AlertDialog,
  addMonths,
  Banner,
  Breadcrumbs,
  Button,
  ButtonGroup,
  DsIcon,
  Checkbox,
  CheckboxGroup,
  Calendar,
  Combobox,
  ConfirmationDialog,
  CurrencyInput,
  DataTable,
  DatePicker,
  DateRangePicker,
  DateTimePicker,
  DesignSystemRoot,
  DestructiveConfirmationDialog,
  DetailGrid,
  Dialog,
  Drawer,
  dsTokens,
  EmptyState,
  ErrorState,
  FeedbackStates,
  FileUpload,
  FilterButton,
  FilterCard,
  FilterToolbar,
  FormField,
  FormLayout,
  FormRow,
  FormSection,
  HierarchyPattern,
  IconButton,
  InfoField,
  InfoGrid,
  InlineNotice,
  KpiCard,
  KpiSummary,
  Menu,
  MonetaryAmount,
  MonthPicker,
  MultiSelect,
  OverflowMenu,
  PageHeader,
  Pagination,
  PasswordInput,
  PercentageInput,
  PhoneInput,
  Popover,
  RadioGroup,
  RecordCount,
  ReadOnlyField,
  RecordActions,
  RecordDetailHeader,
  RelatedRecordList,
  ResponsiveDataTable,
  SearchFilterToolbar,
  SectionCard,
  SegmentedControl,
  Select,
  SkeletonControl,
  SkeletonText,
  StatusBadge,
  SplitButton,
  StatusSummary,
  Stepper,
  StickyActionBar,
  Switch,
  Tabs,
  TextArea,
  TextInput,
  ToastProvider,
  UnsavedChangesDialog,
  YearPicker,
  formatDubaiTimestamp,
  formatDateOnly,
  useToast,
} from "../index";
import type { HierarchyNodeData } from "../index";
import { DropdownsSection } from "./DropdownsSection";
import { EnterpriseSections } from "./EnterpriseSections";
import { FiltersSection } from "./FiltersSection";
import { SidebarSection } from "./SidebarSection";
import { AttendanceSection } from "./AttendanceSection";
import { PerformanceSection } from "./PerformanceSection";
import { CompactValuesSection } from "./CompactValuesSection";
import { ProfileBannerSection } from "./ProfileBannerSection";
import { ResponsiveSection } from "./ResponsiveSection";
import "./showcase.css";

const colorEntries = Object.entries(dsTokens.color);
const spaceEntries = Object.entries(dsTokens.space);

const tableRows = [
  {
    id: "REC-2401",
    name: "North operations",
    owner: "A. Rahman",
    amount: 12_400,
    status: "Active",
    desk: "North operations",
    notes: "Harbour desk coverage with a long authorized title that must wrap",
  },
  {
    id: "REC-2402",
    name: "Harbour desk",
    owner: "M. Khalid",
    amount: 8_250,
    status: "Review",
    desk: "Harbour desk",
    notes: "Documents pending review",
  },
  {
    id: "REC-2403",
    name: "West intake",
    owner: "S. Noor",
    amount: 19_080,
    status: "Closed",
    desk: "West intake",
    notes: "Closed after authorized payout",
  },
];

const deskOptions = [
  { value: "north", label: "North operations" },
  { value: "harbour", label: "Harbour desk" },
  { value: "west", label: "West intake" },
];

const hierarchy: HierarchyNodeData[] = [
  {
    id: "md",
    name: "A. Al Maktoum",
    subtitle: "Managing Director",
    root: true,
    status: "Active",
    statusTone: "success",
    children: [
      {
        id: "branch-north",
        name: "North branch",
        subtitle: "Branch",
        kind: "group",
        count: 12,
        children: [
          {
            id: "mgr",
            name: "S. Rahman",
            subtitle: "Manager",
            children: [
              {
                id: "coord",
                name: "Teams",
                subtitle: "Coordinator group",
                kind: "group",
                count: 4,
                children: [
                  {
                    id: "tl",
                    name: "M. Khalid",
                    subtitle: "Team leader",
                    children: [
                      {
                        id: "m1",
                        name: "L. Noor",
                        subtitle: "Member",
                      },
                      {
                        id: "m2",
                        name: "H. Farid",
                        subtitle: "Member",
                      },
                    ],
                  },
                ],
              },
            ],
          },
        ],
      },
    ],
  },
];

function ShowcaseBody() {
  const { toast } = useToast();
  const [tab, setTab] = useState("open");
  const [sortKey, setSortKey] = useState("id");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [selected, setSelected] = useState<string[]>(["REC-2401"]);
  const [page, setPage] = useState(1);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [longDialogOpen, setLongDialogOpen] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [destroyOpen, setDestroyOpen] = useState(false);
  const [alertOpen, setAlertOpen] = useState(false);
  const [unsavedOpen, setUnsavedOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [files, setFiles] = useState<FileList | null>(null);
  const [combo, setCombo] = useState("north");
  const [multi, setMulti] = useState<string[]>(["harbour"]);
  const [singleDate, setSingleDate] = useState("2026-10-02");
  const [range, setRange] = useState({
    start: "2026-09-03",
    end: "2026-10-02",
  });
  const [month, setMonth] = useState("2026-10");
  const [year, setYear] = useState("2026");
  const [dateTime, setDateTime] = useState({
    date: "2026-10-02",
    time: "15:30",
  });
  const [phonePrefix, setPhonePrefix] = useState("+971");
  const [phone, setPhone] = useState("501234567");
  const [notify, setNotify] = useState(true);
  const [channel, setChannel] = useState("internal");
  const [checks, setChecks] = useState({ docs: true, kyc: false });
  const [segment, setSegment] = useState("open");
  const [bannerVisible, setBannerVisible] = useState(true);
  const [formBusy, setFormBusy] = useState(false);
  const [boardMonth, setBoardMonth] = useState("2026-09-01");
  const [singleMonth, setSingleMonth] = useState("2026-10-01");
  const [openedRecord, setOpenedRecord] = useState<string | null>(null);
  const [listSearch, setListSearch] = useState("");
  const [listFiltersOpen, setListFiltersOpen] = useState(true);
  const [listDesk, setListDesk] = useState("");

  const sortedRows = useMemo(() => {
    const next = [...tableRows];
    next.sort((a, b) => {
      const left = a[sortKey as keyof typeof a];
      const right = b[sortKey as keyof typeof b];
      if (sortKey === "amount") {
        return sortDir === "asc"
          ? Number(left) - Number(right)
          : Number(right) - Number(left);
      }
      return sortDir === "asc"
        ? String(left).localeCompare(String(right))
        : String(right).localeCompare(String(left));
    });
    return next;
  }, [sortDir, sortKey]);

  const recordColumns = useMemo(
    () =>
      (
        [
          { key: "id", header: "ID", sortable: true },
          { key: "name", header: "Name", sortable: true },
          { key: "owner", header: "Owner" },
          { key: "desk", header: "Desk" },
          {
            key: "amount",
            header: "Amount",
            numeric: true,
            align: "end" as const,
            sortable: true,
            render: (row: (typeof tableRows)[number]) => (
              <MonetaryAmount value={row.amount} />
            ),
          },
          {
            key: "status",
            header: "Status",
            render: (row: (typeof tableRows)[number]) => (
              <StatusBadge
                tone={
                  row.status === "Active"
                    ? "success"
                    : row.status === "Review"
                      ? "warning"
                      : "neutral"
                }
              >
                {row.status}
              </StatusBadge>
            ),
          },
          { key: "notes", header: "Notes" },
          {
            key: "actions",
            header: "Actions",
            render: (row: (typeof tableRows)[number]) => (
              <div className="ds-button-row">
                <IconButton
                  label={`View ${row.name}`}
                  variant="ghost"
                  size="compact"
                  onClick={() =>
                    toast({
                      title: "View action",
                      description: `${row.name} opened from the row action.`,
                    })
                  }
                >
                  <DsIcon name="view" size={16} />
                </IconButton>
                <IconButton
                  label={`Edit ${row.name}`}
                  variant="ghost"
                  size="compact"
                  disabled={row.status === "Closed"}
                >
                  <DsIcon name="edit" size={16} />
                </IconButton>
                <OverflowMenu
                  label={`More actions for ${row.name}`}
                  items={[
                    {
                      id: "export-row",
                      label: "Export row",
                      onSelect: () =>
                        toast({
                          title: "Exported row",
                          description: row.name,
                        }),
                    },
                  ]}
                />
              </div>
            ),
          },
        ] as Array<{
          key: string;
          header: string;
          numeric?: boolean;
          align?: "end";
          sortable?: boolean;
          render?: (row: (typeof tableRows)[number]) => ReactNode;
        }>
      ),
    [toast],
  );

  const toggleRow = (key: string) =>
    setSelected((current) =>
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key],
    );
  const toggleAll = () =>
    setSelected((current) =>
      current.length === tableRows.length ? [] : tableRows.map((row) => row.id),
    );
  const handleSort = (key: string) => {
    if (key === sortKey)
      setSortDir((current) => (current === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir("asc");
    }
  };
  const activateShowcaseRow = (row: (typeof tableRows)[number]) => {
    setOpenedRecord(row.name);
    toast({
      title: "Opened record",
      description: row.name,
    });
  };

  return (
    <DesignSystemRoot className="ds-showcase">
      <header className="ds-showcase__top">
        <div className="ds-showcase__identity">
          <img
            className="ds-showcase__brand"
            src="/production/amafh-core-full-logo-exact.svg"
            alt="AMAFH Core"
          />
          <nav className="ds-showcase__nav" aria-label="Showcase sections">
            <a href="#foundations">Foundations</a>
            <a href="#actions">Buttons and icons</a>
            <a href="#forms">Forms</a>
            <a href="#dropdowns">Dropdowns</a>
            <a href="#filters">Search and filters</a>
            <a href="#calendars">Calendars and date ranges</a>
            <a href="#attendance">Attendance</a>
            <a href="#performance">Performance</a>
            <a href="#charts">Charts</a>
            <a href="#stages-horizontal">Stages</a>
            <a href="#data-list">Data-list density</a>
            <a href="#tables">Tables and pagination</a>
            <a href="#overlays">Dialogs, drawers, and popovers</a>
            <a href="#banners">Banners and feedback</a>
            <a href="#profile-banner">Profile banners</a>
            <a href="#activity">Activity and audit history</a>
            <a href="#export">Export and import</a>
            <a href="#hierarchy">Hierarchy and organization</a>
            <a href="#sidebar">Sidebar</a>
            <a href="#responsive">Responsive examples</a>
            <a href="#coverage">Component coverage</a>
          </nav>
        </div>
        <ActionToolbar
          overflowItems={[
            {
              id: "toast",
              label: "Show toast",
              onSelect: () =>
                toast({
                  title: "Saved",
                  description: "Display-only confirmation.",
                  tone: "success",
                }),
            },
            {
              id: "alert",
              label: "Alert dialog",
              onSelect: () => setAlertOpen(true),
            },
          ]}
        >
          <Button variant="secondary" onClick={() => setDrawerOpen(true)}>
            Open drawer
          </Button>
          <Button onClick={() => setDialogOpen(true)}>Open dialog</Button>
        </ActionToolbar>
      </header>

      <main className="ds-showcase__main">
        <PageHeader
          title="AMAFH Design System v1 — Locked"
          subtitle="Canonical compact enterprise system. Development-only application preview. Synthetic display content only."
          status="v1 locked"
          statusTone="brand"
        />

        {bannerVisible ? (
          <Banner
            tone="announcement"
            level="global"
            title="Dismissible announcement"
            onDismiss={() => setBannerVisible(false)}
            actions={
              <Button size="compact" variant="secondary">
                Review
              </Button>
            }
          >
            Pink is reserved for highlights. Primary actions stay violet.
          </Banner>
        ) : null}

        <section id="foundations" className="ds-stack-20">
          <SectionCard
            title="Typography"
            description="Manrope hierarchy for titles, sections, body, labels, and numeric data."
          >
            <div className="ds-type-grid">
              <div>
                <p className="ds-page-title__heading">Page title 24/30</p>
                <p className="ds-page-title__subtitle">
                  Page description 12/16, readable muted contrast
                </p>
              </div>
              <div>
                <h2 className="ds-section-header__title">
                  Section title 16/22
                </h2>
                <p>Form body 14/20 · Toolbar 13/18</p>
                <p className="ds-field__label">Label 12/16</p>
                <p className="ds-field__hint">Supporting text 12/16</p>
              </div>
              <div>
                <p className="ds-numeric ds-numeric--lg">12,400</p>
                <p className="ds-numeric ds-numeric--md">
                  <MonetaryAmount value={1_250} />
                </p>
                <p className="ds-field__hint">
                  Date-only {formatDateOnly("2026-10-02")} · Dubai{" "}
                  {formatDubaiTimestamp("2026-10-02T13:40:00.000Z")}
                </p>
              </div>
            </div>
          </SectionCard>
          <SectionCard
            id="color"
            title="Color and surfaces"
            description="AMAFH violet for actions and selection. Pink and magenta are limited highlights."
          >
            <div className="ds-swatch-grid">
              {colorEntries.map(([name, value]) => (
                <div key={name} className="ds-swatch">
                  <div
                    className="ds-swatch__chip"
                    style={{ background: value }}
                  />
                  <strong>{name}</strong>
                  <p className="ds-field__hint">{value}</p>
                </div>
              ))}
            </div>
          </SectionCard>
          <SectionCard
            title="Spacing scale"
            description="4 / 8 / 12 / 16 / 20 / 24 / 32. Data pages 16, compact cards 12, sections 12."
          >
            <div className="ds-space-grid">
              {spaceEntries.map(([name, value]) => (
                <div key={name} className="ds-space-item">
                  <div
                    className="ds-space-item__bar"
                    style={{ width: value }}
                  />
                  <span>
                    {name} · {value}
                  </span>
                </div>
              ))}
            </div>
          </SectionCard>
        </section>

        <section id="actions" className="ds-stack-20">
          <SectionCard
            title="Buttons and button groups"
            description="Standard 36px, compact 32px, large 40px. Adjacent actions use an 8px gap."
          >
            <div className="ds-button-row">
              <span className="ds-button-row__label">Standard</span>
              <Button>
                <DsIcon name="add" size={18} />
                Primary
              </Button>
              <Button variant="secondary">Secondary</Button>
              <Button variant="subtle">Subtle</Button>
              <Button variant="ghost">Ghost</Button>
              <Button variant="danger">
                <DsIcon name="delete" size={18} />
                Danger
              </Button>
              <Button variant="success">
                <DsIcon name="success" size={18} />
                Success
              </Button>
            </div>
            <div className="ds-button-row">
              <span className="ds-button-row__label">Compact</span>
              <Button size="compact">
                <DsIcon name="add" size={16} />
                Compact
              </Button>
              <Button size="compact" variant="secondary">
                Secondary
              </Button>
              <Button size="compact" variant="ghost">
                Dismiss
              </Button>
            </div>
            <div className="ds-button-row">
              <span className="ds-button-row__label">Large</span>
              <Button size="large">Sign in</Button>
              <Button size="large" variant="secondary">
                Back
              </Button>
            </div>
            <div className="ds-button-row">
              <span className="ds-button-row__label">Icon-only</span>
              <IconButton label="Add">
                <DsIcon name="add" size={18} />
              </IconButton>
              <IconButton label="Filter" variant="ghost">
                <DsIcon name="filter" size={16} />
              </IconButton>
              <IconButton label="Delete" variant="danger" size="compact">
                <DsIcon name="delete" size={16} />
              </IconButton>
              <IconButton label="Approve" variant="success" size="compact">
                <DsIcon name="success" size={16} />
              </IconButton>
            </div>
            <div className="ds-button-row">
              <span className="ds-button-row__label">States</span>
              <Button disabled>Disabled</Button>
              <Button loading>Saving</Button>
              <Button variant="secondary" loading>
                Preparing
              </Button>
            </div>
            <div className="ds-button-row">
              <span className="ds-button-row__label">Split / menu</span>
              <SplitButton
                label="Create"
                onClick={() => undefined}
                items={[
                  { id: "record", label: "Record" },
                  { id: "export", label: "Export" },
                ]}
              />
              <Menu
                label="Record actions"
                trigger={<Button variant="secondary">Menu</Button>}
                items={[
                  { id: "open", label: "Open record" },
                  { id: "export", label: "Export" },
                  { id: "remove", label: "Remove", danger: true },
                ]}
              />
              <ButtonGroup>
                <Button variant="secondary">Previous</Button>
                <Button variant="secondary">Next</Button>
              </ButtonGroup>
            </div>
            <div className="ds-button-row">
              <span className="ds-button-row__label">Form / dialog</span>
              <Button variant="ghost">Cancel</Button>
              <Button
                loading={formBusy}
                onClick={() => {
                  setFormBusy(true);
                  window.setTimeout(() => setFormBusy(false), 800);
                }}
              >
                Save
              </Button>
            </div>
          </SectionCard>
        </section>
        <EnterpriseSections />
        <SidebarSection />
        <AttendanceSection />
        <PerformanceSection />
        <CompactValuesSection />
        <ProfileBannerSection />

        <section id="forms" className="ds-stack-20">
          <FormSection
            title="Form controls"
            description="Row-aligned labels and controls. Help text stays in a reserved support row."
            columns={2}
            actions={
              <>
                <Button variant="ghost">Cancel</Button>
                <Button
                  loading={formBusy}
                  onClick={() => {
                    setFormBusy(true);
                    window.setTimeout(() => setFormBusy(false), 800);
                  }}
                >
                  Save
                </Button>
              </>
            }
          >
            <FormField
              label="Record name"
              htmlFor="ds-name"
              required
              hint="Visible to authorized viewers."
            >
              <TextInput id="ds-name" defaultValue="Harbour desk" />
            </FormField>
            <FormField label="Amount" htmlFor="ds-amount">
              <CurrencyInput id="ds-amount" defaultValue="12400" />
            </FormField>
            <FormField label="Share" htmlFor="ds-share">
              <PercentageInput id="ds-share" defaultValue="12.5" />
            </FormField>
            <FormField label="Password" htmlFor="ds-password">
              <PasswordInput id="ds-password" defaultValue="hidden-value" />
            </FormField>
            <FormField
              label="Phone"
              htmlFor="ds-phone"
              hint="Include the country calling code."
            >
              <PhoneInput
                id="ds-phone"
                prefix={phonePrefix}
                onPrefixChange={setPhonePrefix}
                prefixOptions={[
                  { value: "+971", label: "+971" },
                  { value: "+966", label: "+966" },
                  { value: "+44", label: "+44" },
                ]}
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
              />
            </FormField>
            <FormField label="Desk" htmlFor="ds-combo">
              <Combobox
                id="ds-combo"
                label="Desk"
                options={deskOptions}
                value={combo}
                onChange={setCombo}
              />
            </FormField>
            <FormField label="Watchers" htmlFor="ds-multi">
              <MultiSelect
                id="ds-multi"
                label="Watchers"
                options={deskOptions}
                value={multi}
                onChange={setMulti}
              />
            </FormField>
            <ReadOnlyField
              label="Record ID"
              value="REC-2401"
              hint="Assigned by the system."
            />
            <FormField
              label="Reference"
              htmlFor="ds-ref"
              error="Enter a valid reference."
            >
              <TextInput id="ds-ref" invalid defaultValue="REC-" />
            </FormField>
            <FormField label="Disabled" htmlFor="ds-disabled">
              <TextInput id="ds-disabled" disabled value="Locked" />
            </FormField>
            <FormField label="Notes" htmlFor="ds-notes">
              <TextArea
                id="ds-notes"
                rows={3}
                defaultValue="Display-only note."
              />
            </FormField>
            <FileUpload
              id="ds-file"
              label="Evidence file"
              files={files}
              onChange={setFiles}
            />
            <CheckboxGroup legend="Checks">
              <Checkbox
                label="Documents complete"
                checked={checks.docs}
                onChange={(event) =>
                  setChecks((current) => ({
                    ...current,
                    docs: event.target.checked,
                  }))
                }
              />
              <Checkbox
                label="Identity verified"
                checked={checks.kyc}
                onChange={(event) =>
                  setChecks((current) => ({
                    ...current,
                    kyc: event.target.checked,
                  }))
                }
              />
            </CheckboxGroup>
            <RadioGroup
              legend="Channel"
              name="channel"
              value={channel}
              onChange={setChannel}
              options={[
                { value: "internal", label: "Internal" },
                { value: "partner", label: "Partner" },
              ]}
            />
            <FormField label="Notifications" htmlFor="ds-notify" span>
              <Switch
                id="ds-notify"
                label="Notify owner"
                checked={notify}
                onChange={setNotify}
              />
            </FormField>
            <FormRow columns={3}>
              <FormField label="Owner" htmlFor="ds-owner">
                <TextInput id="ds-owner" defaultValue="A. Rahman" />
              </FormField>
              <FormField label="Status" htmlFor="ds-status">
                <Select
                  id="ds-status"
                  options={[
                    { value: "open", label: "Open" },
                    { value: "review", label: "In review" },
                  ]}
                  value="open"
                />
              </FormField>
              <FormField label="Branch" htmlFor="ds-form-branch">
                <Select
                  id="ds-form-branch"
                  options={[
                    { value: "north", label: "North" },
                    { value: "harbour", label: "Harbour" },
                  ]}
                  value="north"
                />
              </FormField>
            </FormRow>
          </FormSection>
          <SectionCard
            title="Narrow form preview"
            description="One column below 720px. Labels, controls, and support text stay stacked."
          >
            <div className="ds-viewport-frame ds-viewport-frame--narrow">
              <div className="ds-viewport-frame__inner">
                <FormLayout columns={1}>
                  <FormField label="Record name" htmlFor="ds-narrow-name">
                    <TextInput
                      id="ds-narrow-name"
                      defaultValue="Harbour desk"
                    />
                  </FormField>
                  <FormField label="Amount" htmlFor="ds-narrow-amount">
                    <CurrencyInput id="ds-narrow-amount" defaultValue="12400" />
                  </FormField>
                </FormLayout>
              </div>
            </div>
          </SectionCard>
        </section>

        <FiltersSection />

        <DropdownsSection />

        <section id="calendars" className="ds-stack-20">
          <SectionCard
            title="Calendars and date ranges"
            description="Compact month boards. Range endpoints use deep violet; in-range dates keep dark text."
          >
            <FormLayout columns={2}>
              <FormField label="Single date" htmlFor="ds-date">
                <DatePicker
                  id="ds-date"
                  value={singleDate}
                  onChange={setSingleDate}
                />
              </FormField>
              <FormField label="Date and time" htmlFor="ds-dt">
                <DateTimePicker
                  id="ds-dt"
                  value={dateTime}
                  onChange={setDateTime}
                />
              </FormField>
              <FormField label="Month" htmlFor="ds-month">
                <MonthPicker id="ds-month" value={month} onChange={setMonth} />
              </FormField>
              <FormField label="Year" htmlFor="ds-year">
                <YearPicker id="ds-year" value={year} onChange={setYear} />
              </FormField>
              <FormField label="Date range" htmlFor="ds-range" span>
                <DateRangePicker
                  id="ds-range"
                  value={range}
                  onChange={setRange}
                  disabledDates={["2026-10-04", "2026-10-05"]}
                />
              </FormField>
            </FormLayout>
            <div className="ds-calendar-examples">
              <div>
                <p className="ds-field__label">Single month</p>
                <Calendar
                  month={singleMonth}
                  onMonthChange={setSingleMonth}
                  value={singleDate}
                  disabledDates={["2026-10-04", "2026-10-05"]}
                  onSelect={(next) => {
                    setSingleDate(next);
                    setSingleMonth(next);
                  }}
                />
              </div>
              <div>
                <p className="ds-field__label">Two-month range</p>
                <div className="ds-calendar-board ds-calendar-board--range">
                  <Calendar
                    month={boardMonth}
                    onMonthChange={setBoardMonth}
                    rangeStart={range.start}
                    rangeEnd={range.end}
                    disabledDates={["2026-10-04", "2026-10-05"]}
                    onSelect={() => undefined}
                  />
                  <Calendar
                    month={addMonths(boardMonth, 1)}
                    onMonthChange={(next) => setBoardMonth(addMonths(next, -1))}
                    rangeStart={range.start}
                    rangeEnd={range.end}
                    disabledDates={["2026-10-04", "2026-10-05"]}
                    onSelect={() => undefined}
                  />
                </div>
              </div>
            </div>
            <div className="ds-viewport-frame ds-viewport-frame--narrow">
              <div className="ds-viewport-frame__inner">
                <p className="ds-field__label">Narrow single month</p>
                <Calendar
                  month={singleMonth}
                  onMonthChange={setSingleMonth}
                  value={singleDate}
                  onSelect={(next) => {
                    setSingleDate(next);
                    setSingleMonth(next);
                  }}
                />
              </div>
            </div>
          </SectionCard>
        </section>

        <section id="overlays" className="ds-stack-20">
          <SectionCard title="Dialogs, drawers, and popovers">
            <ActionToolbar>
              <Button onClick={() => setDialogOpen(true)}>Dialog</Button>
              <Button
                variant="secondary"
                onClick={() => setLongDialogOpen(true)}
              >
                Long form
              </Button>
              <Button variant="secondary" onClick={() => setConfirmOpen(true)}>
                Confirm
              </Button>
              <Button variant="danger" onClick={() => setDestroyOpen(true)}>
                Destructive
              </Button>
              <Button variant="ghost" onClick={() => setAlertOpen(true)}>
                Alert
              </Button>
              <Button variant="ghost" onClick={() => setUnsavedOpen(true)}>
                Unsaved
              </Button>
              <Button variant="ghost" onClick={() => setDrawerOpen(true)}>
                Drawer
              </Button>
              <Popover
                trigger={<Button variant="secondary">Popover</Button>}
                label="Help"
              >
                <p>Popovers stay inside the viewport and restore focus.</p>
              </Popover>
            </ActionToolbar>
          </SectionCard>
        </section>

        <section id="banners" className="ds-stack-20">
          <SectionCard title="Banners and feedback">
            <div className="ds-stack-12">
              <Banner tone="info" title="Page notice">
                Authorized records only.
              </Banner>
              <Banner tone="success" title="Success">
                The last command completed.
              </Banner>
              <Banner tone="warning" title="Warning">
                A prerequisite is still missing.
              </Banner>
              <Banner tone="error" title="Error">
                The field value is invalid.
              </Banner>
              <Banner tone="permission" title="Restricted">
                This view is outside the current authorized scope.
              </Banner>
              <Banner tone="maintenance" title="Maintenance">
                Read-only while a change window is open.
              </Banner>
              <InlineNotice tone="info" title="Inline">
                Status is labelled, not color alone.
              </InlineNotice>
            </div>
          </SectionCard>
          <section className="ds-state-grid">
            <SectionCard title="Loading">
              <FeedbackStates kind="loading" />
            </SectionCard>
            <SectionCard title="Empty">
              <FeedbackStates kind="empty" />
            </SectionCard>
            <SectionCard title="No search results">
              <FeedbackStates kind="no-results" />
            </SectionCard>
            <SectionCard title="Validation error">
              <FeedbackStates kind="validation" />
            </SectionCard>
            <SectionCard title="Server error">
              <FeedbackStates kind="error" retry={() => undefined} />
            </SectionCard>
            <SectionCard title="Permission denied">
              <FeedbackStates kind="permission" />
            </SectionCard>
            <SectionCard title="Not found">
              <FeedbackStates kind="not-found" />
            </SectionCard>
            <SectionCard title="Offline">
              <FeedbackStates kind="offline" />
            </SectionCard>
            <SectionCard title="Safe retry">
              <FeedbackStates kind="retry" retry={() => undefined} />
            </SectionCard>
            <SectionCard title="Unavailable">
              <FeedbackStates kind="unavailable" retry={() => undefined} />
            </SectionCard>
            <SectionCard title="Skeleton">
              <div className="ds-stack-8">
                <SkeletonControl />
                <SkeletonText />
              </div>
            </SectionCard>
          </section>
        </section>

        <section id="data-list" className="ds-stack-12">
          <SectionCard
            title="Approved data-list page"
            description="Mandatory compact density: title, description, 32px toolbar, optional filter card, record count, 36px table, compact badges, and 32px pagination."
          >
            <div className="ds-stack-12">
              <PageHeader
                title="Records"
                subtitle="Authorized records in the current view"
              />
              <SearchFilterToolbar
                searchId="ds-data-list-search"
                searchLabel="Search"
                searchValue={listSearch}
                onSearchChange={setListSearch}
                searchPlaceholder="Search records"
                actions={
                  <>
                    <FilterButton
                      count={listDesk ? 1 : 0}
                      aria-expanded={listFiltersOpen}
                      aria-controls="ds-data-list-filters"
                      onClick={() => setListFiltersOpen((current) => !current)}
                    />
                    <Button size="compact">Add record</Button>
                  </>
                }
              />
              {listFiltersOpen ? (
                <FilterCard id="ds-data-list-filters" label="Record filters">
                  <FormField label="Desk" htmlFor="ds-data-list-desk">
                    <Select
                      id="ds-data-list-desk"
                      compact
                      clearable
                      value={listDesk}
                      onChange={setListDesk}
                      options={deskOptions}
                      placeholder="All desks"
                    />
                  </FormField>
                </FilterCard>
              ) : null}
              <SectionCard compact>
                <RecordCount count={sortedRows.length} />
                <DataTable
                  ariaLabel="Approved compact records"
                  density="compact"
                  columns={[...recordColumns]}
                  rows={sortedRows}
                  rowKey={(row) => row.id}
                  sort={{ key: sortKey, direction: sortDir }}
                  onSort={handleSort}
                  selectedKeys={selected}
                  onToggleRow={toggleRow}
                  onToggleAll={toggleAll}
                  onRowActivate={activateShowcaseRow}
                  rowActivateLabel={(row) => `Open ${row.name}`}
                />
                <Pagination
                  page={page}
                  pageCount={3}
                  onPageChange={setPage}
                  pageSize={25}
                  onPageSizeChange={() => undefined}
                />
              </SectionCard>
            </div>
          </SectionCard>
        </section>

        <section id="tables" className="ds-stack-20">
          <SectionCard title="Badges and statuses">
            <StatusSummary
              items={[
                { label: "Active", count: 12, tone: "success" },
                { label: "Review", count: 3, tone: "warning" },
                { label: "Blocked", count: 1, tone: "danger" },
                { label: "Info", count: 4, tone: "info" },
                { label: "Neutral", count: 6, tone: "neutral" },
                { label: "Selected", count: 2, tone: "brand" },
              ]}
            />
          </SectionCard>
          <Tabs
            label="Record views"
            items={[
              { id: "open", label: "Open" },
              { id: "review", label: "Review" },
              { id: "closed", label: "Closed", disabled: true },
            ]}
            value={tab}
            onChange={setTab}
          />
          <SegmentedControl
            label="Queue"
            items={[
              { id: "open", label: "Open" },
              { id: "review", label: "Review" },
              { id: "closed", label: "Closed" },
            ]}
            value={segment}
            onChange={setSegment}
          />
          <FilterToolbar label="Action filters">
            <Button size="compact" variant="secondary">
              Export selected
            </Button>
          </FilterToolbar>
          <ResponsiveDataTable
            description="Optional onRowActivate opens an existing authorized destination. Checkboxes, icon buttons, overflow menus, and disabled actions stay independent. Rows without onRowActivate stay inert."
            ariaLabel="Wide showcase records"
            rows={sortedRows}
            rowKey={(row) => row.id}
            selectedKeys={selected}
            onToggleRow={toggleRow}
            onToggleAll={toggleAll}
            sort={{ key: sortKey, direction: sortDir }}
            onSort={handleSort}
            page={page}
            pageCount={3}
            onPageChange={setPage}
            pageSize={25}
            onPageSizeChange={() => undefined}
            columns={[...recordColumns]}
            onRowActivate={activateShowcaseRow}
            rowActivateLabel={(row) => `Open ${row.name}`}
            actions={
              <>
                {openedRecord ? (
                  <span>Last opened: {openedRecord}</span>
                ) : null}
                {selected.length ? (
                  <>
                    <Button size="compact" variant="secondary">
                      Export selected
                    </Button>
                    <Button size="compact" variant="danger">
                      Delete selected
                    </Button>
                  </>
                ) : null}
              </>
            }
          />
          <SectionCard
            title="Laptop table beside an expanded Sidebar"
            description="248px Sidebar chrome reduces the table container. The table stays tabular and may scroll internally."
          >
            <div className="ds-table-sidebar-demo">
              <div className="ds-table-sidebar-demo__nav" aria-hidden="true">
                <span>Dashboard</span>
                <span>Records</span>
                <span>Employees</span>
              </div>
              <div className="ds-table-sidebar-demo__main">
                <DataTable
                  ariaLabel="Laptop-width records"
                  rows={sortedRows}
                  rowKey={(row) => row.id}
                  selectedKeys={selected}
                  onToggleRow={toggleRow}
                  columns={[...recordColumns]}
                />
              </div>
            </div>
          </SectionCard>
          <div className="ds-content-frame ds-content-frame--768">
            <p className="ds-content-frame__caption">
              Constrained container · internal horizontal scroll while tabular.
              No onRowActivate, so rows stay non-clickable.
            </p>
            <DataTable
              ariaLabel="Constrained records"
              rows={sortedRows}
              rowKey={(row) => row.id}
              columns={[...recordColumns]}
            />
          </div>
          <div className="ds-content-frame ds-content-frame--640">
            <p className="ds-content-frame__caption">
              Narrow container · stacked records with the same optional row
              activation
            </p>
            <DataTable
              ariaLabel="Stacked records"
              rows={sortedRows}
              rowKey={(row) => row.id}
              selectedKeys={selected}
              onToggleRow={toggleRow}
              columns={[...recordColumns]}
              onRowActivate={activateShowcaseRow}
              rowActivateLabel={(row) => `Open ${row.name}`}
            />
          </div>
          <ResponsiveDataTable
            description="Compact empty presentation inside the same table system."
            ariaLabel="Empty showcase table"
            rows={[]}
            rowKey={() => ""}
            page={1}
            pageCount={1}
            onPageChange={() => undefined}
            columns={[...recordColumns]}
            empty={
              <EmptyState
                title="No matching rows"
                description="Adjust filters to see authorized records."
              />
            }
          />
          <SectionCard title="Loading table">
            <DataTable
              ariaLabel="Loading records"
              rows={[]}
              rowKey={() => ""}
              columns={[...recordColumns]}
              loading
            />
          </SectionCard>
          <SectionCard title="Error table">
            <DataTable
              ariaLabel="Unavailable records"
              rows={[]}
              rowKey={() => ""}
              columns={[...recordColumns]}
              error={
                <ErrorState
                  description="The last request failed. Retained results were not replaced."
                  retry={() => undefined}
                />
              }
            />
          </SectionCard>
          <Pagination page={2} pageCount={4} onPageChange={() => undefined} />
        </section>

        <section id="records" className="ds-stack-20">
          <Breadcrumbs
            items={[
              { id: "cases", label: "Records", onClick: () => undefined },
              { id: "rec", label: "REC-2401" },
            ]}
          />
          <RecordDetailHeader
            title="Record REC-2401"
            subtitle="Authorized detail header with actions."
            status="Active"
            statusTone="success"
            onBack={() => undefined}
            actions={
              <RecordActions>
                <Button variant="secondary">Secondary</Button>
                <Button>Primary action</Button>
              </RecordActions>
            }
          />
          <Stepper
            label="Process"
            items={[
              { id: "intake", label: "Intake", status: "complete" },
              { id: "review", label: "Review", status: "current" },
              { id: "close", label: "Close", status: "upcoming" },
            ]}
          />
          <KpiSummary
            compact
            items={[
              {
                id: "open",
                label: "Open items",
                value: 24,
                meta: "This period",
              },
              {
                id: "value",
                label: "Value",
                value: <MonetaryAmount value={41_730} />,
                meta: "Authorized total",
                accent: "pink",
              },
              {
                id: "closed",
                label: "Closed",
                value: 9,
                meta: "No pending work",
              },
            ]}
          />
          <DetailGrid
            title="Label and value grid"
            items={[
              { label: "Record ID", value: "REC-2401" },
              { label: "Owner", value: "A. Rahman" },
              { label: "Amount", value: "12,400", numeric: true },
              { label: "Desk", value: "North operations" },
              { label: "Opened", value: "02 Oct 26" },
              { label: "Channel", value: "Internal" },
            ]}
          />
          <SectionCard title="Information grid">
            <strong>Wide container · three columns</strong>
            <InfoGrid>
              <InfoField label="Primary" value="Compact enterprise density" />
              <InfoField
                label="Secondary"
                value="White surfaces, 1px borders"
              />
              <InfoField
                label="Accent"
                value="Violet actions, pink highlights"
              />
              <InfoField label="Branch" value="North operations" />
              <InfoField label="Desk" value="Harbour desk" />
              <InfoField
                label="Assignment"
                value="Harbour desk coverage with a long authorized title"
              />
            </InfoGrid>
            <strong>InfoGrid container widths</strong>
            <div className="ds-content-frame ds-content-frame--1080">
              <p className="ds-content-frame__caption">
                Laptop / constrained · two columns
              </p>
              <InfoGrid>
                <InfoField label="Record ID" value="REC-2401" />
                <InfoField label="Owner" value="A. Rahman" />
                <InfoField label="Desk" value="North operations" />
                <InfoField label="Opened" value="02 Oct 26" />
                <InfoField label="Channel" value="Internal" />
                <InfoField label="Status" value="Active" />
              </InfoGrid>
            </div>
            <div className="ds-content-frame ds-content-frame--640">
              <p className="ds-content-frame__caption">Narrow · one column</p>
              <InfoGrid>
                <InfoField label="Record ID" value="REC-2401" />
                <InfoField label="Owner" value="A. Rahman" />
                <InfoField label="Desk" value="North operations" />
                <InfoField label="Opened" value="02 Oct 26" />
                <InfoField label="Channel" value="Internal" />
                <InfoField label="Status" value="Active" />
              </InfoGrid>
            </div>
          </SectionCard>
          <KpiCard label="Standalone KPI" value="98.2%" meta="Completion" />
          <div id="activity" className="ds-stack-20">
          <ActivityTimeline
            title="Activity and audit history"
            description="Neutral event surfaces. Color stays on the node and status badge. Standard node icons are 16px through DsIcon."
            items={[
              {
                id: "1",
                time: "02 Oct 26 · 15:12",
                title: "Record created",
                description: "Opened from authorized intake.",
                actor: "System",
                tone: "info",
                status: "Recorded",
                icon: <DsIcon name="created" size={16} />,
              },
              {
                id: "2",
                time: "02 Oct 26 · 15:16",
                title: "Assignment changed",
                description: "Owner set to A. Rahman.",
                actor: "M. Khalid",
                tone: "brand",
                status: "Assigned",
                icon: <DsIcon name="user" size={16} />,
              },
              {
                id: "3",
                time: "02 Oct 26 · 15:18",
                title: "Status changed",
                description: "Moved to review. Retained history is unchanged.",
                actor: "A. Rahman",
                tone: "warning",
                status: "In review",
                icon: <DsIcon name="refresh" size={16} />,
              },
              {
                id: "4",
                time: "02 Oct 26 · 16:02",
                title: "Approval",
                description: "Documents confirmed for the current stage.",
                actor: "North operations",
                tone: "success",
                status: "Approved",
                icon: <DsIcon name="completed" size={16} />,
              },
              {
                id: "5",
                time: "02 Oct 26 · 16:40",
                title: "Rejection",
                description: "Missing identity document returned to intake.",
                actor: "Harbour desk",
                tone: "danger",
                status: "Returned",
                icon: <DsIcon name="close" size={16} />,
              },
              {
                id: "6",
                time: "02 Oct 26 · 17:05",
                title: "System audit event",
                description: "Export requested for authorized viewers.",
                actor: "System",
                tone: "neutral",
                status: "Logged",
                icon: <DsIcon name="settings" size={16} />,
              },
            ]}
          />
          <ActivityTimeline
            compact
            title="Compact activity"
            items={[
              {
                id: "c1",
                time: "02 Oct 26 · 15:12",
                title: "Record created",
                actor: "System",
                tone: "info",
                icon: <DsIcon name="created" size={14} />,
              },
              {
                id: "c2",
                time: "02 Oct 26 · 16:02",
                title: "Approval",
                actor: "North operations",
                tone: "success",
                status: "Approved",
                icon: <DsIcon name="completed" size={14} />,
              },
            ]}
          />
          </div>
          <RelatedRecordList
            title="Related records"
            items={[
              {
                id: "REL-1",
                title: "Linked record REL-118",
                meta: "Opened 01 Oct 26",
                status: "Open",
                statusTone: "brand",
              },
              {
                id: "REL-2",
                title: "Linked record REL-204",
                meta: "Closed 28 Sep 2026",
                status: "Closed",
                statusTone: "neutral",
              },
            ]}
          />
          <StickyActionBar>
            <Button variant="ghost">Cancel</Button>
            <Button>Save record</Button>
          </StickyActionBar>
        </section>

        <section id="hierarchy">
          <HierarchyPattern nodes={hierarchy} />
        </section>

        <ResponsiveSection />
      </main>

      <Dialog
        open={dialogOpen}
        title="Record action"
        onClose={() => setDialogOpen(false)}
        footer={<Button onClick={() => setDialogOpen(false)}>Done</Button>}
      >
        <p>
          Dialogs keep a close control in the header and left-aligned footer
          actions.
        </p>
      </Dialog>
      <Dialog
        open={longDialogOpen}
        title="Update record"
        size="lg"
        busy={formBusy}
        onClose={() => setLongDialogOpen(false)}
        footer={
          <>
            <Button
              variant="secondary"
              disabled={formBusy}
              onClick={() => setLongDialogOpen(false)}
            >
              Cancel
            </Button>
            <Button
              loading={formBusy}
              onClick={() => {
                setFormBusy(true);
                window.setTimeout(() => {
                  setFormBusy(false);
                  setLongDialogOpen(false);
                }, 700);
              }}
            >
              Submit
            </Button>
          </>
        }
      >
        <FormLayout columns={1}>
          {["Owner", "Desk", "Reference", "Notes", "Follow-up"].map((label) => (
            <FormField key={label} label={label} htmlFor={`long-${label}`}>
              <TextInput id={`long-${label}`} defaultValue={label} />
            </FormField>
          ))}
        </FormLayout>
      </Dialog>
      <ConfirmationDialog
        open={confirmOpen}
        title="Confirm action"
        confirmLabel="Confirm"
        onClose={() => setConfirmOpen(false)}
        onConfirm={() => setConfirmOpen(false)}
      >
        <p>This confirmation does not submit application data.</p>
      </ConfirmationDialog>
      <DestructiveConfirmationDialog
        open={destroyOpen}
        title="Remove record"
        onClose={() => setDestroyOpen(false)}
        onConfirm={() => setDestroyOpen(false)}
      >
        <p>This destructive confirmation is display-only.</p>
      </DestructiveConfirmationDialog>
      <AlertDialog
        open={alertOpen}
        title="Action required"
        onClose={() => setAlertOpen(false)}
        footer={<Button onClick={() => setAlertOpen(false)}>Understood</Button>}
      >
        <p>Alert dialogs do not close on outside click.</p>
      </AlertDialog>
      <UnsavedChangesDialog
        open={unsavedOpen}
        onStay={() => setUnsavedOpen(false)}
        onLeave={() => setUnsavedOpen(false)}
      />
      <Drawer
        open={drawerOpen}
        title="Record panel"
        onClose={() => setDrawerOpen(false)}
        footer={<Button onClick={() => setDrawerOpen(false)}>Close</Button>}
      >
        <p>
          Drawers present secondary detail without changing the current page.
        </p>
      </Drawer>
    </DesignSystemRoot>
  );
}

export function DesignSystemShowcase() {
  return (
    <ToastProvider>
      <ShowcaseBody />
    </ToastProvider>
  );
}
