import type { ReactNode } from "react";
import {
  Button,
  CompactAmount,
  CompactNumber,
  MetricValue,
  ProfileBanner,
  ProfileBannerActions,
  ProfileBannerIdentity,
  ProfileBannerMetadata,
  ProfileBannerPrimaryAction,
  ProfileBannerSecondaryAction,
  ProfileBannerStats,
  ProfileCoverBanner,
  SectionCard,
} from "../index";

const metadata = [
  {
    id: "branch",
    label: "Branch",
    value: "North operations",
    icon: "branch" as const,
  },
  {
    id: "dept",
    label: "Department",
    value: "Sales",
    icon: "department" as const,
  },
  {
    id: "manager",
    label: "Reporting manager",
    value: "M. Khalid",
    icon: "user" as const,
  },
  { id: "team", label: "Team", value: "Harbour desk", icon: "team" as const },
  {
    id: "joined",
    label: "Joining date",
    value: "12 Mar 2021",
    icon: "calendar" as const,
  },
  {
    id: "mail",
    label: "Email",
    value: "arahman@amafh.example",
    icon: "mail" as const,
  },
  {
    id: "phone",
    label: "Phone",
    value: "+971 50 000 1182",
    icon: "phone" as const,
  },
  {
    id: "assignment",
    label: "Current assignment",
    value: "Harbour desk coverage",
    icon: "cases" as const,
  },
];

const employeeActions = (
  <ProfileBannerActions
    onBack={() => undefined}
    primary={
      <ProfileBannerPrimaryAction>View profile</ProfileBannerPrimaryAction>
    }
    secondary={
      <ProfileBannerSecondaryAction>Message</ProfileBannerSecondaryAction>
    }
    overflow={[
      { id: "assign", label: "Assign" },
      {
        id: "disable",
        label: "Deactivate",
        danger: true,
        separator: true,
      },
    ]}
  />
);

function CoverExample({
  editAvatar,
  actions,
}: {
  editAvatar?: boolean;
  actions?: ReactNode;
}) {
  return (
    <ProfileCoverBanner
      identity={
        <ProfileBannerIdentity
          name="A. Rahman"
          designation="Operations manager"
          code="EMP-1182"
          status="Active"
          contextLabel="Employee profile"
          onEditAvatar={editAvatar ? () => undefined : undefined}
        />
      }
      metadata={<ProfileBannerMetadata items={metadata} />}
      actions={actions}
    />
  );
}

function WidthFrame({
  width,
  caption,
  children,
}: {
  width: "1080" | "960" | "768" | "640";
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

export function ProfileBannerSection() {
  return (
    <section id="profile-banner" className="ds-stack-20">
      <SectionCard
        title="Profile banners"
        description="The branded cover banner is the recommended identity header for employee, Attendance, and Performance. Pages supply records and actions. The white variant remains only as a compact contextual option."
      >
        <strong>Branded employee profile</strong>
        <CoverExample editAvatar actions={employeeActions} />
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
          stats={
            <ProfileBannerStats
              items={[
                {
                  id: "assignment",
                  label: "Assignment",
                  value: "Harbour desk",
                },
                { id: "team", label: "Team", value: "North ops" },
                { id: "status", label: "Status", value: "Active" },
                { id: "joined", label: "Joined", value: "12 Mar 2021" },
              ]}
            />
          }
          actions={employeeActions}
        />
        <strong>Cover container widths</strong>
        <WidthFrame
          width="1080"
          caption="~1080px · identity left, equal-height actions right"
        >
          <CoverExample editAvatar actions={employeeActions} />
        </WidthFrame>
        <WidthFrame
          width="960"
          caption="~960px · identity keeps space; actions stay one group"
        >
          <CoverExample editAvatar actions={employeeActions} />
        </WidthFrame>
        <WidthFrame
          width="768"
          caption="Medium · actions wrap as a complete second row"
        >
          <CoverExample editAvatar actions={employeeActions} />
        </WidthFrame>
        <WidthFrame
          width="640"
          caption="Narrow · avatar and identity stay aligned; actions wrap"
        >
          <CoverExample editAvatar actions={employeeActions} />
        </WidthFrame>
        <strong>Attendance profile context</strong>
        <ProfileCoverBanner
          identity={
            <ProfileBannerIdentity
              name="A. Rahman"
              designation="Operations manager"
              code="EMP-1182"
              status="Active"
              contextLabel="Attendance"
            />
          }
          stats={
            <ProfileBannerStats
              items={[
                { id: "present", label: "Present", value: "18" },
                { id: "late", label: "Late", value: "3" },
                { id: "leave", label: "Leave", value: "1" },
                {
                  id: "pct",
                  label: "Attendance",
                  value: <MetricValue value={94} kind="percent" />,
                },
              ]}
            />
          }
        />
        <strong>Performance profile context</strong>
        <ProfileCoverBanner
          identity={
            <ProfileBannerIdentity
              name="A. Rahman"
              designation="Operations manager"
              code="EMP-1182"
              status="Active"
              contextLabel="Performance"
            />
          }
          stats={
            <ProfileBannerStats
              items={[
                {
                  id: "cases",
                  label: "Cases",
                  value: <CompactNumber value={128} />,
                },
                {
                  id: "ach",
                  label: "Target",
                  value: <MetricValue value={91} kind="percent" />,
                },
                {
                  id: "points",
                  label: "Points",
                  value: <CompactAmount value={1_250_000} currency="AED" />,
                },
                { id: "rank", label: "Ranking", value: "#4" },
              ]}
            />
          }
        />
        <strong>Compact profile banner</strong>
        <ProfileCoverBanner
          compact
          identity={
            <ProfileBannerIdentity
              name="A. Rahman"
              designation="Operations manager"
              code="EMP-1182"
              status="Active"
              contextLabel="Employee profile"
            />
          }
          actions={
            <ProfileBannerActions
              primary={<Button size="compact">Edit</Button>}
            />
          }
        />
        <strong>Missing avatar</strong>
        <ProfileCoverBanner
          identity={
            <ProfileBannerIdentity
              name="L. Noor"
              designation="Assigned employee"
              code="EMP-2204"
              status="Active"
              contextLabel="Employee profile"
            />
          }
          metadata={<ProfileBannerMetadata items={metadata.slice(0, 4)} />}
        />
        <strong>Long employee name</strong>
        <ProfileCoverBanner
          identity={
            <ProfileBannerIdentity
              name="Hanan Abdullah Mohammed Al Suwaidi"
              designation="Coordinator"
              code="EMP-2048"
              status="Active"
              contextLabel="Employee profile"
            />
          }
        />
        <strong>Inactive employee</strong>
        <ProfileCoverBanner
          identity={
            <ProfileBannerIdentity
              name="Harbour Desk"
              designation="Coordinator"
              code="EMP-2210"
              status="Inactive"
              statusTone="neutral"
              contextLabel="Employee profile"
            />
          }
        />
        <strong>Banner with actions</strong>
        <ProfileCoverBanner
          identity={
            <ProfileBannerIdentity
              name="A. Rahman"
              designation="Operations manager"
              code="EMP-1182"
              status="Active"
              contextLabel="Employee profile"
            />
          }
          metadata={<ProfileBannerMetadata items={metadata.slice(0, 6)} />}
          actions={employeeActions}
        />
        <strong>Optional compact white variant</strong>
        <ProfileBanner
          compact
          identity={
            <ProfileBannerIdentity
              name="A. Rahman"
              designation="Operations manager"
              code="EMP-1182"
              status="Active"
            />
          }
          actions={
            <ProfileBannerActions
              primary={<Button size="compact">Open</Button>}
            />
          }
        />
        <strong>Narrow responsive layout</strong>
        <div className="ds-narrow-frame">
          <CoverExample actions={employeeActions} />
        </div>
      </SectionCard>
    </section>
  );
}
