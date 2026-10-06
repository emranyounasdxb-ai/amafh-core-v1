export type Page<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};
export type NamedRecord = {
  id: string;
  name: string;
  active?: boolean;
  code?: string;
  bank_id?: string;
  product_type_id?: string;
  branch_id?: string;
};
export type EmployeeSummary = {
  id: string;
  employeeCode: string;
  fullName: string;
  designation: string;
  status: string;
  branchId: string | null;
  departmentId: string | null;
};
export type CaseRecord = {
  id: string;
  internalCaseId: string;
  customerId: string;
  bankId: string;
  productTypeId: string;
  productVariantId: string | null;
  pipelineConfigurationId: string;
  requestedPfAmount: string | null;
  ownerEmployeeId: string;
  coordinatorEmployeeId: string | null;
  createdByEmployeeId: string;
  branchId: string;
  departmentId: string;
  status: string;
  currentStage: string | null;
  bankCaseNumber: string | null;
  createdAt: string;
  updatedAt?: string | null;
  finalizedAt?: string | null;
  administrativelyVoidedAt: string | null;
  administrativelyVoidedByEmployeeId?: string | null;
  administrativeVoidReason?: string | null;
};
export type DataRecord = Record<string, unknown>;
