import { useState } from "react";
import {
  AvatarGroup,
  BarChart,
  Button,
  ChartCard,
  ChartGrid,
  DonutChart,
  DsIcon,
  ExportButton,
  ExportDialog,
  ExportResult,
  HorizontalStageTracker,
  ImportButton,
  ImportDialog,
  ImportResult,
  InlineGroup,
  LineChart,
  MonetaryAmount,
  ProfileMenu,
  ProfileSummary,
  UserIdentity,
  SectionCard,
  Sparkline,
  StackedBarChart,
  VerticalStageTracker,
  dsIconGuide,
  type ExportOptionSpec,
  type ImportPhase,
  type StageTrackerItem,
} from "../index";

const months = ["Jun", "Jul", "Aug", "Sep", "Oct"];
const caseStages: StageTrackerItem[] = [
  {
    id: "intake",
    title: "Intake",
    status: "completed",
    actor: "Harbour desk",
    time: "01 Oct 26",
  },
  {
    id: "review",
    title: "Review",
    status: "current",
    actor: "A. Rahman",
    time: "02 Oct 26",
    description: "Documents are with North operations.",
  },
  {
    id: "approval",
    title: "Approval",
    status: "upcoming",
  },
  {
    id: "payout",
    title: "Payout",
    status: "locked",
  },
  {
    id: "close",
    title: "Close",
    status: "upcoming",
  },
];

const longStages: StageTrackerItem[] = [
  ...caseStages,
  { id: "audit", title: "Audit pack", status: "upcoming" },
  { id: "archive", title: "Archive", status: "upcoming" },
  { id: "retain", title: "Retain", status: "upcoming" },
];

const historyStages: StageTrackerItem[] = [
  {
    id: "created",
    title: "Record created",
    status: "completed",
    description: "Opened from authorized intake.",
    actor: "System",
    time: "01 Oct 26 · 09:12",
  },
  {
    id: "assigned",
    title: "Assigned",
    status: "completed",
    description: "Owner set to A. Rahman.",
    actor: "M. Khalid",
    time: "01 Oct 26 · 09:40",
  },
  {
    id: "failed",
    title: "Document check",
    status: "failed",
    description: "Identity page was unreadable.",
    actor: "Harbour desk",
    time: "01 Oct 26 · 11:05",
  },
  {
    id: "rejected",
    title: "Returned",
    status: "rejected",
    description: "Sent back to intake for a replacement scan.",
    actor: "North operations",
    time: "01 Oct 26 · 11:20",
  },
  {
    id: "current",
    title: "In review",
    status: "current",
    description: "Replacement documents are with the reviewer.",
    actor: "A. Rahman",
    time: "02 Oct 26 · 15:18",
  },
];

const mixedStages: StageTrackerItem[] = [
  {
    id: "submitted",
    title: "Submitted",
    status: "completed",
    time: "01 Oct 26",
  },
  {
    id: "check",
    title: "Document check",
    status: "failed",
    time: "01 Oct 26",
  },
  { id: "returned", title: "Returned", status: "rejected" },
  { id: "hold", title: "Compliance hold", status: "blocked" },
  { id: "skip", title: "Peer review", status: "skipped" },
  { id: "lock", title: "Payout", status: "locked" },
];

const shortStages: StageTrackerItem[] = caseStages.slice(0, 3);

const lastCurrentStages: StageTrackerItem[] = [
  { id: "intake", title: "Intake", status: "completed", time: "01 Oct 26" },
  { id: "review", title: "Review", status: "completed", time: "02 Oct 26" },
  { id: "close", title: "Close", status: "current", time: "02 Oct 26" },
];

const lastFailedStages: StageTrackerItem[] = [
  { id: "intake", title: "Intake", status: "completed", time: "01 Oct 26" },
  { id: "review", title: "Review", status: "completed", time: "02 Oct 26" },
  { id: "close", title: "Close", status: "failed", time: "02 Oct 26" },
];

const lastCompletedStages: StageTrackerItem[] = [
  { id: "intake", title: "Intake", status: "completed", time: "01 Oct 26" },
  { id: "review", title: "Review", status: "completed", time: "02 Oct 26" },
  { id: "close", title: "Close", status: "completed", time: "02 Oct 26" },
];

const importPhases: ImportPhase[] = [
  "select",
  "selected",
  "validating",
  "warnings",
  "errors",
  "ready",
  "importing",
  "partial",
  "completed",
  "failed",
];

const exportOptions: ExportOptionSpec[] = [
  {
    id: "csv-filtered",
    format: "csv",
    scope: "filtered",
    label: "Export CSV",
    description: "Current filtered results",
  },
  {
    id: "pdf-filtered",
    format: "pdf",
    scope: "filtered",
    label: "Export PDF",
    description: "Printable filtered results",
  },
  {
    id: "csv-all",
    format: "csv",
    scope: "all",
    label: "Export all permitted",
    description: "All rows in the authorized scope",
  },
  {
    id: "csv-off",
    format: "csv",
    scope: "selected",
    label: "Export selected",
    description: "Requires a row selection",
    disabled: true,
  },
];

export function EnterpriseSections() {
  const [exportOpen, setExportOpen] = useState(false);
  const [exportStatus, setExportStatus] = useState<
    "idle" | "preparing" | "success" | "error"
  >("idle");
  const [importOpen, setImportOpen] = useState(false);
  const [importPhase, setImportPhase] = useState<ImportPhase>("select");
  const [fileName, setFileName] = useState<string>();

  return (
    <>
      <section id="icons" className="ds-stack-20">
        <SectionCard
          title="Icon standards"
          description="Lucide only through DsIcon. Stroke 1.75. Use 14px for metadata, 16px in compact controls, 18px in standard buttons, 20px for page actions, and 24px in feedback and empty states. charts use SVG primitives, not Lucide."
        >
          <div className="ds-icon-guide">
            {dsIconGuide.map((item) => (
              <div key={item.name} className="ds-icon-guide__item">
                <DsIcon name={item.name} size={item.size} />
                {item.meaning}
              </div>
            ))}
          </div>
        </SectionCard>
      </section>

      <section id="charts" className="ds-stack-20">
        <ChartGrid>
          <ChartCard
            title="Monthly performance"
            description="Authorized origination value."
            kpi={<MonetaryAmount value={1_240_000} />}
            comparison="+4.2% vs prior month"
            context="Jun–Oct 2026 · North operations"
            legend={[
              { id: "actual", label: "Actual", color: "var(--ds-chart-1)" },
              { id: "plan", label: "Plan", color: "var(--ds-chart-2)" },
            ]}
            actions={
              <Button size="compact" variant="ghost">
                <DsIcon name="filter" size={16} />
                Scope
              </Button>
            }
            footer="Values stay in the supplied series. Pages own calculations."
          >
            <LineChart
              labels={months}
              kind="currency"
              series={[
                {
                  id: "actual",
                  label: "Actual",
                  values: [980, 1040, 1110, 1180, 1240],
                },
                {
                  id: "plan",
                  label: "Plan",
                  values: [1000, 1050, 1100, 1160, 1220],
                },
              ]}
            />
          </ChartCard>
          <ChartCard
            title="Department comparison"
            description="Active records by desk."
            context="October 2026"
            legend={[{ id: "open", label: "Open", color: "var(--ds-chart-1)" }]}
          >
            <BarChart
              labels={[
                "North",
                "Harbour",
                "West intake with a long authorized label",
              ]}
              series={[{ id: "open", label: "Open", values: [42, 28, 16] }]}
            />
          </ChartCard>
          <ChartCard
            title="Product comparison"
            description="Grouped counts by authorized product."
            legend={[
              { id: "a", label: "Product A", color: "var(--ds-chart-1)" },
              { id: "b", label: "Product B", color: "var(--ds-chart-4)" },
            ]}
          >
            <BarChart
              grouped
              labels={months}
              series={[
                {
                  id: "a",
                  label: "Product A",
                  color: "var(--ds-chart-1)",
                  values: [12, 14, 13, 16, 15],
                },
                {
                  id: "b",
                  label: "Product B",
                  color: "var(--ds-chart-4)",
                  values: [8, 7, 9, 8, 10],
                },
              ]}
            />
          </ChartCard>
          <ChartCard
            title="Product mix"
            description="Stacked share of authorized products."
            legend={[
              { id: "a", label: "Product A", color: "var(--ds-chart-1)" },
              { id: "b", label: "Product B", color: "var(--ds-chart-4)" },
            ]}
          >
            <StackedBarChart
              labels={months}
              series={[
                {
                  id: "a",
                  label: "Product A",
                  color: "var(--ds-chart-1)",
                  values: [12, 14, 13, 16, 15],
                },
                {
                  id: "b",
                  label: "Product B",
                  color: "var(--ds-chart-4)",
                  values: [8, 7, 9, 8, 10],
                },
              ]}
            />
          </ChartCard>
          <ChartCard
            title="Status distribution"
            description="Current authorized case status."
            legend={[
              { id: "open", label: "Open", color: "var(--ds-chart-1)" },
              { id: "review", label: "Review", color: "var(--ds-chart-4)" },
              { id: "closed", label: "Closed", color: "var(--ds-chart-2)" },
            ]}
          >
            <DonutChart
              center={
                <>
                  <strong>128</strong>
                  <span>records</span>
                </>
              }
              items={[
                {
                  id: "open",
                  label: "Open",
                  value: 64,
                  color: "var(--ds-chart-1)",
                },
                {
                  id: "review",
                  label: "Review",
                  value: 40,
                  color: "var(--ds-chart-4)",
                },
                {
                  id: "closed",
                  label: "Closed",
                  value: 24,
                  color: "var(--ds-chart-2)",
                },
              ]}
            />
          </ChartCard>
          <ChartCard title="Loading chart" state="loading" />
          <ChartCard title="Empty chart" state="empty" />
          <ChartCard title="Error chart" state="error" />
          <ChartCard title="Permission denied" state="permission" />
          <ChartCard title="Unavailable chart" state="unavailable" />
          <ChartCard
            title="Compact KPI"
            description="North operations"
            kpi={
              <InlineGroup>
                <MonetaryAmount value={124_000} />
                <Sparkline
                  label="North sparkline"
                  values={[18, 21, 19, 24, 22, 28]}
                />
              </InlineGroup>
            }
            context="Last 6 weeks"
          />
        </ChartGrid>
        <div className="ds-content-frame ds-content-frame--1080">
          <p className="ds-content-frame__caption">
            Laptop ~1080px · two columns while each chart stays readable
          </p>
          <ChartGrid>
            <ChartCard title="Monthly performance">
              <LineChart
                labels={months}
                kind="currency"
                series={[
                  {
                    id: "actual",
                    label: "Actual",
                    values: [980, 1040, 1110, 1180, 1240],
                  },
                ]}
              />
            </ChartCard>
            <ChartCard title="Department comparison">
              <BarChart
                labels={["North", "Harbour", "West"]}
                series={[{ id: "open", label: "Open", values: [42, 28, 16] }]}
              />
            </ChartCard>
          </ChartGrid>
        </div>
        <div className="ds-content-frame ds-content-frame--640">
          <p className="ds-content-frame__caption">
            Constrained · one-column chart stack
          </p>
          <ChartGrid>
            <ChartCard title="Monthly performance">
              <LineChart
                labels={months}
                kind="currency"
                series={[
                  {
                    id: "actual",
                    label: "Actual",
                    values: [980, 1040, 1110, 1180, 1240],
                  },
                ]}
              />
            </ChartCard>
            <ChartCard title="Department comparison">
              <BarChart
                labels={["North", "Harbour", "West"]}
                series={[{ id: "open", label: "Open", values: [42, 28, 16] }]}
              />
            </ChartCard>
          </ChartGrid>
        </div>
        <div className="ds-viewport-frame ds-viewport-frame--narrow">
          <div className="ds-viewport-frame__inner">
            <ChartCard
              title="Narrow chart"
              context="Internal scroll if labels cannot compress."
            >
              <BarChart
                labels={["North operations", "Harbour desk", "West intake"]}
                series={[{ id: "open", label: "Open", values: [42, 28, 16] }]}
              />
            </ChartCard>
          </div>
        </div>
      </section>

      <section id="stages-horizontal" className="ds-stack-20">
        <SectionCard
          title="Horizontal stages"
          description="Case progression. Current stage uses violet. Completed connectors stay restrained."
        >
          <HorizontalStageTracker label="Case pipeline" items={caseStages} />
          <HorizontalStageTracker
            compact
            label="Compact pipeline"
            items={caseStages.slice(0, 4)}
          />
        </SectionCard>
        <SectionCard
          title="Failed, blocked, and locked stages"
          description="Semantic red is reserved for failed or rejected stages. Locked stages stay muted."
        >
          <HorizontalStageTracker
            label="Exception pipeline"
            items={mixedStages}
          />
        </SectionCard>
        <SectionCard
          title="Long horizontal pipeline"
          description="Internal scrolling keeps the page from overflowing."
        >
          <HorizontalStageTracker
            label="Extended pipeline"
            items={longStages}
          />
        </SectionCard>
        <SectionCard
          title="First and final nodes"
          description="Track padding keeps the first and last nodes, status rings, labels, and focus rings fully visible. Connectors stop at node centers."
        >
          <strong>Short sequence</strong>
          <HorizontalStageTracker label="Short pipeline" items={shortStages} />
          <strong>First node focused</strong>
          <HorizontalStageTracker
            label="First stage focused"
            items={caseStages}
            focusedId="intake"
          />
          <strong>Final node focused</strong>
          <HorizontalStageTracker
            label="Final stage focused"
            items={caseStages}
            focusedId="close"
          />
          <strong>Final node current</strong>
          <HorizontalStageTracker
            label="Final stage current"
            items={lastCurrentStages}
          />
          <strong>Final node failed</strong>
          <HorizontalStageTracker
            label="Final stage failed"
            items={lastFailedStages}
          />
          <strong>Final node completed</strong>
          <HorizontalStageTracker
            label="Final stage completed"
            items={lastCompletedStages}
          />
        </SectionCard>
      </section>

      <section id="stages-vertical" className="ds-stack-20">
        <SectionCard
          title="Vertical stages"
          description="History with title, state, description, actor, and date. The final node, badge, and action stay fully visible."
        >
          <VerticalStageTracker
            label="Approval history"
            items={historyStages}
          />
        </SectionCard>
        <div className="ds-viewport-frame ds-viewport-frame--narrow">
          <div className="ds-viewport-frame__inner">
            <VerticalStageTracker
              compact
              label="Narrow stages"
              items={caseStages}
            />
          </div>
        </div>
      </section>

      <section id="export" className="ds-stack-20">
        <SectionCard
          title="Export"
          description="One Export control. CSV and PDF are alternatives. Pages own the command."
        >
          <div className="ds-button-row">
            <span className="ds-button-row__label">Filtered</span>
            <ExportButton
              options={exportOptions}
              onSelect={() => {
                setExportStatus("preparing");
                setExportOpen(true);
                window.setTimeout(() => setExportStatus("success"), 700);
              }}
            />
          </div>
          <div className="ds-button-row">
            <span className="ds-button-row__label">Selected</span>
            <ExportButton
              selectedCount={5}
              options={exportOptions.map((item) =>
                item.disabled ? { ...item, disabled: false } : item,
              )}
              onSelect={() => undefined}
            />
          </div>
          <div className="ds-button-row">
            <span className="ds-button-row__label">Icon-only</span>
            <ExportButton
              iconOnly
              options={exportOptions}
              onSelect={() => undefined}
            />
          </div>
          <div className="ds-button-row">
            <span className="ds-button-row__label">Preparing</span>
            <ExportButton loading label="Export" />
          </div>
          <div className="ds-button-row">
            <span className="ds-button-row__label">Results</span>
            <ExportResult status="success" fileName="north-operations.csv" />
            <ExportResult
              status="error"
              error="The CSV could not be prepared."
            />
          </div>
          <Button
            variant="secondary"
            onClick={() => {
              setExportStatus("error");
              setExportOpen(true);
            }}
          >
            Failed dialog
          </Button>
        </SectionCard>
        <ExportDialog
          open={exportOpen}
          onClose={() => setExportOpen(false)}
          status={exportStatus}
          fileName="north-operations.csv"
        />
      </section>

      <section id="import" className="ds-stack-20">
        <SectionCard
          title="Import"
          description="Controlled visual flow. No upload request is sent from the design system."
        >
          <ImportButton
            onClick={() => {
              setImportPhase("select");
              setFileName(undefined);
              setImportOpen(true);
            }}
          />
          <div className="ds-button-row">
            <span className="ds-button-row__label">Phases</span>
            {importPhases.map((phase) => (
              <Button
                key={phase}
                size="compact"
                variant="ghost"
                onClick={() => {
                  setImportPhase(phase);
                  setFileName(
                    phase === "select" ? undefined : "harbour-intake.csv",
                  );
                  setImportOpen(true);
                }}
              >
                {phase}
              </Button>
            ))}
          </div>
          <ImportResult phase="partial" />
          <ImportResult phase="failed" />
        </SectionCard>
        <ImportDialog
          open={importOpen}
          onClose={() => setImportOpen(false)}
          phase={importPhase}
          fileName={fileName}
          fileSize={fileName ? "18 KB" : undefined}
          valid={fileName ? (importPhase === "errors" ? 0 : 2) : 0}
          warnings={fileName && importPhase !== "errors" ? 1 : 0}
          errors={importPhase === "errors" ? 2 : 0}
          ready={importPhase === "ready" || importPhase === "warnings"}
          onDownloadTemplate={() => undefined}
          onRemoveFile={() => {
            setFileName(undefined);
            setImportPhase("select");
          }}
          onFiles={(files) => {
            setFileName(files?.[0]?.name ?? "harbour-intake.csv");
            setImportPhase("validating");
            window.setTimeout(() => setImportPhase("ready"), 600);
          }}
          onImport={() => {
            setImportPhase("importing");
            window.setTimeout(() => setImportPhase("completed"), 700);
          }}
          columns={["Name", "Desk", "Amount"]}
          rows={
            fileName
              ? [
                  {
                    id: "1",
                    values: ["A. Rahman", "North", "12,400"],
                    status: importPhase === "errors" ? "error" : "valid",
                    message:
                      importPhase === "errors"
                        ? "Employee code is missing."
                        : undefined,
                  },
                  {
                    id: "2",
                    values: ["Harbour desk", "Harbour", "8,200"],
                    status: importPhase === "errors" ? "error" : "warning",
                    message:
                      importPhase === "errors"
                        ? "Amount is not a number."
                        : "Desk code will be normalized.",
                  },
                ]
              : []
          }
        />
      </section>

      <section id="profile" className="ds-stack-20">
        <SectionCard
          title="Compact profile identity"
          description="Use UserIdentity and ProfileMenu for compact user references. Employee, attendance, and performance headers must use ProfileCoverBanner in the Profile Banner section. ProfileCard remains exported for Sidebar / ProfileMenu only and is legacy for new pages."
        >
          <InlineGroup>
            <ProfileMenu name="A. Rahman" designation="Operations manager" />
            <UserIdentity
              name="M. Khalid"
              designation="Team leader"
              code="EMP-2041"
              size="sm"
            />
            <UserIdentity
              name="L. Noor"
              designation="Assigned employee"
              code="EMP-2204"
              size="sm"
            />
            <AvatarGroup
              people={[
                { name: "A. Rahman" },
                { name: "M. Khalid" },
                { name: "L. Noor" },
                { name: "H. Farid" },
                { name: "S. Noor" },
              ]}
            />
          </InlineGroup>
          <ProfileSummary
            name="A. Rahman"
            designation="Operations manager"
            code="EMP-1182"
            status="Active"
            branch="North"
            department="Operations"
            manager="M. Khalid"
            primaryAction={<Button>View profile</Button>}
            secondaryActions={
              <Button variant="secondary">
                <DsIcon name="edit" size={16} />
                Edit
              </Button>
            }
          />
        </SectionCard>
      </section>
    </>
  );
}
