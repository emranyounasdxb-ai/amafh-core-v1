import { CatalogSettings } from "./CatalogSettings";
import { HolidaySettings, OfficeTimingSettings } from "./CalendarSettings";
import { BrandingSettings } from "./GovernanceSettings";
import { HrDocumentSettings } from "./HrDocumentSettings";
import { PermissionSettings } from "./PermissionSettings";
import {
  BranchSettings,
  BusinessUnitSettings,
  DepartmentSettings,
} from "./OrganizationSettings";
import { PipelineSettings } from "./PipelineSettings";
import type { SettingsSectionId } from "./settingsRegistry";
import { TargetSettings } from "./TargetSettings";

export function SettingsSectionContent({ id }: { id: SettingsSectionId }) {
  switch (id) {
    case "business-units":
      return <BusinessUnitSettings />;
    case "branches":
      return <BranchSettings />;
    case "departments":
      return <DepartmentSettings />;
    case "designations":
      return <PermissionSettings />;
    case "banks":
    case "product-types":
    case "bank-product-mappings":
    case "product-variants":
      return <CatalogSettings key={id} kind={id} />;
    case "pipelines":
      return <PipelineSettings />;
    case "targets":
      return <TargetSettings />;
    case "office-timings":
      return <OfficeTimingSettings />;
    case "uae-holidays":
      return <HolidaySettings />;
    case "branding":
      return <BrandingSettings />;
    case "hr-documents":
      return <HrDocumentSettings />;
    default:
      return null;
  }
}
