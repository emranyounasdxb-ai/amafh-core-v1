const DATE_ONLY_FIELDS = new Set([
  "attendanceDate",
  "clawbackDate",
  "effectiveDate",
  "effective_date",
  "endDate",
  "holidayDate",
  "issueDate",
  "issuedDate",
  "joiningDate",
  "paymentDate",
  "startDate",
]);

const TIMESTAMP_FIELDS = new Set([
  "administrativelyVoidedAt",
  "approvedAt",
  "approved_at",
  "archivedAt",
  "archived_at",
  "completedAt",
  "completed_at",
  "createdAt",
  "created_at",
  "dueAt",
  "finalizedAt",
  "occurredAt",
  "occurred_at",
  "startedAt",
  "started_at",
  "updatedAt",
  "updated_at",
  "uploadedAt",
  "uploaded_at",
]);

export function isDateOnlyField(key: string) {
  return DATE_ONLY_FIELDS.has(key);
}

export function isTimestampField(key: string) {
  return TIMESTAMP_FIELDS.has(key);
}

export function isRecordDateField(key: string) {
  return isDateOnlyField(key) || isTimestampField(key);
}
