import { useMemo, useState } from "react";
import type { PageId } from "../../access";
import { canOpenPage } from "../../access";
import { LiveRoutes } from "../router/LiveRoutes";
import {
  caseDetailNavigation,
  taskNavigation,
  useAppRoute,
  type CaseDetailOrigin,
} from "../router/useAppRoute";
import { useSession } from "../session/useSession";
import { SignIn } from "../session/SignIn";
import {
  pageTitles,
  sidebarActiveId,
  sidebarGroups,
} from "../navigation/sidebarGroups";
import { NotificationBell } from "../../features/notifications/NotificationBell";
import {
  DesignSystemRoot,
  DsIcon,
  LoadingState,
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
  ToastProvider,
  ProfileMenu,
  type MenuItem,
  type SidebarNavGroup,
} from "../../design-system";
import { AppErrorBoundary } from "./AppErrorBoundary";
import { DubaiClock } from "./DubaiClock";
import styles from "./ApplicationShell.module.css";

export function ApplicationShell() {
  const { session: identity, loading, signOut } = useSession();
  const { route, navigationState, navigate, back } = useAppRoute();
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [signOutError, setSignOutError] = useState("");
  const page = route?.page ?? "dashboard";
  const session = identity;

  const groups = useMemo((): SidebarNavGroup[] => {
    if (!session) return [];
    return sidebarGroups
      .map((group) => ({
        id: group.id,
        label: group.label,
        items: group.items
          .filter((item) => canOpenPage(session, item.id))
          .map((item) => ({
            id: item.id,
            label: item.label,
            icon: item.icon,
          })),
      }))
      .filter((group) => group.items.length > 0);
  }, [session]);

  const go = (next: PageId, recordId?: string) => {
    if (!session || !canOpenPage(session, next)) return;
    navigate(next, recordId);
    setMobileOpen(false);
  };

  const profileItems = (closeMobile = false): MenuItem[] => [
    {
      id: "profile",
      label: "My profile",
      icon: <DsIcon name="user" size={16} />,
      onSelect: () => {
        go("my-profile");
        if (closeMobile) setMobileOpen(false);
      },
    },
    {
      id: "out",
      label: "Sign out",
      icon: <DsIcon name="signOut" size={16} />,
      separator: true,
      danger: true,
      onSelect: () => {
        void signOut()
          .then(() => setSignOutError(""))
          .catch((error: Error) => setSignOutError(error.message));
      },
    },
  ];

  if (!session && signOutError) setSignOutError("");

  if (loading) {
    return (
      <DesignSystemRoot>
        <LoadingState title="Loading session" />
      </DesignSystemRoot>
    );
  }

  if (!session || !identity) return <SignIn />;

  const activeId = sidebarActiveId(
    page,
    navigationState?.employeeOrigin,
    navigationState?.caseDetailOrigin,
  );
  const openRecord = (next: PageId, recordId?: string) => {
    if (next === "tasks" && recordId) {
      navigate("tasks", undefined, taskNavigation(recordId));
      return;
    }
    if (next === "case-detail" && recordId) {
      const origin: CaseDetailOrigin =
        page === "customers" ||
        page === "notifications" ||
        page === "tasks" ||
        page === "cases" ||
        page === "my-cases"
          ? page
          : "cases";
      navigate("case-detail", recordId, caseDetailNavigation(origin));
      return;
    }
    go(next, recordId);
  };

  const sidebarBody = (
    <>
      <SidebarHeader>
        <SidebarBrand />
      </SidebarHeader>
      <SidebarContent>
        <SidebarScrollArea>
          <SidebarNavigation
            groups={groups}
            activeId={activeId}
            onSelect={(id) => go(id as PageId)}
          />
        </SidebarScrollArea>
      </SidebarContent>
      <SidebarFooter>
        <SidebarProfile
          name={identity.displayName}
          designation={identity.designation}
          items={profileItems(true)}
        />
        {signOutError ? (
          <p className="ds-app-signout-error" role="alert">
            {signOutError}
          </p>
        ) : null}
      </SidebarFooter>
    </>
  );

  return (
    <DesignSystemRoot>
      <ToastProvider>
        <div className={`ds-app-shell ${styles.shell}`}>
          <div className={styles.dock}>
            <Sidebar collapsed={collapsed} label="Application">
              <SidebarHeader>
                <SidebarBrand />
                <SidebarToggle
                  collapsed={collapsed}
                  onClick={() => setCollapsed((value) => !value)}
                />
              </SidebarHeader>
              <SidebarContent>
                <SidebarScrollArea>
                  <SidebarNavigation
                    groups={groups}
                    activeId={activeId}
                    onSelect={(id) => go(id as PageId)}
                  />
                </SidebarScrollArea>
              </SidebarContent>
              <SidebarFooter>
                <SidebarProfile
                  name={identity.displayName}
                  designation={identity.designation}
                  items={profileItems()}
                />
                {signOutError ? (
                  <p className="ds-app-signout-error" role="alert">
                    {signOutError}
                  </p>
                ) : null}
              </SidebarFooter>
            </Sidebar>
          </div>
          <div className={styles.column}>
            <header className={styles.topbar}>
              <div className={styles.topbarLead}>
                <span className={styles.mobileTrigger}>
                  <SidebarMobileTrigger onClick={() => setMobileOpen(true)} />
                </span>
                {page !== "cases" &&
                page !== "customers" &&
                page !== "tasks" &&
                page !== "notifications" ? (
                  <p className={styles.pageContext}>{pageTitles[page]}</p>
                ) : null}
              </div>
              <div className={styles.topbarActions}>
                <DubaiClock />
                <NotificationBell
                  onViewAll={() => go("notifications")}
                  onOpenRecord={openRecord}
                />
                <ProfileMenu
                  name={identity.displayName}
                  designation={identity.designation}
                  items={profileItems()}
                />
              </div>
            </header>
            <main className={styles.main}>
              <AppErrorBoundary>
                <LiveRoutes
                  route={route}
                  navigationState={navigationState}
                  navigate={(next, id, state) => {
                    if (session && canOpenPage(session, next))
                      navigate(next, id, state);
                  }}
                  back={back}
                />
              </AppErrorBoundary>
            </main>
          </div>
          <SidebarMobileDrawer
            open={mobileOpen}
            onClose={() => setMobileOpen(false)}
            label="Application"
          >
            <Sidebar collapsed={false} label="Application">
              {sidebarBody}
            </Sidebar>
          </SidebarMobileDrawer>
        </div>
      </ToastProvider>
    </DesignSystemRoot>
  );
}
