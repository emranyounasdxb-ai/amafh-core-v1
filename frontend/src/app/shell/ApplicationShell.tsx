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
import { sidebarActiveId, sidebarGroups } from "../navigation/sidebarGroups";
import { NotificationBell } from "../../features/notifications/NotificationBell";
import {
  DesignSystemRoot,
  DsIcon,
  LoadingState,
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarHeader,
  SidebarMobileDrawer,
  SidebarMobileTrigger,
  SidebarProfile,
  SidebarScrollArea,
  ToastProvider,
  ProfileMenu,
  type MenuItem,
  type SidebarNavGroup,
} from "../../design-system";
import { AppErrorBoundary } from "./AppErrorBoundary";
import { ApplicationNavigation } from "./ApplicationNavigation";
import { DubaiClock } from "./DubaiClock";
import styles from "./ApplicationShell.module.css";
import { recordImageSrc } from "../api/recordImages";

export function ApplicationShell() {
  const { session: identity, loading, signOut } = useSession();
  const { route, navigationState, navigate, back } = useAppRoute();
  const [collapsed, setCollapsed] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [signOutError, setSignOutError] = useState("");
  const page = route?.page ?? "dashboard";
  const session = identity;
  const photo = identity
    ? recordImageSrc("employee", {
        id: identity.employeeId,
        avatarFileId: identity.avatarFileId,
      })
    : undefined;

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
        <SidebarMobileTrigger
          label="Close navigation"
          onClick={() => setMobileOpen(false)}
        />
      </SidebarHeader>
      <SidebarContent>
        <SidebarScrollArea>
          <ApplicationNavigation
            groups={groups}
            activeId={activeId}
            onSelect={(id) => go(id as PageId)}
          />
        </SidebarScrollArea>
      </SidebarContent>
      <SidebarFooter>
        <SidebarProfile
          name={identity.displayName}
          src={photo}
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
          <header className={styles.topbar}>
            <div className={styles.topbarLead}>
              <img
                className={styles.logo}
                src="/production/amafh-core-full-logo-exact.svg"
                alt="AMAFH Core"
              />
              <span className={styles.mobileTrigger}>
                <SidebarMobileTrigger onClick={() => setMobileOpen(true)} />
              </span>
            </div>
            <div className={styles.topbarActions}>
              <DubaiClock />
              <NotificationBell
                onViewAll={() => go("notifications")}
                onOpenRecord={openRecord}
              />
              <ProfileMenu
                avatarOnly
                name={identity.displayName}
                src={photo}
                designation={identity.designation}
                items={profileItems()}
              />
            </div>
          </header>
          <div
            className={styles.dock}
            onMouseEnter={() => setCollapsed(false)}
            onMouseLeave={() => setCollapsed(true)}
            onFocus={() => setCollapsed(false)}
            onBlur={(event) => {
              if (!event.currentTarget.contains(event.relatedTarget))
                setCollapsed(true);
            }}
          >
            <Sidebar
              collapsed={collapsed}
              label="Application"
              className={styles.navigationShell}
            >
              <SidebarContent>
                <SidebarScrollArea>
                  <ApplicationNavigation
                    collapsed={collapsed}
                    onExpand={() => setCollapsed(false)}
                    groups={groups}
                    activeId={activeId}
                    onSelect={(id) => go(id as PageId)}
                  />
                </SidebarScrollArea>
              </SidebarContent>
              <SidebarFooter>
                <SidebarProfile
                  collapsed={false}
                  name={identity.displayName}
                  src={photo}
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
            <Sidebar
              collapsed={false}
              label="Application"
              className={styles.navigationShell}
            >
              {sidebarBody}
            </Sidebar>
          </SidebarMobileDrawer>
        </div>
      </ToastProvider>
    </DesignSystemRoot>
  );
}
