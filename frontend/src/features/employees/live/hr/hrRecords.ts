import type { StatusTone } from "../../../../design-system";
import { ApiFailure } from "../../../../app/api/http";

export type PackageVersion = {
  id: string;
  effectiveDate: string;
  basicSalaryAed: string;
  housingAllowanceAed: string | null;
  transportAllowanceAed: string | null;
  otherAllowanceLabel: string | null;
  otherAllowanceAed: string | null;
  totalMonthlyAed: string;
  changeReason: string;
  createdByName: string | null;
  createdAt: string;
};

export type PackageList = {
  current: PackageVersion | null;
  upcoming: PackageVersion[];
  history: PackageVersion[];
  canManage: boolean;
};

export type FieldMode = "required" | "optional" | "none";

export type DocumentType = {
  id: string;
  code: string;
  name: string;
  requiredAtOnboarding: boolean;
  numberMode: FieldMode;
  issueDateMode: FieldMode;
  expiryDateMode: FieldMode;
  countryMode: FieldMode;
};

export type DocumentVersion = {
  id: string;
  version: number;
  status: "Current" | "Superseded" | "Withdrawn";
  documentNumber: string | null;
  issueDate: string | null;
  expiryDate: string | null;
  expired: boolean;
  issuingCountry: string | null;
  notes: string | null;
  originalFilename: string;
  contentType: string;
  byteSize: number;
  uploadedByName: string | null;
  uploadedAt: string;
  supersededAt: string | null;
  withdrawnByName: string | null;
  withdrawnAt: string | null;
  withdrawalReason: string | null;
};

export type DocumentSeries = {
  seriesId: string;
  typeId: string;
  typeName: string;
  status: DocumentVersion["status"];
  latest: DocumentVersion;
  versions: DocumentVersion[];
};

export type DocumentList = {
  checklist: { typeId: string; typeName: string; satisfied: boolean }[];
  missingRequired: number;
  documents: DocumentSeries[];
  types: DocumentType[];
  canUpload: boolean;
  canWithdraw: boolean;
};

export type VisaStatus =
  | "Draft"
  | "In Progress"
  | "Active"
  | "Renewal In Progress"
  | "Cancellation In Progress"
  | "Cancelled";

export type VisaRecord = {
  id: string;
  visaType: string;
  sponsor: string;
  visaNumber: string | null;
  fileNumber: string | null;
  issueDate: string | null;
  expiryDate: string | null;
  workPermitNumber: string | null;
  workPermitExpiryDate: string | null;
  medicalFitnessDate: string | null;
  insuranceExpiryDate: string | null;
  notes: string | null;
  status: VisaStatus;
  expired: boolean;
  workPermitExpired: boolean;
  allowedTransitions: VisaStatus[];
  createdByName: string | null;
  createdAt: string;
  updatedByName: string | null;
  updatedAt: string;
  documents: {
    linkId: string;
    documentId: string;
    seriesId: string;
    typeName: string;
    version: number;
    documentStatus: DocumentVersion["status"];
    originalFilename: string;
    attachedByName: string | null;
    attachedAt: string;
  }[];
  events: {
    id: string;
    eventType: string;
    fromStatus: VisaStatus | null;
    toStatus: VisaStatus | null;
    changes: Record<string, unknown> | null;
    note: string | null;
    actorName: string | null;
    occurredAt: string;
  }[];
};

export type VisaList = {
  current: VisaRecord | null;
  history: VisaRecord[];
  canManage: boolean;
};

export type HrDocumentStatus =
  | "Prepared"
  | "Pending Approval"
  | "Issued"
  | "Voided"
  | "Cancelled";

export type HrDocumentItem = {
  id: string;
  documentType: string;
  label: string;
  status: HrDocumentStatus;
  requiresApproval: boolean;
  addressee: string | null;
  purpose: string | null;
  nocPurpose: string | null;
  documentNumber: string | null;
  preparedByName: string | null;
  preparedAt: string;
  approvedByName: string | null;
  approvedAt: string | null;
  issuedByName: string | null;
  issuedAt: string | null;
  voidedByName: string | null;
  voidedAt: string | null;
  voidReason: string | null;
  cancelledByName: string | null;
  cancelledAt: string | null;
  cancelReason: string | null;
  reissueOfNumber: string | null;
};

export type HrDocumentList = {
  items: HrDocumentItem[];
  eligibleTypes: {
    documentType: string;
    label: string;
    requiresApproval: boolean;
    issuanceBlockers: string[];
  }[];
  canPrepare: boolean;
  canApprove: boolean;
  canVoid: boolean;
};

export type HrTemplate = {
  id: string;
  version: number;
  title: string;
  body: string;
  status: "Draft" | "Approved" | "Retired";
  createdByName: string | null;
  createdAt: string;
  approvedByName: string | null;
  approvedAt: string | null;
  retiredAt: string | null;
};

export type HrDocumentSettings = {
  company: {
    companyLegalName: string | null;
    companyAddress: string | null;
    tradeLicenseNumber: string | null;
    signatoryName: string | null;
    signatoryDesignation: string | null;
    updatedByName: string | null;
    updatedAt: string | null;
  };
  missingCompanyDetails: string[];
  templates: {
    documentType: string;
    label: string;
    requiresApproval: boolean;
    approved: HrTemplate | null;
    latest: HrTemplate | null;
    versions: HrTemplate[];
  }[];
  placeholders: { key: string; description: string; salary: boolean }[];
  canManage: boolean;
};

export const DOCUMENT_ACCEPT = "application/pdf,image/jpeg,image/png";
export const DOCUMENT_MAX_BYTES = 5_000_000;

export const VISA_TYPES = [
  "Employment",
  "Investor/Partner",
  "Family-sponsored",
  "Other",
];

export function failureMessage(failure: unknown) {
  if (failure instanceof ApiFailure) return failure.message;
  return "The request could not be completed. Retry safely when the connection returns.";
}

export function documentStatusTone(status: string): StatusTone {
  if (status === "Current") return "success";
  if (status === "Withdrawn") return "danger";
  return "neutral";
}

export function visaStatusTone(status: string): StatusTone {
  if (status === "Active") return "success";
  if (status === "Cancelled") return "neutral";
  if (status === "Draft") return "neutral";
  return "info";
}

export function hrDocumentStatusTone(status: string): StatusTone {
  if (status === "Issued") return "success";
  if (status === "Pending Approval") return "warning";
  if (status === "Voided") return "danger";
  if (status === "Prepared") return "info";
  return "neutral";
}

export function fileSizeLabel(bytes: number) {
  return `${Math.max(1, Math.ceil(bytes / 1000)).toLocaleString("en-US")} KB`;
}
