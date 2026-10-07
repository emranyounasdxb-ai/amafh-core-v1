// Only fields backed by an allowlisted full-result sort in the matching API.
const FIELDS: Record<string, Record<string, string>> = {
  "/customers": {
    customerId: "customerId",
    type: "type",
    name: "name",
    nationality: "nationality",
    salaryAed: "salaryAed",
    contactPerson: "contactPerson",
    mobile: "mobile",
    email: "email",
    passportNumber: "passportNumber",
    eidOrTl: "eidOrTl",
    createdAt: "createdAt",
  },
  "/employees": {
    employeeCode: "companyEmployeeCode",
    fullName: "fullName",
    designation: "designation",
    status: "status",
  },
  "/teams": {
    name: "name",
    active: "active",
    branch_id: "branchName",
    department_id: "departmentName",
  },
  "/assets": {
    assetCode: "assetCode",
    category: "category",
    brand: "brand",
    model: "model",
    serialNumber: "serialNumber",
    status: "status",
    createdAt: "createdAt",
  },
  "/attendance": {
    employeeName: "employeeName",
    systemEmployeeCode: "employeeCode",
    attendanceDate: "attendanceDate",
    checkInTime: "checkInTime",
    checkOutTime: "checkOutTime",
    status: "status",
    isLate: "isLate",
  },
  "/tasks": {
    title: "title",
    priority: "priority",
    status: "status",
    dueAt: "dueAt",
    isOverdue: "isOverdue",
  },
  "/audit-events": {
    occurredAt: "occurredAt",
    action: "action",
    module: "module",
    entityType: "entityType",
    actorEmployeeId: "actorEmployeeId",
  },
  "/attendance/imports": {
    batchId: "batchId",
    attendanceDate: "attendanceDate",
    status: "status",
    dataRowCount: "dataRowCount",
    errorCount: "errorCount",
    createdAt: "createdAt",
  },
  "/performance/employees": {
    employeeId: "employeeName",
    createdCaseCount: "createdCaseCount",
    bookedCaseCount: "bookedCaseCount",
    completedCaseCount: "completedCaseCount",
    achievedCCPoints: "achievedCCPoints",
    achievedPFAed: "achievedPFAed",
    targetProgress: "targetProgress",
  },
  "/performance/comparisons": {
    name: "name",
    createdCaseCount: "createdCaseCount",
    bookedCaseCount: "bookedCaseCount",
    completedCaseCount: "completedCaseCount",
    achievedCCPoints: "achievedCCPoints",
    achievedPFAed: "achievedPFAed",
    targetProgress: "targetProgress",
  },
  "/performance/rankings": {
    rank: "rank",
    employeeName: "employeeName",
    achievementPercentage: "achievementPercentage",
    completedCaseCount: "completedCaseCount",
  },
  "/performance/coordinator-workload": {
    employeeId: "employeeName",
    handledCases: "handledCases",
    submittedBookedCases: "submittedBookedCases",
    stageUpdatedCases: "stageUpdatedCases",
  },
  "/finance/rules": {
    id: "id",
    effective_date: "effectiveDate",
    cc_points: "ccPoints",
    commission_aed: "commissionAed",
    active: "active",
  },
  "/finance/completed-cases": {
    internal_case_id: "internalCaseId",
    product_code: "productCode",
    completed_at: "completedAt",
    cc_points: "ccPoints",
    commission_aed: "commissionAed",
  },
  "/finance/wallets": {
    employee_id: "employeeName",
    balance_points: "balancePoints",
  },
  "/finance/clawbacks": {
    internal_case_id: "internalCaseId",
    amount_aed: "amountAed",
    clawback_date: "clawbackDate",
    reason: "reason",
  },
  "/finance/payments": {
    employee_id: "employeeName",
    payment_type: "paymentType",
    amount_aed: "amountAed",
    payment_month: "paymentMonth",
    payment_date: "paymentDate",
  },
  "/targets": {
    effectiveDate: "effectiveDate",
    targetPoints: "targetPoints",
    targetAmountAed: "targetAmountAed",
    active: "active",
  },
  "/office-timings": {
    effectiveDate: "effectiveDate",
    branchId: "branchId",
    startTime: "startTime",
    endTime: "endTime",
  },
  "/pipelines": { id: "id", effective_date: "effectiveDate", active: "active" },
  "/performance/uae-holidays": {
    holidayDate: "holidayDate",
    name: "name",
    sourceReference: "sourceReference",
  },
  "/catalog/banks": { name: "name", bank_code: "code", active: "active" },
  "/catalog/product-types": { name: "name", active: "active" },
  "/catalog/bank-product-mappings": {
    bank_id: "bankId",
    product_type_id: "productTypeId",
    active: "active",
  },
  "/catalog/product-variants": {
    name: "name",
    active: "active",
    minimum_salary_aed: "minimum_salary_aed",
    maximum_salary_aed: "maximum_salary_aed",
  },
};

export function serverSortField(
  path: string,
  columnId: string,
): string | undefined {
  const base = path.split("?")[0];
  if (/^\/performance\/teams\/[^/]+$/.test(base))
    return FIELDS["/performance/employees"]?.[columnId];
  if (/^\/attendance\/imports\/[^/]+\/rows$/.test(base))
    return [
      "rowNumber",
      "status",
      "errorCode",
      "columnName",
      "errorDetail",
    ].includes(columnId)
      ? columnId
      : undefined;
  return FIELDS[base]?.[columnId];
}
