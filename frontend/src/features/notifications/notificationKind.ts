const KIND_LABELS: Record<string, string> = {
  case: "Case",
  finance: "Finance",
  attendance: "Attendance",
  target: "Target",
  employee: "Employee",
  user: "Account access",
  team: "Team",
  asset: "Asset",
  task: "Task",
  hr_document: "HR document",
};

export function notificationKindLabel(kind: string) {
  return KIND_LABELS[kind.split(".")[0] ?? ""] ?? "Notification";
}
