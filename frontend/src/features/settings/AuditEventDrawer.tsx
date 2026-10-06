import {
  CompactDate,
  CompactDateTime,
  CompactMonthYear,
  Drawer,
  EmptyValue,
  InfoField,
  InfoGrid,
  MonetaryAmount,
  SectionCard,
  TruncatedText,
  formatFullNumber,
  isDateOnly,
  isDateOnlyField,
  isMoneyField,
  isTimestampField,
} from "../../design-system";
import type { DataRecord, NamedRecord } from "../../app/api/models";
import { useResource } from "../../app/api/useResource";
import {
  EmployeeLabel,
  isUuid,
  readableLabel,
} from "../../app/presentation/labels";
import { clockTime } from "../attendance/live/attendancePresentation";
import { namedLabel } from "../employees/live/employeePresentation";
import {
  codeLabel,
  entityKind,
  eventLabel,
  fieldLabel,
  keyKind,
  moduleLabel,
  payloadEntries,
  recordTypeLabel,
  type AuditEvent,
  type RecordKind,
} from "./auditPresentation";
import styles from "./AuditLog.module.css";

const FALLBACK: Record<RecordKind, string> = {
  person: "Team member",
  case: "Related case",
  customer: "Related customer",
  asset: "Related asset",
  team: "Related team",
  branch: "Related branch",
  department: "Related department",
  designation: "Related designation",
  banks: "Related bank",
  "product-types": "Related product",
  "product-variants": "Related product variant",
};

const LIST_PATH: Partial<Record<RecordKind, string>> = {
  branch: "/branches",
  department: "/departments",
  designation: "/designations",
};

function detailPath(kind: RecordKind, id: string) {
  const safe = encodeURIComponent(id);
  if (kind === "case") return `/cases/${safe}`;
  if (kind === "customer") return `/customers/${safe}`;
  if (kind === "asset") return `/assets/${safe}`;
  if (kind === "team") return `/teams/${safe}`;
  return `/catalog/${kind}/${safe}`;
}

function detailLabel(kind: RecordKind, record: DataRecord | null) {
  if (!record) return "";
  if (kind === "case") return readableLabel(record.internalCaseId, "");
  if (kind === "customer") return readableLabel(record.customerId, "");
  if (kind === "asset")
    return readableLabel(
      (record.asset as DataRecord | undefined)?.assetCode,
      "",
    );
  return readableLabel(record.name, "");
}

function ListLabel({ path, id, fallback }: { path: string; id: string; fallback: string }) {
  const rows = useResource<NamedRecord[]>(path);
  if (!rows.data) return <>{rows.loading ? "Loading…" : fallback}</>;
  const label = namedLabel(rows.data, id);
  return <TruncatedText value={label === "Unavailable" ? fallback : label} />;
}

function DetailLabel({ kind, id }: { kind: RecordKind; id: string }) {
  const record = useResource<DataRecord>(detailPath(kind, id));
  if (!record.data)
    return <>{record.loading && !record.error ? "Loading…" : FALLBACK[kind]}</>;
  return <TruncatedText value={detailLabel(kind, record.data) || FALLBACK[kind]} />;
}

function RecordValue({
  kind,
  id,
  fieldKey,
}: {
  kind: RecordKind;
  id: string;
  fieldKey?: string;
}) {
  if (kind === "person")
    return (
      <EmployeeLabel
        employeeId={id}
        fieldKey={fieldKey}
        fallback={FALLBACK.person}
        showCode
      />
    );
  const list = LIST_PATH[kind];
  if (list) return <ListLabel path={list} id={id} fallback={FALLBACK[kind]} />;
  return <DetailLabel kind={kind} id={id} />;
}

function AuditValue({ fieldKey, value }: { fieldKey: string; value: unknown }) {
  if (value == null || value === "") return <EmptyValue />;
  if (typeof value === "string" && isUuid(value)) {
    const kind = keyKind(fieldKey);
    return kind ? (
      <RecordValue kind={kind} id={value} fieldKey={fieldKey} />
    ) : (
      <>Related record</>
    );
  }
  if (Array.isArray(value)) {
    if (!value.length) return <EmptyValue />;
    if (value.every((item) => isUuid(item)))
      return (
        <>{`${value.length} related ${value.length === 1 ? "record" : "records"}`}</>
      );
    if (value.every((item) => typeof item === "string" || typeof item === "number"))
      return (
        <TruncatedText
          value={value
            .map((item) => codeLabel(fieldKey, String(item)) ?? String(item))
            .join(", ")}
        />
      );
    const names = value
      .map((item) =>
        item && typeof item === "object"
          ? readableLabel((item as DataRecord).name, "")
          : "",
      )
      .filter(Boolean);
    return names.length ? (
      <TruncatedText value={names.join(", ")} />
    ) : (
      <>{`${value.length} ${value.length === 1 ? "item" : "items"}`}</>
    );
  }
  if (typeof value === "object") return <>Recorded details</>;
  if (typeof value === "boolean") return <>{value ? "Yes" : "No"}</>;
  if (isMoneyField(fieldKey)) return <MonetaryAmount compact={false} value={value} align="start" />;
  if (typeof value === "number")
    return <span className="ds-numeric">{formatFullNumber(value)}</span>;
  const text = String(value);
  const code = codeLabel(fieldKey, text);
  if (code) return <TruncatedText value={code} />;
  if (fieldKey === "paymentMonth" && isDateOnly(text))
    return <CompactMonthYear value={text} />;
  if (isDateOnlyField(fieldKey) || isDateOnly(text)) return <CompactDate value={text} />;
  if (isTimestampField(fieldKey) || /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}/.test(text))
    return <CompactDateTime value={text} />;
  if (/^\d{2}:\d{2}(:\d{2})?$/.test(text)) return <>{clockTime(text)}</>;
  return <TruncatedText value={readableLabel(text, "Related record")} />;
}

type ChangeRow = { id: string; before: unknown; after: unknown };

function ChangeTable({ event }: { event: AuditEvent }) {
  const before = payloadEntries(event.before);
  const after = payloadEntries(event.after);
  const keys = [...new Set([...before, ...after].map(([key]) => key))];
  if (!keys.length) return null;
  const beforeMap = new Map(before);
  const afterMap = new Map(after);
  const rows: ChangeRow[] = keys.map((key) => ({
    id: key,
    before: beforeMap.get(key),
    after: afterMap.get(key),
  }));
  const compare = before.length > 0;
  return (
    <SectionCard compact title={compare ? "Before and after" : "Recorded values"}>
      <InfoGrid>
        {rows.map((row) => (
          <InfoField
            key={row.id}
            label={fieldLabel(row.id)}
            value={
              compare ? (
                <span className={styles.change}>
                  <span className={styles.changeLine}>
                    <span className={styles.changeLabel}>Before</span>
                    <AuditValue fieldKey={row.id} value={row.before} />
                  </span>
                  <span className={styles.changeLine}>
                    <span className={styles.changeLabel}>After</span>
                    <AuditValue fieldKey={row.id} value={row.after} />
                  </span>
                </span>
              ) : (
                <AuditValue fieldKey={row.id} value={row.after} />
              )
            }
          />
        ))}
      </InfoGrid>
    </SectionCard>
  );
}

export function AuditEventDrawer({
  event,
  actorLabel,
  onClose,
}: {
  event: AuditEvent | null;
  actorLabel?: string;
  onClose: () => void;
}) {
  const context = event ? payloadEntries(event.context) : [];
  const kind = entityKind(event?.entityType);
  return (
    <Drawer
      open={Boolean(event)}
      size="wide"
      title={event ? eventLabel(event.action) : "Audit event"}
      description="Read-only audit event"
      onClose={onClose}
    >
      {event ? (
        <div className={styles.drawerBody}>
          <SectionCard compact title="Event details">
            <InfoGrid>
              <InfoField label="Event" value={eventLabel(event.action)} />
              <InfoField
                label="Module"
                value={moduleLabel(event.module) || <EmptyValue />}
              />
              <InfoField
                label="Record type"
                value={recordTypeLabel(event.entityType) || <EmptyValue />}
              />
              <InfoField
                label="Related record"
                value={
                  !event.entityId ? (
                    <EmptyValue />
                  ) : kind && isUuid(event.entityId) ? (
                    <RecordValue kind={kind} id={event.entityId} />
                  ) : (
                    "Related record"
                  )
                }
              />
              <InfoField
                label="Actor"
                value={
                  event.actorEmployeeId && actorLabel ? (
                    actorLabel
                  ) : event.actorEmployeeId ? (
                    <EmployeeLabel
                      employeeId={event.actorEmployeeId}
                      fieldKey="actorEmployeeId"
                      showCode
                    />
                  ) : (
                    <EmptyValue />
                  )
                }
              />
              <InfoField
                label="Occurred (Dubai)"
                value={<CompactDateTime value={event.occurredAt} />}
              />
            </InfoGrid>
          </SectionCard>
          <ChangeTable event={event} />
          {context.length ? (
            <SectionCard compact title="Context">
              <InfoGrid>
                {context.map(([key, value]) => (
                  <InfoField
                    key={key}
                    label={fieldLabel(key)}
                    value={<AuditValue fieldKey={key} value={value} />}
                  />
                ))}
              </InfoGrid>
            </SectionCard>
          ) : null}
        </div>
      ) : null}
    </Drawer>
  );
}
