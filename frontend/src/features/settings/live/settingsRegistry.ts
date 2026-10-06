import type { AccessSession, PreviewRole } from "../../../access";

export type SettingsSectionId =
  | "business-units"
  | "branches"
  | "departments"
  | "designations"
  | "banks"
  | "product-types"
  | "bank-product-mappings"
  | "product-variants"
  | "pipelines"
  | "targets"
  | "financial-rules"
  | "office-timings"
  | "uae-holidays"
  | "audit"
  | "branding"
  | "hr-documents";

export type SettingsSection = {
  id: SettingsSectionId;
  group: string;
  title: string;
  description: string;
  roles: readonly PreviewRole[];
  /** Server permission required to open the section, when its reads require one. */
  requires?: string;
  /** Server permission that enables changes inside the section. */
  manage?: string;
};

const ADMIN: readonly PreviewRole[] = ["Owner", "Managing Director"];

export const SETTINGS_SECTIONS: readonly SettingsSection[] = [
  {
    id: "business-units",
    group: "Organization",
    title: "Business units",
    description: "Business units that group branches",
    roles: ADMIN,
    manage: "organization.write",
  },
  {
    id: "branches",
    group: "Organization",
    title: "Branches",
    description: "Branches and their business unit",
    roles: ADMIN,
    manage: "organization.write",
  },
  {
    id: "departments",
    group: "Organization",
    title: "Departments",
    description: "Departments by branch and their Target product",
    roles: ADMIN,
    manage: "organization.write",
  },
  {
    id: "banks",
    group: "Products and pipelines",
    title: "Banks",
    description: "Partner banks, codes, and logos",
    roles: ADMIN,
    manage: "pipeline.write",
  },
  {
    id: "product-types",
    group: "Products and pipelines",
    title: "Products",
    description: "Product types, codes, and images",
    roles: ADMIN,
    manage: "pipeline.write",
  },
  {
    id: "bank-product-mappings",
    group: "Products and pipelines",
    title: "Bank products",
    description: "Products offered by each bank",
    roles: ADMIN,
    manage: "pipeline.write",
  },
  {
    id: "product-variants",
    group: "Products and pipelines",
    title: "Product variants",
    description: "Variants offered for each bank product",
    roles: ADMIN,
    manage: "pipeline.write",
  },
  {
    id: "pipelines",
    group: "Products and pipelines",
    title: "Pipelines",
    description: "Versioned case stages for each bank product",
    roles: ADMIN,
    manage: "pipeline.write",
  },
  {
    id: "targets",
    group: "Performance and finance",
    title: "Targets",
    description: "Monthly targets by branch, department, and designation",
    roles: ADMIN,
    requires: "target.write",
    manage: "target.write",
  },
  {
    id: "financial-rules",
    group: "Performance and finance",
    title: "Financial rules",
    description: "CC points, PF slabs, and commission by bank and product",
    roles: [...ADMIN, "Finance"],
    requires: "finance.read",
    manage: "finance.write",
  },
  {
    id: "office-timings",
    group: "Calendar and timing",
    title: "Office timings",
    description: "Effective-dated working hours by branch",
    roles: ADMIN,
    requires: "office_timing.write",
    manage: "office_timing.write",
  },
  {
    id: "uae-holidays",
    group: "Calendar and timing",
    title: "UAE holidays",
    description: "Official UAE holidays and certified holiday years",
    roles: ADMIN,
    requires: "target.write",
    manage: "target.write",
  },
  {
    id: "designations",
    group: "Governance and branding",
    title: "User Types and permissions",
    description: "Actions and data scopes for each User Type",
    roles: ADMIN,
    requires: "permissions.read",
    manage: "permissions.write",
  },
  {
    id: "audit",
    group: "Governance and branding",
    title: "Audit",
    description: "Immutable audit events and exports",
    roles: ADMIN,
    requires: "audit.read",
  },
  {
    id: "branding",
    group: "Governance and branding",
    title: "Branding",
    description: "Global profile banner shown on employee profiles",
    roles: ["Owner"],
  },
  {
    id: "hr-documents",
    group: "Governance and branding",
    title: "HR documents",
    description:
      "Company details, letter wording, and required employee documents",
    roles: ["Owner"],
    requires: "hr_settings.write",
    manage: "hr_settings.write",
  },
];

export function authorizedSettings(session: AccessSession | null | undefined) {
  if (!session) return [];
  return SETTINGS_SECTIONS.filter(
    (section) =>
      section.roles.includes(session.designation) &&
      (!section.requires || session.permissions.includes(section.requires)),
  );
}

export function canManageSettings(
  session: AccessSession | null | undefined,
  permission: string,
) {
  return Boolean(session?.permissions.includes(permission));
}
