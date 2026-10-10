import { useState } from "react";
import {
  Avatar,
  Button,
  CompactDate,
  Dialog,
  EmptyState,
  EmptyValue,
  ErrorState,
  FileUpload,
  InfoField,
  InfoGrid,
  IconButton,
  InlineNotice,
  LoadingState,
  MonetaryAmount,
  NotFoundState,
  OfflineState,
  PageContainer,
  Pagination,
  PermissionDeniedState,
  ProfileBannerPrimaryAction,
  ProfileBannerSecondaryAction,
  ProfileCoverActions,
  ProfileCoverBanner,
  ProfileCoverIdentity,
  ProfileCoverMetadata,
  RelatedRecordList,
  SectionCard,
  StatusBadge,
  Tabs,
  Timeline,
  TruncatedText,
  nationalityOptions,
  type MenuItem,
  type RelatedRecordItem,
  type TimelineItem,
} from "../../../design-system";
import { DsIcon } from "../../../design-system/icons";
import {
  canManageEmployees,
  canOpenPage,
  hasPermission,
} from "../../../access";
import { ApiFailure } from "../../../app/api/http";
import type { NamedRecord, Page } from "../../../app/api/models";
import { useResource } from "../../../app/api/useResource";
import type { EmployeeSection } from "../../../app/router/useAppRoute";
import { useSession } from "../../../app/session/useSession";
import { EmployeeAccessSection } from "./EmployeeAccessSection";
import {
  EmployeeCommandDialog,
  type EmployeeCommandKind,
} from "./EmployeeCommandDialog";
import {
  canRecordLastWorkingDate,
  employeeAvatarSrc,
  employeeCode,
  employeeLookupPath,
  employeeName,
  employeeStatusTone,
  namedLabel,
  readEmployeeLookup,
  type AssignmentHistoryRecord,
  type EmployeeDetailRecord,
  type EmployeeLabelRecord,
} from "./employeePresentation";
import styles from "./EmployeeDetailPage.module.css";
import { uploadRecordImage } from "../../../app/api/recordImages";
import { EmployeeDocumentsSection } from "./hr/EmployeeDocumentsSection";
import { EmployeeLettersSection } from "./hr/EmployeeLettersSection";
import { EmployeePackageSection } from "./hr/EmployeePackageSection";
import { EmployeeVisaSection } from "./hr/EmployeeVisaSection";

type Department = NamedRecord & { branch_id?: string };
type ClawbackMention = {
  id: string;
  case_id: string | null;
  amount_aed: number | string | null;
  clawback_date: string | null;
  reason: string | null;
};

const nationalities = nationalityOptions();
type DetailTab = "overview" | EmployeeSection | "history";

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function Value({ value }: { value: string | null | undefined }) {
  return value ? <TruncatedText value={value} /> : <EmptyValue />;
}

function nationalityLabel(code: string | null | undefined) {
  if (!code) return "";
  return nationalities.find((item) => item.value === code)?.label || code;
}

export function EmployeeDetailPage({
  id,
  own = false,
  focus,
  back,
  openEmployee,
}: {
  id: string;
  own?: boolean;
  focus?: EmployeeSection;
  back: () => void;
  openEmployee?: (id: string) => void;
}) {
  const { api, session } = useSession();
  const tabContext = `${id}:${focus ?? "overview"}`;
  const [tabSelection, setTabSelection] = useState<{
    context: string;
    value: DetailTab;
  }>({ context: tabContext, value: focus ?? "overview" });
  const [refresh, setRefresh] = useState(0);
  const [packageRefresh, setPackageRefresh] = useState(0);
  const [command, setCommand] = useState<EmployeeCommandKind | null>(null);
  const [notice, setNotice] = useState("");
  const [avatarOpen, setAvatarOpen] = useState(false);
  const [avatarFiles, setAvatarFiles] = useState<FileList | null>(null);
  const [avatarBusy, setAvatarBusy] = useState(false);
  const [avatarError, setAvatarError] = useState("");
  const [mentionsPage, setMentionsPage] = useState(1);

  const resource = useResource<EmployeeDetailRecord>(
    `/employees/${id}`,
    refresh,
  );
  const history = useResource<AssignmentHistoryRecord[]>(
    `/employees/${id}/assignments`,
    refresh,
  );
  const branches = useResource<NamedRecord[]>("/branches");
  const departments = useResource<Department[]>("/departments");
  const designations = useResource<NamedRecord[]>("/designations");
  const employee = resource.data;
  const isSelf = Boolean(session && employee?.id === session.employeeId);
  const mentions = useResource<Page<ClawbackMention>>(
    isSelf
      ? `/employees/me/clawback-mentions${mentionsPage > 1 ? `?page=${mentionsPage}` : ""}`
      : null,
    refresh,
  );
  const lookup = useResource<Record<string, EmployeeLabelRecord>>(
    employeeLookupPath([
      employee?.reportingManagerId,
      ...(history.data ?? []).map((row) => row.reporting_manager_id),
    ]),
    refresh,
    readEmployeeLookup,
    "employee-lookup",
  );

  if (!session) return null;
  const mayWrite = canManageEmployees(session) && !own;
  const canWriteAvatar = mayWrite || isSelf;
  const canOpenEmployee = Boolean(
    openEmployee && canOpenPage(session, "employees"),
  );
  const unavailable = (
    <NotFoundState
      title="Employee unavailable"
      description="This record is not available in the current authorized scope."
      action={
        <Button variant="secondary" onClick={back}>
          Back
        </Button>
      }
    />
  );
  if (resource.denied) {
    const missing = /unavailable|not found/i.test(resource.error);
    return (
      <PageContainer>
        {missing ? unavailable : <PermissionDeniedState />}
      </PageContainer>
    );
  }
  if (resource.error && !employee)
    return (
      <PageContainer>
        {isOffline(resource.error) ? (
          <OfflineState />
        ) : (
          <ErrorState description={resource.error} retry={resource.reload} />
        )}
      </PageContainer>
    );
  if (resource.loading && !employee)
    return (
      <PageContainer>
        <LoadingState title="Loading Employee" />
      </PageContainer>
    );
  if (!employee) return <PageContainer>{unavailable}</PageContainer>;

  const name = employeeName(employee);
  const canManagePrivileged =
    session.designation === "Owner" ||
    !["Owner", "Managing Director"].includes(employee.designation || "");
  const code = employeeCode(employee);
  const branch = namedLabel(branches.data, employee.branchId);
  const department = namedLabel(departments.data, employee.departmentId);
  const manager = employee.reportingManagerId
    ? lookup.data?.[employee.reportingManagerId]
    : undefined;
  const managerLabel = employee.reportingManagerId
    ? manager
      ? employeeName(manager)
      : "Assigned employee"
    : "";

  const overflow: MenuItem[] = [];
  if (mayWrite && canManagePrivileged && employee.status === "Pending Setup")
    overflow.push({
      id: "activate",
      label: "Activate employee",
      onSelect: () => setCommand("activate"),
    });
  if (
    mayWrite &&
    canManagePrivileged &&
    employee.status !== "Offboarded" &&
    employee.designation !== "Owner"
  )
    overflow.push({
      id: "offboard",
      label: "Offboard employee",
      danger: true,
      separator: overflow.length > 0,
      onSelect: () => setCommand("offboard"),
    });
  if (!own && canRecordLastWorkingDate(session.designation, employee))
    overflow.push({
      id: "last-working-date",
      label: "Record last working date",
      onSelect: () => setCommand("lastWorkingDate"),
    });

  const uploadAvatar = async () => {
    const file = avatarFiles?.[0];
    if (!file) {
      setAvatarError("Select an image to upload.");
      return;
    }
    setAvatarBusy(true);
    setAvatarError("");
    try {
      await uploadRecordImage(api, "employee", employee.id, file);
      setAvatarOpen(false);
      setAvatarFiles(null);
      setNotice("Profile photo updated.");
      setRefresh((value) => value + 1);
    } catch (failure) {
      setAvatarError(
        failure instanceof ApiFailure || failure instanceof Error
          ? failure.message
          : "Image upload failed",
      );
    } finally {
      setAvatarBusy(false);
    }
  };

  const historyItems: TimelineItem[] = [...(history.data ?? [])]
    .reverse()
    .map((row) => {
      const current = !row.assignment_end_date;
      const designation =
        namedLabel(designations.data, row.designation_id) || "Designation";
      const scope = [
        namedLabel(branches.data, row.branch_id),
        namedLabel(departments.data, row.department_id),
      ].filter(Boolean);
      const reportingManager = row.reporting_manager_id
        ? lookup.data?.[row.reporting_manager_id]
          ? employeeName(lookup.data[row.reporting_manager_id])
          : "Assigned employee"
        : "";
      return {
        id: row.id,
        time: (
          <span className={styles.period}>
            <CompactDate value={row.assignment_start_date} />
            <span aria-hidden="true">–</span>
            {row.assignment_end_date ? (
              <CompactDate value={row.assignment_end_date} />
            ) : (
              <span>Present</span>
            )}
          </span>
        ),
        title: designation,
        description: scope.length
          ? scope.join(" · ")
          : "Branch and Department not assigned",
        actor: reportingManager
          ? `Reporting Manager: ${reportingManager}`
          : undefined,
        status: current ? "Current" : "Ended",
        tone: current ? "success" : "neutral",
      } satisfies TimelineItem;
    });

  const mentionItems: RelatedRecordItem[] = (mentions.data?.items ?? []).map(
    (item) => ({
      id: item.id,
      title: item.clawback_date ? (
        <span className={styles.inline}>
          Clawback · <CompactDate value={item.clawback_date} />
        </span>
      ) : (
        "Clawback"
      ),
      meta: (
        <span className={styles.inline}>
          <MonetaryAmount compact={false} value={item.amount_aed} />
          {item.reason ? <span>· {item.reason}</span> : null}
        </span>
      ),
    }),
  );
  const mentionPages = Math.max(
    1,
    Math.ceil((mentions.data?.total ?? 0) / (mentions.data?.pageSize || 25)),
  );
  const tabs: { id: DetailTab; label: string }[] = [
    { id: "overview", label: "Overview" },
    ...(!own && hasPermission(session, "package.read")
      ? [{ id: "packages" as const, label: "Package" }]
      : []),
    ...(!own && hasPermission(session, "employee_document.read")
      ? [{ id: "documents" as const, label: "Documents" }]
      : []),
    ...(!own && hasPermission(session, "visa.read")
      ? [{ id: "visa" as const, label: "Visa / PRO" }]
      : []),
    ...(!own && hasPermission(session, "hr_letter.read")
      ? [{ id: "letters" as const, label: "Letters" }]
      : []),
    { id: "history", label: "History" },
  ];
  const requestedTab =
    tabSelection.context === tabContext
      ? tabSelection.value
      : (focus ?? "overview");
  const activeTab = tabs.some((tab) => tab.id === requestedTab)
    ? requestedTab
    : "overview";
  const accessSection = ["Owner", "HR", "Managing Director"].includes(
    session.designation,
  ) ? (
    <EmployeeAccessSection
      employeeId={employee.id}
      employeeName={name}
      employeeCode={code}
      employeeStatus={employee.status}
      employeeDesignation={employee.designation}
      account={employee.account}
      embedded={!own}
      onChanged={() => setRefresh((value) => value + 1)}
    />
  ) : null;

  const mentionsSection = isSelf ? (
    mentions.loading && !mentions.data ? (
      <SectionCard compact title="My Clawback mentions">
        <LoadingState title="Loading Clawback mentions" />
      </SectionCard>
    ) : mentionItems.length ? (
      <>
        <RelatedRecordList title="My Clawback mentions" items={mentionItems} />
        {mentionPages > 1 ? (
          <Pagination
            page={mentionsPage}
            pageCount={mentionPages}
            onPageChange={setMentionsPage}
          />
        ) : null}
      </>
    ) : (
      <SectionCard compact title="My Clawback mentions">
        {mentions.error ? (
          <ErrorState description={mentions.error} retry={mentions.reload} />
        ) : own ? (
          <EmptyState
            title="No Clawback mentions"
            description="There are no Clawback records that mention you."
          />
        ) : (
          <p className={styles.empty}>
            There are no Clawback records that mention you.
          </p>
        )}
      </SectionCard>
    )
  ) : null;

  return (
    <PageContainer>
      <div className={own ? styles.page : styles.detailPage}>
        <div className={own ? undefined : styles.compactHeader}>
          <ProfileCoverBanner
            compact={!own}
            identity={
              own ? (
                <ProfileCoverIdentity
                  name={name}
                  designation={employee.designation || undefined}
                  code={code || undefined}
                  src={employeeAvatarSrc(employee)}
                  status={employee.status}
                  statusTone={employeeStatusTone(employee.status)}
                  contextLabel={own ? "My profile" : "Employee"}
                  onEditAvatar={
                    canWriteAvatar
                      ? () => {
                          setAvatarError("");
                          setAvatarFiles(null);
                          setAvatarOpen(true);
                        }
                      : undefined
                  }
                />
              ) : (
                <div className={styles.identity}>
                  <div className={styles.avatar}>
                    <Avatar
                      name={name}
                      src={employeeAvatarSrc(employee)}
                      size="xl"
                    />
                    {canWriteAvatar ? (
                      <span className={styles.avatarEdit}>
                        <IconButton
                          label="Edit photo"
                          size="compact"
                          variant="secondary"
                          onClick={() => {
                            setAvatarError("");
                            setAvatarFiles(null);
                            setAvatarOpen(true);
                          }}
                        >
                          <DsIcon name="edit" size={14} />
                        </IconButton>
                      </span>
                    ) : null}
                  </div>
                  <div className={styles.identityCopy}>
                    <span className={styles.context}>Employee</span>
                    <h1>{name}</h1>
                    <span>{employee.designation || <EmptyValue />}</span>
                    <span
                      title="Company Employee Code"
                      aria-label={`Company Employee Code: ${code || "Not recorded"}`}
                    >
                      {code || <EmptyValue />}
                    </span>
                    <StatusBadge
                      tone={employeeStatusTone(employee.status)}
                      className="ds-profile-banner__status"
                    >
                      {employee.status}
                    </StatusBadge>
                  </div>
                </div>
              )
            }
            actions={
              <ProfileCoverActions
                onBack={back}
                primary={
                  mayWrite &&
                  canManagePrivileged &&
                  employee.status !== "Offboarded" ? (
                    <ProfileBannerPrimaryAction
                      onClick={() => setCommand("assignment")}
                    >
                      Change assignment
                    </ProfileBannerPrimaryAction>
                  ) : undefined
                }
                secondary={
                  mayWrite ? (
                    <ProfileBannerSecondaryAction
                      onClick={() => setCommand("profile")}
                    >
                      Edit profile
                    </ProfileBannerSecondaryAction>
                  ) : undefined
                }
                overflow={overflow}
              />
            }
            metadata={
              own ? (
                <ProfileCoverMetadata
                  items={[
                    {
                      id: "branch",
                      label: "Branch",
                      icon: "branch",
                      value: branch || <EmptyValue />,
                    },
                    {
                      id: "department",
                      label: "Department",
                      icon: "department",
                      value: department || <EmptyValue />,
                    },
                    {
                      id: "manager",
                      label: "Reporting Manager",
                      icon: "user",
                      value: managerLabel || <EmptyValue />,
                    },
                    {
                      id: "mobile",
                      label: "Mobile",
                      icon: "phone",
                      value: employee.mobile || <EmptyValue />,
                    },
                    {
                      id: "email",
                      label: "Personal email",
                      icon: "mail",
                      value: employee.personalEmail || <EmptyValue />,
                    },
                  ]}
                />
              ) : undefined
            }
          />
        </div>
        {!own ? (
          <Tabs
            label="Employee sections"
            className={styles.tabs}
            items={tabs}
            value={activeTab}
            onChange={(value) => {
              if (tabs.some((tab) => tab.id === value))
                setTabSelection({
                  context: tabContext,
                  value: value as DetailTab,
                });
            }}
          />
        ) : null}

        {resource.updating ? (
          <InlineNotice tone="info" title="Refreshing">
            Updating the authorized Employee record.
          </InlineNotice>
        ) : null}
        {notice ? (
          <InlineNotice tone="success" title="Saved">
            {notice}
          </InlineNotice>
        ) : null}

        {own ? (
          <>
            <div className={styles.columns}>
              <SectionCard compact title="Employment">
                <InfoGrid>
                  <InfoField
                    label="Company Employee Code"
                    value={<Value value={code} />}
                  />
                  <InfoField
                    label="Designation"
                    value={<Value value={employee.designation} />}
                  />
                  <InfoField
                    label="Status"
                    value={
                      <StatusBadge tone={employeeStatusTone(employee.status)}>
                        {employee.status}
                      </StatusBadge>
                    }
                  />
                  <InfoField
                    label="Joining date"
                    value={
                      employee.dateOfJoining ? (
                        <CompactDate value={employee.dateOfJoining} />
                      ) : (
                        <EmptyValue />
                      )
                    }
                  />
                  {employee.status === "Offboarded" ? (
                    <InfoField
                      label="Last working date"
                      value={
                        employee.lastWorkingDate ? (
                          <CompactDate value={employee.lastWorkingDate} />
                        ) : (
                          "Not recorded"
                        )
                      }
                    />
                  ) : null}
                </InfoGrid>
              </SectionCard>

              <SectionCard compact title="Current assignment">
                <InfoGrid>
                  <InfoField label="Branch" value={<Value value={branch} />} />
                  <InfoField
                    label="Department"
                    value={<Value value={department} />}
                  />
                  <InfoField
                    label="Designation"
                    value={<Value value={employee.designation} />}
                  />
                  <InfoField
                    label="Reporting Manager"
                    value={<Value value={managerLabel} />}
                  />
                </InfoGrid>
              </SectionCard>

              <SectionCard compact title="Contact">
                <InfoGrid>
                  <InfoField
                    label="Mobile"
                    value={<Value value={employee.mobile} />}
                  />
                  <InfoField
                    label="Personal email"
                    value={<Value value={employee.personalEmail} />}
                  />
                </InfoGrid>
              </SectionCard>

              <SectionCard compact title="Personal details">
                <InfoGrid>
                  <InfoField
                    label="Nationality"
                    value={
                      <Value value={nationalityLabel(employee.nationality)} />
                    }
                  />
                  <InfoField
                    label="Gender"
                    value={<Value value={employee.gender} />}
                  />
                  <InfoField
                    label="Marital status"
                    value={<Value value={employee.maritalStatus} />}
                  />
                  <InfoField
                    label="Passport number"
                    value={<Value value={employee.passportNumber} />}
                  />
                  <InfoField
                    label="Emirates ID"
                    value={<Value value={employee.emiratesIdNumber} />}
                  />
                </InfoGrid>
              </SectionCard>
            </div>

            <SectionCard compact title="Reporting line">
              {employee.reportingManagerId ? (
                <div className={styles.person}>
                  <Avatar
                    name={managerLabel}
                    src={employeeAvatarSrc(manager)}
                    size="md"
                  />
                  <div className={styles.personCopy}>
                    <div className={styles.personName}>
                      <TruncatedText value={managerLabel} />
                    </div>
                    <span>
                      {[manager?.designation, employeeCode(manager)]
                        .filter(Boolean)
                        .join(" · ") || "Details unavailable in this view"}
                    </span>
                  </div>
                  {manager && canOpenEmployee ? (
                    <Button
                      size="compact"
                      variant="secondary"
                      onClick={() => openEmployee?.(manager.id)}
                    >
                      View employee
                    </Button>
                  ) : null}
                </div>
              ) : (
                <EmptyState
                  title="No Reporting Manager"
                  description="This employee has no Reporting Manager assigned."
                />
              )}
            </SectionCard>
          </>
        ) : (
          <div
            role="tabpanel"
            aria-label="Overview"
            hidden={activeTab !== "overview"}
          >
            <div className={styles.overview}>
              <SectionCard
                compact
                title="Employee details"
                className={styles.overviewCard}
              >
                <section className={styles.detailGroup} aria-label="Employment">
                  <h3>Employment</h3>
                  <InfoGrid>
                    <InfoField
                      label="Joining date"
                      value={
                        employee.dateOfJoining ? (
                          <CompactDate value={employee.dateOfJoining} />
                        ) : (
                          <EmptyValue />
                        )
                      }
                    />
                    {employee.status === "Offboarded" ? (
                      <InfoField
                        label="Last working date"
                        value={
                          employee.lastWorkingDate ? (
                            <CompactDate value={employee.lastWorkingDate} />
                          ) : (
                            "Not recorded"
                          )
                        }
                      />
                    ) : null}
                  </InfoGrid>
                </section>
                <section className={styles.detailGroup} aria-label="Contact">
                  <h3>Contact</h3>
                  <InfoGrid>
                    <InfoField
                      label="Mobile"
                      value={employee.mobile || <EmptyValue />}
                    />
                    <InfoField
                      label="Personal email"
                      value={employee.personalEmail || <EmptyValue />}
                    />
                  </InfoGrid>
                </section>
                <section
                  className={styles.detailGroup}
                  aria-label="Personal details"
                >
                  <h3>Personal details</h3>
                  <InfoGrid>
                    <InfoField
                      label="Nationality"
                      value={
                        nationalityLabel(employee.nationality) || <EmptyValue />
                      }
                    />
                    <InfoField
                      label="Gender"
                      value={employee.gender || <EmptyValue />}
                    />
                    <InfoField
                      label="Marital status"
                      value={employee.maritalStatus || <EmptyValue />}
                    />
                    <InfoField
                      label="Passport number"
                      value={employee.passportNumber || <EmptyValue />}
                    />
                    <InfoField
                      label="Emirates ID"
                      value={employee.emiratesIdNumber || <EmptyValue />}
                    />
                    <InfoField
                      label="Profile photo"
                      value={
                        employee.avatarFileId ? "Uploaded" : "Not uploaded"
                      }
                    />
                  </InfoGrid>
                </section>
                {mentionsSection ? (
                  <div className={styles.selfMentions}>{mentionsSection}</div>
                ) : null}
              </SectionCard>
              <SectionCard
                compact
                title="Assignment & access"
                className={styles.overviewCard}
              >
                <div className={styles.detailGroup}>
                  <InfoGrid>
                    <InfoField
                      label="Branch"
                      value={branch || <EmptyValue />}
                    />
                    <InfoField
                      label="Department"
                      value={department || <EmptyValue />}
                    />
                    <InfoField
                      label="Reporting Manager"
                      value={
                        employee.reportingManagerId ? (
                          <div className={styles.person}>
                            <Avatar
                              name={managerLabel}
                              src={employeeAvatarSrc(manager)}
                              size="md"
                            />
                            <div className={styles.personCopy}>
                              <span>{managerLabel}</span>
                              <span>
                                {[manager?.designation, employeeCode(manager)]
                                  .filter(Boolean)
                                  .join(" · ") ||
                                  "Details unavailable in this view"}
                              </span>
                            </div>
                            {manager && canOpenEmployee ? (
                              <Button
                                size="compact"
                                variant="secondary"
                                onClick={() => openEmployee?.(manager.id)}
                              >
                                View employee
                              </Button>
                            ) : null}
                          </div>
                        ) : (
                          "Not assigned"
                        )
                      }
                    />
                  </InfoGrid>
                </div>
                {accessSection}
              </SectionCard>
            </div>
          </div>
        )}

        <div
          role={own ? undefined : "tabpanel"}
          aria-label={own ? undefined : "History"}
          hidden={!own && activeTab !== "history"}
        >
          <SectionCard compact title="Historical assignments">
            {history.loading && !history.data ? (
              <LoadingState title="Loading assignment history" />
            ) : history.error && !history.data ? (
              <ErrorState description={history.error} retry={history.reload} />
            ) : historyItems.length ? (
              <Timeline compact items={historyItems} />
            ) : own ? (
              <EmptyState
                title="No assignment history"
                description="No assignments have been recorded for this employee."
              />
            ) : (
              <p className={styles.empty}>
                No assignments have been recorded for this employee.
              </p>
            )}
          </SectionCard>
        </div>

        {!own && hasPermission(session, "package.read") ? (
          <div
            id="employee-section-packages"
            className={styles.anchor}
            role="tabpanel"
            aria-label="Package"
            hidden={activeTab !== "packages"}
          >
            <EmployeePackageSection
              employeeId={employee.id}
              employeeStatus={employee.status}
              onChanged={() => setPackageRefresh((value) => value + 1)}
            />
          </div>
        ) : null}
        {!own && hasPermission(session, "employee_document.read") ? (
          <div
            id="employee-section-documents"
            className={styles.anchor}
            role="tabpanel"
            aria-label="Documents"
            hidden={activeTab !== "documents"}
          >
            <EmployeeDocumentsSection
              employeeId={employee.id}
              employeeStatus={employee.status}
            />
          </div>
        ) : null}
        {!own && hasPermission(session, "visa.read") ? (
          <div
            id="employee-section-visa"
            className={styles.anchor}
            role="tabpanel"
            aria-label="Visa / PRO"
            hidden={activeTab !== "visa"}
          >
            <EmployeeVisaSection
              employeeId={employee.id}
              employeeStatus={employee.status}
              canReadDocuments={hasPermission(
                session,
                "employee_document.read",
              )}
            />
          </div>
        ) : null}
        {!own && hasPermission(session, "hr_letter.read") ? (
          <div
            id="employee-section-letters"
            className={styles.anchor}
            role="tabpanel"
            aria-label="Letters"
            hidden={activeTab !== "letters"}
          >
            <EmployeeLettersSection
              employeeId={employee.id}
              refreshKey={refresh + packageRefresh}
            />
          </div>
        ) : null}

        {own ? (
          <SectionCard compact title="Record information">
            <InfoGrid>
              <InfoField
                label="Company Employee Code"
                value={<Value value={code} />}
              />
              <InfoField
                label="Record status"
                value={<Value value={employee.status} />}
              />
              <InfoField
                label="Profile photo"
                value={employee.avatarFileId ? "Uploaded" : "Not uploaded"}
              />
            </InfoGrid>
          </SectionCard>
        ) : null}

        {own ? mentionsSection : null}

        {own ? accessSection : null}
      </div>

      {command ? (
        <EmployeeCommandDialog
          kind={command}
          employee={employee}
          branch={branch}
          department={department}
          onClose={() => setCommand(null)}
          onSaved={(message) => {
            setCommand(null);
            setNotice(message);
            setRefresh((value) => value + 1);
          }}
        />
      ) : null}

      <Dialog
        open={avatarOpen}
        title="Update profile photo"
        size="sm"
        busy={avatarBusy}
        onClose={() => {
          if (!avatarBusy) setAvatarOpen(false);
        }}
        footer={
          <>
            <Button
              variant="secondary"
              disabled={avatarBusy}
              onClick={() => setAvatarOpen(false)}
            >
              Cancel
            </Button>
            <Button loading={avatarBusy} onClick={() => void uploadAvatar()}>
              Upload photo
            </Button>
          </>
        }
      >
        <Avatar
          name={employeeName(employee)}
          src={employeeAvatarSrc(employee)}
          size="lg"
        />
        <FileUpload
          id="employee-avatar-file"
          label="Profile photo"
          hint="JPEG, PNG, or WebP image."
          accept="image/jpeg,image/png,image/webp"
          files={avatarFiles}
          busy={avatarBusy}
          error={avatarError || undefined}
          onChange={setAvatarFiles}
        />
      </Dialog>
    </PageContainer>
  );
}
