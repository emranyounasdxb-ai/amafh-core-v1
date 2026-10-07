import { useEffect, useMemo, useRef, useState } from "react";
import {
  ActivityTimeline,
  Banner,
  Button,
  Checkbox,
  ConfirmationDialog,
  CountedTextArea,
  DestructiveConfirmationDialog,
  Dialog,
  DropdownSelect,
  EmptyState,
  ErrorState,
  FormField,
  HorizontalStageTracker,
  InfoField,
  InfoGrid,
  InlineNotice,
  LoadingState,
  NotFoundState,
  OfflineState,
  OverflowMenu,
  PageContainer,
  PermissionDeniedState,
  PersonSelect,
  RecordActions,
  RecordDetailHeader,
  RelatedRecordList,
  RetryState,
  SectionCard,
  StatusBadge,
  TextInput,
  CompactDateTime,
  MonetaryAmount,
  TruncatedText,
  UnavailableState,
  type MenuItem,
  type PersonOption,
  type RelatedRecordItem,
  type SelectOption,
} from "../../../design-system";
import { canApproveCases, canBookCases } from "../../../access";
import { choices } from "../../../app/api/choices";
import { ApiFailure } from "../../../app/api/http";
import { useResource } from "../../../app/api/useResource";
import type {
  CaseRecord,
  DataRecord,
  EmployeeSummary,
} from "../../../app/api/models";
import { EmployeeLabel } from "../../../app/presentation/labels";
import { useSession } from "../../../app/session/useSession";
import {
  REOPENED_BY_OWNER,
  caseHistoryItems,
  caseStatusTone,
  displayOrFallback,
  isPlaceholderLabel,
  pipelineStageItems,
  type PipelineStage,
} from "./caseDetailPresentation";
import { useCaseLabels } from "./useCaseLabels";
import styles from "./CaseDetailPage.module.css";
import { recordImageSrc } from "../../../app/api/recordImages";
import { RecordImageLabel } from "../../../shared/media/RecordImage";

type DialogKind =
  "approval" | "booking" | "correction" | "reopen" | "void" | "";

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function FieldValue({
  value,
  fallback,
  onOpen,
}: {
  value: string | null | undefined;
  fallback: string;
  onOpen?: () => void;
}) {
  const text = displayOrFallback(value, fallback);
  const available = !isPlaceholderLabel(text);
  if (onOpen && available) {
    return (
      <Button variant="ghost" size="compact" onClick={onOpen}>
        <TruncatedText value={text} />
      </Button>
    );
  }
  return (
    <span className={styles.fieldValue}>
      <TruncatedText value={text} />
    </span>
  );
}

export function CaseDetailPage({
  id,
  back,
  openCustomer,
  openEmployee,
}: {
  id: string;
  back: () => void;
  openCustomer?: (id: string) => void;
  openEmployee?: (id: string) => void;
}) {
  const { api, session } = useSession();
  const record = useResource<CaseRecord>(`/cases/${encodeURIComponent(id)}`);
  const history = useResource<Record<string, DataRecord[]>>(
    record.data ? `/cases/${encodeURIComponent(id)}/history` : null,
  );
  const label = useCaseLabels(
    useMemo(() => (record.data ? [record.data] : []), [record.data]),
  );
  const item = record.data;
  const pipeline = useResource<{ stages: PipelineStage[] }>(
    item ? `/pipelines/${item.pipelineConfigurationId}` : null,
  );
  const [owners, setOwners] = useState<EmployeeSummary[]>([]);
  const [coordinators, setCoordinators] = useState<EmployeeSummary[]>([]);
  const [coordinator, setCoordinator] = useState("");
  const [bankRef, setBankRef] = useState("");
  const [dialog, setDialog] = useState<DialogKind>("");
  const [reason, setReason] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [correction, setCorrection] = useState("");
  const [correctionField, setCorrectionField] = useState("bankCaseNumber");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [busy, setBusy] = useState(false);
  const [choicesError, setChoicesError] = useState("");
  const replay = useRef({ payload: "", key: "" });

  useEffect(() => {
    if (!item || !session || !canApproveCases(session)) return;
    const controller = new AbortController();
    choices<EmployeeSummary>(api, "/employee-labels?status=Active", controller.signal)
      .then((rows) => {
        setOwners(
          rows.filter((person) =>
            [
              "Sales Manager",
              "Coordinator",
              "Team Leader",
              "Sales Executive",
            ].includes(person.designation),
          ),
        );
        setCoordinators(
          rows.filter(
            (person) =>
              person.designation === "Coordinator" &&
              person.branchId === item.branchId &&
              person.departmentId === item.departmentId,
          ),
        );
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setChoicesError(
            failure instanceof Error
              ? failure.message
              : "Coordinator choices unavailable",
          );
      });
    return () => controller.abort();
  }, [api, item, session]);

  const command = async (name: string, body: DataRecord) => {
    const payload = JSON.stringify(body);
    if (replay.current.payload !== name + payload)
      replay.current = { payload: name + payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    setSuccess("");
    try {
      await api.request(`/cases/${id}/${name}`, {
        method: "POST",
        body: payload,
        headers: { "Idempotency-Key": replay.current.key },
      });
      record.reload();
      history.reload();
      setDialog("");
      setReason("");
      setConfirmed(false);
      setCorrection("");
      setSuccess("The last authorized command completed.");
    } catch (failure) {
      setError(
        failure instanceof ApiFailure
          ? [
              failure.message,
              ...Object.entries(failure.fieldErrors).map(
                ([key, messages]) => `${key}: ${messages.join(" ")}`,
              ),
            ].join(" · ")
          : "Request failed. You may safely retry.",
      );
    } finally {
      setBusy(false);
    }
  };

  const closeDialog = () => {
    if (busy) return;
    setDialog("");
    setReason("");
    setConfirmed(false);
    setCorrection("");
  };

  const openDialog = (kind: DialogKind) => {
    setError("");
    setSuccess("");
    setReason("");
    setConfirmed(false);
    setCorrection("");
    setDialog(kind);
  };

  if (!session) return null;

  if (record.denied) {
    const missing =
      record.error.toLowerCase().includes("unavailable") ||
      record.error.toLowerCase().includes("not found");
    return (
      <PageContainer>
        {missing ? (
          <NotFoundState
            title="Case unavailable"
            description="This Case is not available in the current authorized scope."
            action={
              <Button variant="secondary" onClick={back}>
                Back to Cases
              </Button>
            }
          />
        ) : (
          <PermissionDeniedState />
        )}
      </PageContainer>
    );
  }

  if (record.error && !item) {
    return (
      <PageContainer>
        {isOffline(record.error) ? (
          <OfflineState />
        ) : (
          <ErrorState description={record.error} retry={record.reload} />
        )}
      </PageContainer>
    );
  }

  if (record.loading && !item) {
    return (
      <PageContainer>
        <LoadingState title="Loading Case" />
      </PageContainer>
    );
  }

  if (!item) {
    return (
      <PageContainer>
        <UnavailableState title="Record unavailable" />
      </PageContainer>
    );
  }

  const voided = Boolean(item.administrativelyVoidedAt);
  const canApprove =
    canApproveCases(session) &&
    item.status === "Pending for Approval" &&
    !voided;
  const canBook =
    canBookCases(session) &&
    item.status === "Approved" &&
    !voided &&
    (["Owner", "Managing Director"].includes(session.designation) ||
      item.coordinatorEmployeeId === session.employeeId);
  const ownerControls = session.designation === "Owner" && !voided;
  const canReopen = ["Completed", "Rejected"].includes(item.status);
  const customerName = label(item.customerId);
  const productName = label(item.productTypeId);
  const bankName = label(item.bankId);
  const variantName = item.requestedPfAmount
    ? item.requestedPfAmount
    : label(item.productVariantId);
  const ownerName = label(item.ownerEmployeeId);
  const coordinatorName = label(item.coordinatorEmployeeId);
  const createdByName = label(item.createdByEmployeeId);
  const branchName = label(item.branchId);
  const departmentName = label(item.departmentId);
  const timeline = caseHistoryItems(history.data);
  const stages = pipeline.data?.stages ?? [];
  const stageItems = pipelineStageItems(
    stages,
    item.currentStage,
    item.status,
    voided,
  );
  const coordinatorOptions: PersonOption[] = coordinators.map((person) => ({
    value: person.id,
    name: person.fullName,
    subtitle: person.employeeCode,
    src: recordImageSrc("employee", person),
  }));
  const ownerOptions: PersonOption[] = owners.map((person) => ({
    value: person.id,
    name: person.fullName,
    subtitle: person.employeeCode,
    src: recordImageSrc("employee", person),
  }));
  const stageOptions: SelectOption[] = stages.map((stage) => ({
    value: stage.name,
    label: stage.name,
  }));
  const subtitle = [
    displayOrFallback(customerName, "Customer unavailable"),
    displayOrFallback(productName, "Product unavailable"),
    displayOrFallback(item.currentStage, ""),
    displayOrFallback(branchName, ""),
    displayOrFallback(departmentName, ""),
  ]
    .filter(
      (part) =>
        (part && !isPlaceholderLabel(part)) || part.endsWith("unavailable"),
    )
    .filter(Boolean)
    .join(" · ");
  const related: RelatedRecordItem[] = [
    {
      id: "customer",
      title: displayOrFallback(customerName, "Related record"),
      meta: "Customer",
      onOpen:
        openCustomer && !isPlaceholderLabel(displayOrFallback(customerName, ""))
          ? () => openCustomer(item.customerId)
          : undefined,
    },
    {
      id: "owner",
      title: displayOrFallback(ownerName, "Assigned employee"),
      meta: "Case Owner",
      onOpen:
        openEmployee && !isPlaceholderLabel(displayOrFallback(ownerName, ""))
          ? () => openEmployee(item.ownerEmployeeId)
          : undefined,
    },
    ...(item.coordinatorEmployeeId
      ? [
          {
            id: "coordinator",
            title: displayOrFallback(coordinatorName, "Assigned employee"),
            meta: "Coordinator",
            onOpen:
              openEmployee &&
              !isPlaceholderLabel(displayOrFallback(coordinatorName, ""))
                ? () => openEmployee(item.coordinatorEmployeeId!)
                : undefined,
          } satisfies RelatedRecordItem,
        ]
      : []),
  ];

  const primaryAction = canApprove
    ? {
        label: "Approve and assign",
        onClick: () => openDialog("approval"),
      }
    : canBook
      ? {
          label: "Record Bank Case Number",
          onClick: () => {
            setBankRef("");
            openDialog("booking");
          },
        }
      : null;

  const overflowItems: MenuItem[] = ownerControls
    ? [
        ...(primaryAction
          ? [
              {
                id: "correction",
                label: "Correct Case",
                onSelect: () => openDialog("correction"),
              },
            ]
          : []),
        ...(canReopen
          ? [
              {
                id: "reopen",
                label: "Reopen Case",
                onSelect: () => openDialog("reopen"),
              },
            ]
          : []),
        {
          id: "void",
          label: "Administrative void",
          danger: true,
          separator: Boolean(primaryAction || canReopen),
          onSelect: () => openDialog("void"),
        },
      ]
    : [];

  return (
    <PageContainer>
      <div className={styles.page} aria-busy={record.updating || busy}>
        <RecordDetailHeader
          title={`Case ${item.internalCaseId}`}
          subtitle={subtitle}
          status={voided ? "Archived" : item.status}
          statusTone={caseStatusTone(item.status, voided)}
          onBack={back}
          actions={
            <RecordActions>
              <div className={styles.actions}>
                {primaryAction ? (
                  <Button disabled={busy} onClick={primaryAction.onClick}>
                    {primaryAction.label}
                  </Button>
                ) : null}
                {ownerControls && !primaryAction ? (
                  <Button
                    variant="secondary"
                    disabled={busy}
                    onClick={() => openDialog("correction")}
                  >
                    Correct Case
                  </Button>
                ) : null}
                {overflowItems.length ? (
                  <OverflowMenu
                    label="More Case actions"
                    items={overflowItems}
                  />
                ) : null}
              </div>
            </RecordActions>
          }
        />

        {record.updating ? (
          <InlineNotice
            className={styles.notice}
            tone="info"
            title="Refreshing"
          >
            Updating authorized Case results.
          </InlineNotice>
        ) : null}
        {record.error && item ? (
          <InlineNotice
            className={styles.notice}
            tone="warning"
            title="Refresh failed"
          >
            {record.error} The last authorized Case remains on screen.
          </InlineNotice>
        ) : null}
        {success ? (
          <InlineNotice className={styles.notice} tone="success" title="Saved">
            {success}
          </InlineNotice>
        ) : null}
        {error ? (
          <InlineNotice
            className={styles.notice}
            tone="error"
            title="Command failed"
          >
            {error}
          </InlineNotice>
        ) : null}
        {choicesError ? (
          <InlineNotice
            className={styles.notice}
            tone="warning"
            title="Choices unavailable"
          >
            {choicesError}
          </InlineNotice>
        ) : null}
        {voided ? (
          <Banner tone="info" title="Archived">
            Retained read-only Case. Approval, booking, correction, and reopen
            are not available.
          </Banner>
        ) : null}

        <SectionCard
          title="Pipeline"
          description="Configured Bank Pipeline for this Case."
        >
          {pipeline.denied || (pipeline.error && !pipeline.data) ? (
            <UnavailableState
              title="Pipeline unavailable"
              description="No applicable Pipeline is available for this Case."
            />
          ) : pipeline.loading && !pipeline.data ? (
            <LoadingState title="Loading Pipeline" />
          ) : !stageItems.length ? (
            <UnavailableState
              title="Pipeline unavailable"
              description="No applicable Pipeline is available for this Case."
            />
          ) : (
            <HorizontalStageTracker
              label="Case Pipeline"
              items={stageItems}
              focusedId={
                stageItems.find((stage) => stage.status === "current")?.id
              }
            />
          )}
        </SectionCard>

        <SectionCard title="Customer">
          <InfoGrid>
            <InfoField
              label="Customer"
              value={
                <FieldValue
                  value={customerName}
                  fallback="Related record"
                  onOpen={
                    openCustomer
                      ? () => openCustomer(item.customerId)
                      : undefined
                  }
                />
              }
            />
            <InfoField
              label="Case"
              value={<TruncatedText value={item.internalCaseId} />}
            />
          </InfoGrid>
        </SectionCard>

        <SectionCard title="Product and Bank">
          <InfoGrid>
            <InfoField
              label="Case salary (AED)"
              value={
                item.salaryAed != null ? (
                  <MonetaryAmount
                    value={item.salaryAed}
                    compact={false}
                    align="start"
                  />
                ) : (
                  <FieldValue
                    value=""
                    fallback="Not recorded / not applicable"
                  />
                )
              }
            />
            <InfoField
              label="Product"
              value={
                <RecordImageLabel
                  src={label.image(item.productTypeId)}
                  label={productName}
                >
                  <FieldValue value={productName} fallback="Unavailable" />
                </RecordImageLabel>
              }
            />
            <InfoField
              label="Bank"
              value={
                <RecordImageLabel
                  src={label.image(item.bankId)}
                  label={bankName}
                >
                  <FieldValue value={bankName} fallback="Unavailable" />
                </RecordImageLabel>
              }
            />
            <InfoField
              label="Variant / PF amount"
              value={
                item.requestedPfAmount ? (
                  <MonetaryAmount
                    value={item.requestedPfAmount}
                    compact={false}
                    align="start"
                  />
                ) : (
                  <RecordImageLabel
                    src={label.image(item.productVariantId)}
                    label={variantName}
                  >
                    <FieldValue value={variantName} fallback="Not recorded" />
                  </RecordImageLabel>
                )
              }
            />
          </InfoGrid>
        </SectionCard>

        <SectionCard title="Assignment and ownership">
          <InfoGrid>
            <InfoField
              label="Case Owner"
              value={
                <FieldValue
                  value={ownerName}
                  fallback="Assigned employee"
                  onOpen={
                    openEmployee
                      ? () => openEmployee(item.ownerEmployeeId)
                      : undefined
                  }
                />
              }
            />
            <InfoField
              label="Coordinator"
              value={
                <FieldValue
                  value={coordinatorName}
                  fallback="Not assigned"
                  onOpen={
                    openEmployee && item.coordinatorEmployeeId
                      ? () => openEmployee(item.coordinatorEmployeeId!)
                      : undefined
                  }
                />
              }
            />
            <InfoField
              label="Branch"
              value={<FieldValue value={branchName} fallback="Unavailable" />}
            />
            <InfoField
              label="Department"
              value={
                <FieldValue value={departmentName} fallback="Unavailable" />
              }
            />
          </InfoGrid>
        </SectionCard>

        <SectionCard title="Processing and status">
          <InfoGrid>
            <InfoField
              label="Lifecycle status"
              value={
                <StatusBadge tone={caseStatusTone(item.status, voided)}>
                  {voided ? "Archived" : item.status}
                </StatusBadge>
              }
            />
            <InfoField
              label="Pipeline stage"
              value={
                <FieldValue value={item.currentStage} fallback="Not recorded" />
              }
            />
          </InfoGrid>
        </SectionCard>

        <SectionCard title="Booking">
          <InfoGrid>
            <InfoField
              label="Bank Case Number"
              value={
                <FieldValue
                  value={item.bankCaseNumber}
                  fallback="Not assigned"
                />
              }
            />
          </InfoGrid>
        </SectionCard>

        <SectionCard title="System information">
          <InfoGrid>
            <InfoField
              label="Created"
              value={
                item.createdAt ? (
                  <CompactDateTime value={item.createdAt} />
                ) : (
                  "Not recorded"
                )
              }
            />
            <InfoField
              label="Created by"
              value={
                <FieldValue
                  value={createdByName}
                  fallback="Team member"
                  onOpen={
                    openEmployee
                      ? () => openEmployee(item.createdByEmployeeId)
                      : undefined
                  }
                />
              }
            />
            {item.finalizedAt ? (
              <InfoField
                label="Finalized"
                value={<CompactDateTime value={item.finalizedAt} />}
              />
            ) : null}
            {voided ? (
              <InfoField
                label="Archived"
                value={
                  <CompactDateTime value={item.administrativelyVoidedAt} />
                }
              />
            ) : null}
            {voided && item.administrativelyVoidedByEmployeeId ? (
              <InfoField
                label="Archived by"
                value={
                  <EmployeeLabel
                    employeeId={item.administrativelyVoidedByEmployeeId}
                    fieldKey="actorEmployeeId"
                  />
                }
              />
            ) : null}
            {voided && item.administrativeVoidReason ? (
              <InfoField
                label="Archive reason"
                value={<TruncatedText value={item.administrativeVoidReason} />}
              />
            ) : null}
          </InfoGrid>
        </SectionCard>

        <RelatedRecordList title="Related records" items={related} />

        {history.denied ? (
          <SectionCard title="Activity">
            <PermissionDeniedState description="Case history is outside the current authorized scope." />
          </SectionCard>
        ) : history.error && !history.data ? (
          <SectionCard title="Activity">
            {isOffline(history.error) ? (
              <OfflineState />
            ) : (
              <RetryState
                title="History unavailable"
                description={history.error}
                retry={history.reload}
              />
            )}
          </SectionCard>
        ) : history.loading && !history.data ? (
          <SectionCard title="Activity">
            <LoadingState title="Loading history" />
          </SectionCard>
        ) : !timeline.length ? (
          <SectionCard title="Activity">
            <EmptyState
              title="No retained history"
              description="There are no authorized history events for this Case."
            />
          </SectionCard>
        ) : (
          <ActivityTimeline
            title="Activity"
            description="Retained Case lifecycle, approval, assignment, and stage history."
            items={timeline.map((event) => ({
              id: event.id,
              time: <CompactDateTime value={event.time} />,
              title: event.title,
              description: event.description,
              tone: event.tone,
              actor: event.actorId ? (
                <EmployeeLabel
                  employeeId={event.actorId}
                  fieldKey="actorEmployeeId"
                  plain
                />
              ) : undefined,
            }))}
          />
        )}
      </div>

      <Dialog
        open={dialog === "approval"}
        title="Approve and assign Coordinator"
        size="md"
        busy={busy}
        onClose={closeDialog}
        footer={
          <>
            <Button variant="secondary" disabled={busy} onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              loading={busy}
              disabled={!coordinator}
              onClick={() =>
                void command("approval", {
                  coordinatorEmployeeId: coordinator,
                })
              }
            >
              Approve and assign
            </Button>
          </>
        }
      >
        <div className={styles.dialogBody}>
          <p>
            {item.internalCaseId} · {customerName}
          </p>
          <PersonSelect
            id="case-coordinator"
            label="Coordinator"
            people={coordinatorOptions}
            value={coordinator}
            onChange={setCoordinator}
          />
        </div>
      </Dialog>

      <Dialog
        open={dialog === "booking"}
        title="Bank submission"
        size="md"
        busy={busy}
        onClose={closeDialog}
        footer={
          <>
            <Button variant="secondary" disabled={busy} onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              loading={busy}
              disabled={!bankRef.trim()}
              onClick={() =>
                void command("booking", { bankCaseNumber: bankRef.trim() })
              }
            >
              Record Bank Case Number
            </Button>
          </>
        }
      >
        <FormField label="Bank Case Number" htmlFor="case-bank-ref" required>
          <TextInput
            id="case-bank-ref"
            required
            value={bankRef}
            onChange={(event) => setBankRef(event.target.value)}
          />
        </FormField>
      </Dialog>

      <Dialog
        open={dialog === "correction"}
        title="Correct Case"
        size="md"
        busy={busy}
        onClose={closeDialog}
        footer={
          <>
            <Button variant="secondary" disabled={busy} onClick={closeDialog}>
              Cancel
            </Button>
            <Button
              loading={busy}
              disabled={!correction || !reason.trim() || !confirmed}
              onClick={() =>
                void command("correction", {
                  confirm: true,
                  reason,
                  [correctionField]: correction,
                })
              }
            >
              Confirm correction
            </Button>
          </>
        }
      >
        <div className={styles.dialogBody}>
          <FormField label="Correction" htmlFor="case-correction-field">
            <DropdownSelect
              id="case-correction-field"
              value={correctionField}
              onChange={(value) => {
                setCorrectionField(String(value));
                setCorrection("");
              }}
              options={[
                { value: "bankCaseNumber", label: "Bank Case Number" },
                { value: "currentStage", label: "Current stage" },
                { value: "ownerEmployeeId", label: "Case Owner" },
              ]}
            />
          </FormField>
          {correctionField === "ownerEmployeeId" ? (
            <PersonSelect
              id="case-correction-owner"
              label="New Case Owner"
              people={ownerOptions}
              value={correction}
              onChange={setCorrection}
            />
          ) : correctionField === "currentStage" ? (
            <FormField label="New stage" htmlFor="case-correction-stage">
              <DropdownSelect
                id="case-correction-stage"
                value={correction}
                onChange={(value) => setCorrection(String(value))}
                options={stageOptions}
                placeholder="Select retained Pipeline stage"
              />
            </FormField>
          ) : (
            <FormField
              label="New value"
              htmlFor="case-correction-value"
              required
            >
              <TextInput
                id="case-correction-value"
                required
                value={correction}
                onChange={(event) => setCorrection(event.target.value)}
              />
            </FormField>
          )}
          <FormField label="Reason" htmlFor="case-correction-reason" required>
            <CountedTextArea
              id="case-correction-reason"
              value={reason}
              onChange={setReason}
              maxLength={500}
            />
          </FormField>
          <Checkbox
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            label="Confirm this retained, audited action"
          />
        </div>
      </Dialog>

      <ConfirmationDialog
        open={dialog === "reopen"}
        title="Reopen Case"
        confirmLabel="Reopen Case"
        busy={busy}
        onClose={closeDialog}
        onConfirm={() => {
          if (!reason.trim() || !confirmed) return;
          void command("reopen", { confirm: true, reason });
        }}
      >
        <div className={styles.dialogBody}>
          <p>
            Lifecycle status and Bank Pipeline stage will both become{" "}
            {REOPENED_BY_OWNER}. Finance and wallet records are not reversed.
          </p>
          <FormField label="Reason" htmlFor="case-reopen-reason" required>
            <CountedTextArea
              id="case-reopen-reason"
              value={reason}
              onChange={setReason}
              maxLength={500}
            />
          </FormField>
          <Checkbox
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            label="Confirm this retained, audited action"
          />
        </div>
      </ConfirmationDialog>

      <DestructiveConfirmationDialog
        open={dialog === "void"}
        title="Administrative void"
        confirmLabel="Archive Case"
        busy={busy}
        onClose={closeDialog}
        onConfirm={() => {
          if (!reason.trim() || !confirmed) return;
          void command("administrative-void", { confirm: true, reason });
        }}
      >
        <div className={styles.dialogBody}>
          <p>
            The Case remains retained and read-only. Approval, booking,
            correction, and reopen will be rejected.
          </p>
          <FormField label="Reason" htmlFor="case-void-reason" required>
            <CountedTextArea
              id="case-void-reason"
              value={reason}
              onChange={setReason}
              maxLength={500}
            />
          </FormField>
          <Checkbox
            checked={confirmed}
            onChange={(event) => setConfirmed(event.target.checked)}
            label="Confirm this retained, audited action"
          />
        </div>
      </DestructiveConfirmationDialog>
    </PageContainer>
  );
}
