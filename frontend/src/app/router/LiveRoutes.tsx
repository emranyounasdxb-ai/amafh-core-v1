import type { PageId } from "../../access";
import { canOpenPage } from "../../access";
import { useSession } from "../session/useSession";
import { CasesPage } from "../../features/cases/live/CasesPage";
import { CaseDetailPage } from "../../features/cases/live/CaseDetailPage";
import { BankStageUpdatesPage } from "../../features/cases/live/BankStageUpdatesPage";
import { Button, NotFoundState, PermissionDeniedState } from "../../design-system";
import { DashboardPage } from "../../features/dashboard/live/DashboardPage";
import { TasksPage } from "../../features/tasks/TasksPage";
import { NotificationsPage } from "../../features/notifications/NotificationsPage";
import { EmployeeDetailPage } from "../../features/employees/live/EmployeeDetailPage";
import { EmployeesPage } from "../../features/employees/live/EmployeesPage";
import { OrganizationPage } from "../../features/organization/OrganizationPage";
import { CustomerDetailPage } from "../../features/customers/live/CustomerDetailPage";
import { CustomersPage } from "../../features/customers/live/CustomersPage";
import { TeamDetailPage } from "../../features/teams/live/TeamDetailPage";
import { TeamsPage } from "../../features/teams/live/TeamsPage";
import { AssetDetailPage } from "../../features/assets/live/AssetDetailPage";
import { AssetsPage } from "../../features/assets/live/AssetsPage";
import { AttendancePage } from "../../features/attendance/live/AttendancePage";
import { FinancePage } from "../../features/finance/live/FinancePage";
import { MyWalletPage } from "../../features/wallet/MyWalletPage";
import { ReportsPage } from "../../features/reports/ReportsPage";
import { PerformancePage } from "../../features/performance/live/PerformancePage";
import { SettingsPage } from "../../features/settings/live/SettingsPage";
import type { AppRoute } from "./routes";
import {
  HrCertificatesPage,
  HrDocumentsPage,
  HrLettersPage,
  HrOffboardingPage,
  HrPackagesPage,
  HrVisaPage,
} from "../../features/hr/HrPages";
import {
  caseDetailNavigation,
  employeeSectionNavigation,
  taskNavigation,
  type AppNavigationState,
  type CaseDetailOrigin,
  type EmployeeSection,
} from "./useAppRoute";

export function LiveRoutes({
  route,
  navigationState,
  navigate,
  back,
}: {
  route: AppRoute | null;
  navigationState: AppNavigationState | null;
  navigate: (
    page: PageId,
    id?: string,
    state?: AppNavigationState | null,
  ) => void;
  back: () => void;
}) {
  const { session } = useSession();
  if (!session) return null;
  if (!route)
    return (
      <NotFoundState
        action={
          <Button onClick={() => navigate("dashboard")}>Go to dashboard</Button>
        }
      />
    );
  if (!canOpenPage(session, route.page))
    return <PermissionDeniedState />;
  if (route.page === "cases")
    return (
      <CasesPage
        open={(id) =>
          navigate("case-detail", id, caseDetailNavigation("cases"))
        }
      />
    );
  if (route.page === "my-cases")
    return (
      <CasesPage
        key={session.employeeId}
        mode="own"
        open={(id) =>
          navigate("case-detail", id, caseDetailNavigation("my-cases"))
        }
      />
    );
  if (route.page === "bank-stage-updates")
    return (
      <BankStageUpdatesPage
        batchId={route.recordId}
        openBatch={(id) => navigate("bank-stage-updates", id)}
      />
    );
  if (route.page === "case-detail" && route.recordId) {
    const origin = navigationState?.caseDetailOrigin;
    const canReturn =
      Boolean(origin) && canOpenPage(session, origin as PageId);
    return (
      <CaseDetailPage
        key={route.recordId}
        id={route.recordId}
        back={() =>
          navigate(
            canReturn
              ? (origin as CaseDetailOrigin)
              : canOpenPage(session, "cases")
                ? "cases"
                : "my-cases",
          )
        }
        openCustomer={
          canOpenPage(session, "customers")
            ? (id) => navigate("customers", id)
            : undefined
        }
        openEmployee={
          canOpenPage(session, "employees")
            ? (id) => navigate("employees", id)
            : undefined
        }
      />
    );
  }
  const props = {
    id: route.recordId,
    select: (id?: string) => navigate(route.page, id),
  };
  switch (route.page) {
    case "dashboard":
      return (
        <DashboardPage
          openTasks={() => navigate("tasks")}
          openNotifications={() => navigate("notifications")}
        />
      );
    case "tasks":
      return (
        <TasksPage
          openTaskId={navigationState?.openTaskId}
          openTaskNonce={navigationState?.openTaskNonce}
          onOpenRecord={(page, recordId) => {
            if (page === "tasks" && recordId) {
              navigate("tasks", undefined, taskNavigation(recordId));
              return;
            }
            if (page === "case-detail" && recordId) {
              navigate(
                "case-detail",
                recordId,
                caseDetailNavigation("tasks"),
              );
              return;
            }
            navigate(page, recordId);
          }}
        />
      );
    case "notifications":
      return (
        <NotificationsPage
          onOpenRecord={(page, recordId) => {
            if (page === "tasks" && recordId) {
              navigate("tasks", undefined, taskNavigation(recordId));
              return;
            }
            if (page === "case-detail" && recordId) {
              navigate(
                "case-detail",
                recordId,
                caseDetailNavigation("notifications"),
              );
              return;
            }
            navigate(page, recordId);
          }}
        />
      );
    case "my-profile":
      return (
        <EmployeeDetailPage
          key={session.employeeId}
          id={session.employeeId}
          own
          back={() => navigate("dashboard")}
        />
      );
    case "my-wallet":
      return (
        <MyWalletPage
          openCase={
            canOpenPage(session, "case-detail")
              ? (id) =>
                  navigate("case-detail", id, caseDetailNavigation("my-wallet"))
              : undefined
          }
        />
      );
    case "employees":
      if (route.recordId) {
        const origin = navigationState?.employeeOrigin;
        const returnTo =
          origin && canOpenPage(session, origin) ? origin : "employees";
        return (
          <EmployeeDetailPage
            key={route.recordId}
            id={route.recordId}
            focus={navigationState?.employeeSection}
            back={() => navigate(returnTo)}
            openEmployee={(id) => navigate("employees", id)}
          />
        );
      }
      return <EmployeesPage open={(id) => navigate("employees", id)} />;
    case "hr-packages":
    case "hr-documents":
    case "hr-visa":
    case "hr-letters":
    case "hr-certificates":
    case "hr-offboarding": {
      const page = route.page;
      const open = (id: string, section?: EmployeeSection) =>
        navigate("employees", id, employeeSectionNavigation(page, section));
      if (page === "hr-packages") return <HrPackagesPage open={open} />;
      if (page === "hr-documents") return <HrDocumentsPage open={open} />;
      if (page === "hr-visa") return <HrVisaPage open={open} />;
      if (page === "hr-letters") return <HrLettersPage open={open} />;
      if (page === "hr-certificates") return <HrCertificatesPage open={open} />;
      return <HrOffboardingPage open={open} />;
    }
    case "organization":
      return (
        <OrganizationPage
          openPerformance={(employeeId) =>
            navigate("performance-detail", employeeId, {
              performanceDetailOrigin: "organization",
              sessionEmployeeId: session.employeeId,
            })
          }
        />
      );
    case "customers":
      if (route.recordId)
        return (
          <CustomerDetailPage
            key={route.recordId}
            id={route.recordId}
            back={() => navigate("customers")}
            openCase={
              canOpenPage(session, "case-detail")
                ? (id) =>
                    navigate(
                      "case-detail",
                      id,
                      caseDetailNavigation("customers"),
                    )
                : undefined
            }
          />
        );
      return (
        <CustomersPage open={(id) => navigate("customers", id)} />
      );
    case "teams":
      if (route.recordId)
        return (
          <TeamDetailPage
            key={route.recordId}
            id={route.recordId}
            back={() => navigate("teams")}
            openEmployee={
              canOpenPage(session, "employees")
                ? (id) => navigate("employees", id)
                : undefined
            }
          />
        );
      return <TeamsPage open={(id) => navigate("teams", id)} />;
    case "assets":
      if (route.recordId)
        return (
          <AssetDetailPage
            key={route.recordId}
            id={route.recordId}
            back={() => navigate("assets")}
            openEmployee={
              canOpenPage(session, "employees")
                ? (id) => navigate("employees", id)
                : undefined
            }
          />
        );
      return <AssetsPage open={(id) => navigate("assets", id)} />;
    case "attendance":
      return <AttendancePage {...props} />;
    case "finance":
      return <FinancePage />;
    case "reports":
      return <ReportsPage />;
    case "settings":
      return (
        <SettingsPage
          key={route.recordId ?? "index"}
          sectionId={route.recordId}
          open={(sectionId) => navigate("settings", sectionId)}
        />
      );
    case "performance":
    case "performance-detail":
      return (
        <PerformancePage
          id={route.recordId}
          select={(id) => {
            if (id) {
              navigate("performance-detail", id, {
                performanceDetailOrigin: "performance",
                sessionEmployeeId: session.employeeId,
              });
              return;
            }
            const hasCurrentCaller =
              route.page === "performance-detail" &&
              navigationState?.sessionEmployeeId === session.employeeId &&
              Boolean(navigationState.performanceDetailOrigin);
            if (hasCurrentCaller) back();
            else navigate("performance");
          }}
        />
      );
    default:
      return (
        <NotFoundState
          action={
            <Button onClick={() => navigate("dashboard")}>
              Go to dashboard
            </Button>
          }
        />
      );
  }
}
