import type { StatusTone } from "../../../design-system";
import type { DataRecord } from "../../../app/api/models";
import { isUuid, readableLabel } from "../../../app/presentation/labels";

export const REOPENED_BY_OWNER = "Case Reopened by Owner";

export type PipelineStage = {
  name: string;
  stage_order?: number;
  stageOrder?: number;
  is_final?: boolean;
  isFinal?: boolean;
};

export type CaseHistoryEvent = {
  id: string;
  time: string;
  title: string;
  description?: string;
  actorId?: string;
  tone?: StatusTone;
};

export function caseStatusTone(status: string, voided?: boolean): StatusTone {
  if (voided) return "neutral";
  if (status === "Completed") return "success";
  if (status === "Rejected") return "danger";
  if (status === "Pending for Approval") return "warning";
  if (status === REOPENED_BY_OWNER) return "warning";
  if (status === "Approved" || status === "Booked") return "info";
  return "neutral";
}

export function displayOrFallback(
  value: string | null | undefined,
  fallback: string,
) {
  const text = String(value ?? "").trim();
  if (!text || text === "—" || isUuid(text)) return fallback;
  return text;
}

function eventTime(event: DataRecord) {
  const raw =
    event.occurred_at ||
    event.approved_at ||
    event.started_at ||
    event.ended_at;
  return typeof raw === "string" ? raw : "";
}

function contextRecord(event: DataRecord) {
  const raw = event.context;
  if (!raw) return null;
  if (typeof raw === "string") {
    try {
      const parsed = JSON.parse(raw);
      return parsed && typeof parsed === "object"
        ? (parsed as Record<string, unknown>)
        : null;
    } catch {
      return null;
    }
  }
  return typeof raw === "object" ? (raw as Record<string, unknown>) : null;
}

function contextReason(event: DataRecord) {
  const context = contextRecord(event);
  const reason = context?.reason;
  return typeof reason === "string" ? reason.trim() : "";
}

function lifecycleTitle(event: DataRecord) {
  const status = readableLabel(event.status, "");
  const previous = readableLabel(event.previous_status, "");
  const context = contextRecord(event);
  if (context?.ownerReopen) return "Case reopened";
  if (context?.ownerCorrection) return "Case corrected";
  if (context?.ownerTransfer) return "Case Owner transferred";
  if (!previous && status === "Pending for Approval") return "Case created";
  if (status === REOPENED_BY_OWNER) return "Case reopened";
  if (status === "Completed") return "Case completed";
  if (status === "Rejected") return "Case rejected";
  if (status === "Approved") return "Status updated";
  if (status === "Pending for Approval" && previous)
    return "Returned for approval";
  return status ? "Status updated" : "Lifecycle event";
}

export function isPlaceholderLabel(value: string) {
  return [
    "",
    "—",
    "Unavailable",
    "Loading…",
    "Not assigned",
    "Not recorded",
    "Not available",
    "Related record",
    "Assigned employee",
    "Team member",
  ].includes(value.trim());
}

export function caseHistoryItems(
  history: Record<string, DataRecord[]> | null,
): CaseHistoryEvent[] {
  if (!history) return [];
  const items: CaseHistoryEvent[] = [];
  const lifecycle = history.lifecycle ?? [];
  lifecycle.forEach((event, index) => {
    const status = readableLabel(event.status, "");
    const previous = readableLabel(event.previous_status, "");
    const reason = contextReason(event);
    const description = [
      previous && status && previous !== status
        ? `${previous} to ${status}`
        : status && !previous
          ? status
          : "",
      reason,
    ]
      .filter(Boolean)
      .join(" · ");
    items.push({
      id: `lifecycle-${index}`,
      time: eventTime(event),
      title: lifecycleTitle(event),
      description: description || undefined,
      actorId:
        typeof event.actor_employee_id === "string"
          ? event.actor_employee_id
          : undefined,
      tone:
        status === "Rejected"
          ? "danger"
          : status === "Completed"
            ? "success"
            : status === REOPENED_BY_OWNER
              ? "warning"
              : "info",
    });
  });
  (history.ownership ?? []).forEach((event, index) => {
    items.push({
      id: `ownership-${index}`,
      time: eventTime(event),
      title: "Case Owner assigned",
      actorId:
        typeof event.changed_by_employee_id === "string"
          ? event.changed_by_employee_id
          : undefined,
      tone: "neutral",
    });
  });
  (history.stages ?? []).forEach((event, index) => {
    const stage = readableLabel(event.stage, "");
    const previous = readableLabel(history.stages?.[index - 1]?.stage, "");
    const remark = readableLabel(event.remark, "");
    const imported = Boolean(
      event.csv_import_batch_id || event.csvImportBatchId,
    );
    items.push({
      id: `stages-${index}`,
      time: eventTime(event),
      title: "Pipeline stage updated",
      description:
        [
          previous && stage && previous !== stage
            ? `${previous} to ${stage}`
            : stage,
          remark,
          imported ? "Bank Stage Updates" : "",
        ]
          .filter(Boolean)
          .join(" · ") || undefined,
      actorId:
        typeof event.updated_by_employee_id === "string"
          ? event.updated_by_employee_id
          : typeof event.updatedByEmployeeId === "string"
            ? event.updatedByEmployeeId
            : undefined,
      tone: "brand",
    });
  });
  (history.approvals ?? []).forEach((event, index) => {
    items.push({
      id: `approvals-${index}`,
      time: eventTime(event),
      title: "Case approved",
      description: "Coordinator assigned",
      actorId:
        typeof event.approved_by_employee_id === "string"
          ? event.approved_by_employee_id
          : undefined,
      tone: "success",
    });
  });
  return items
    .filter((item) => item.time)
    .sort((left, right) => left.time.localeCompare(right.time));
}

export function pipelineStageItems(
  stages: PipelineStage[],
  currentStage: string | null,
  status: string,
  voided: boolean,
) {
  const ordered = [...stages].sort((left, right) => {
    const a = left.stageOrder ?? left.stage_order ?? 0;
    const b = right.stageOrder ?? right.stage_order ?? 0;
    return a - b;
  });
  const currentIndex = ordered.findIndex(
    (stage) => stage.name === currentStage,
  );
  const rejected = status === "Rejected";
  const completed = status === "Completed";
  const reopened = currentStage === REOPENED_BY_OWNER || status === REOPENED_BY_OWNER;
  return ordered.map((stage, index) => {
    let stageStatus: "completed" | "current" | "upcoming" | "rejected" | "locked" =
      "upcoming";
    if (voided || reopened) stageStatus = "locked";
    else if (currentIndex < 0) stageStatus = "upcoming";
    else if (index < currentIndex) stageStatus = "completed";
    else if (index === currentIndex) {
      if (rejected) stageStatus = "rejected";
      else if (completed) stageStatus = "completed";
      else stageStatus = "current";
    } else stageStatus = "upcoming";
    return {
      id: `${index}-${stage.name}`,
      title: stage.name,
      status: stageStatus,
    };
  });
}
