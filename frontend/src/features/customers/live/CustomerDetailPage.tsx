import { useState } from "react";
import {
  Button,
  Checkbox,
  CountedTextArea,
  Dialog,
  EmptyState,
  EmptyValue,
  EmiratesIdInput,
  MonetaryAmount,
  ErrorState,
  FormField,
  InfoField,
  InfoGrid,
  InlineNotice,
  LoadingState,
  NotFoundState,
  OfflineState,
  PageContainer,
  PermissionDeniedState,
  RecordActions,
  RecordDetailHeader,
  RelatedRecordList,
  SectionCard,
  StatusBadge,
  TextInput,
  type RelatedRecordItem,
} from "../../../design-system";
import { canOpenPage } from "../../../access";
import { ApiFailure } from "../../../app/api/http";
import { useResource } from "../../../app/api/useResource";
import { useSession } from "../../../app/session/useSession";
import {
  customerDisplayName,
  identityValue,
  individualNationality,
  relatedCaseMeta,
  relatedCaseTitle,
  type CustomerDetailRecord,
} from "./customerDetailPresentation";
import styles from "./CustomerDetailPage.module.css";

function isOffline(error: string) {
  return !navigator.onLine || error.includes("could not be reached");
}

function Value({ value }: { value: string }) {
  return value ? value : <EmptyValue />;
}

function optionalField(value: string) {
  const next = value.trim();
  return next || undefined;
}

export function CustomerDetailPage({
  id,
  back,
  openCase,
}: {
  id: string;
  back: () => void;
  openCase?: (id: string) => void;
}) {
  const { api, session } = useSession();
  const resource = useResource<CustomerDetailRecord>(`/customers/${id}`);
  const [correctOpen, setCorrectOpen] = useState(false);
  const [emiratesId, setEmiratesId] = useState("");
  const [passportNumber, setPassportNumber] = useState("");
  const [tradeLicense, setTradeLicense] = useState("");
  const [reason, setReason] = useState("");
  const [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false);
  const [commandError, setCommandError] = useState("");
  const [commandSuccess, setCommandSuccess] = useState("");

  const row = resource.data;
  const individual = row?.type === "Individual";
  const identity = row?.identity;
  const canCorrect = session?.designation === "Owner";
  const canOpenCase = Boolean(
    openCase && session && canOpenPage(session, "case-detail"),
  );

  const openCorrection = () => {
    setEmiratesId(identityValue(identity, "emirates_id"));
    setPassportNumber(identityValue(identity, "passport_number"));
    setTradeLicense(identityValue(identity, "trade_license"));
    setReason("");
    setConfirm(false);
    setCommandError("");
    setCorrectOpen(true);
  };

  const submitCorrection = async () => {
    if (!confirm || !reason.trim()) {
      setCommandError("Confirm the correction and enter a reason.");
      return;
    }
    const body = individual
      ? {
          confirm: true as const,
          reason: reason.trim(),
          ...(optionalField(emiratesId)
            ? { emiratesId: optionalField(emiratesId) }
            : {}),
          ...(optionalField(passportNumber)
            ? { passportNumber: optionalField(passportNumber) }
            : {}),
        }
      : {
          confirm: true as const,
          reason: reason.trim(),
          ...(optionalField(tradeLicense)
            ? { tradeLicense: optionalField(tradeLicense) }
            : {}),
        };
    setBusy(true);
    setCommandError("");
    try {
      await api.request(`/customers/${id}/correct-identity`, {
        method: "POST",
        body: JSON.stringify(body),
      });
      setCorrectOpen(false);
      setCommandSuccess("Identity correction recorded.");
      resource.reload();
    } catch (failure) {
      setCommandError(
        failure instanceof ApiFailure
          ? failure.message
          : "Unable to save the identity correction.",
      );
    } finally {
      setBusy(false);
    }
  };

  if (!session) return null;
  if (resource.denied) {
    const missing =
      resource.error.toLowerCase().includes("unavailable") ||
      resource.error.toLowerCase().includes("not found");
    return (
      <PageContainer>
        {missing ? (
          <NotFoundState
            title="Customer unavailable"
            description="This record is not available in the current authorized scope."
            action={
              <Button variant="secondary" onClick={back}>
                Back
              </Button>
            }
          />
        ) : (
          <PermissionDeniedState />
        )}
      </PageContainer>
    );
  }
  if (resource.error && !resource.data) {
    return (
      <PageContainer>
        {isOffline(resource.error) ? (
          <OfflineState />
        ) : (
          <ErrorState description={resource.error} retry={resource.reload} />
        )}
      </PageContainer>
    );
  }
  if (resource.loading && !resource.data) {
    return (
      <PageContainer>
        <LoadingState title="Loading Customer" />
      </PageContainer>
    );
  }
  if (!row) {
    return (
      <PageContainer>
        <NotFoundState
          title="Customer unavailable"
          description="This record is not available in the current authorized scope."
          action={
            <Button variant="secondary" onClick={back}>
              Back
            </Button>
          }
        />
      </PageContainer>
    );
  }

  const name = customerDisplayName(row);
  const related = (row.cases ?? []).map((item) => {
    const title = relatedCaseTitle(item);
    const meta = relatedCaseMeta(item);
    return {
      id: item.id,
      title,
      meta: meta || undefined,
      onOpen: canOpenCase ? () => openCase?.(item.id) : undefined,
    } satisfies RelatedRecordItem;
  });

  return (
    <PageContainer>
      <div className={styles.page}>
        <RecordDetailHeader
          title={name}
          subtitle={row.customerId}
          status={row.type}
          statusTone="neutral"
          onBack={back}
          actions={
            canCorrect ? (
              <RecordActions>
                <Button
                  size="compact"
                  disabled={busy}
                  onClick={openCorrection}
                >
                  Correct identity
                </Button>
              </RecordActions>
            ) : undefined
          }
        />
        {resource.updating ? (
          <InlineNotice tone="info" title="Refreshing">
            Updating the authorized Customer record.
          </InlineNotice>
        ) : null}
        {commandSuccess ? (
          <InlineNotice tone="success" title="Saved">
            {commandSuccess}
          </InlineNotice>
        ) : null}

        <SectionCard compact title="Customer identity">
          <InfoGrid>
            <InfoField
              label={individual ? "Full name" : "Company name"}
              value={
                <Value
                  value={identityValue(
                    identity,
                    individual ? "full_name" : "company_name",
                  )}
                />
              }
            />
            <InfoField
              label="Customer type"
              value={<StatusBadge tone="neutral">{row.type}</StatusBadge>}
            />
            {individual ? (
              <InfoField
                label="Nationality"
                value={<Value value={individualNationality(identity)} />}
              />
            ) : null}
            <InfoField
              label="Salary (AED)"
              value={
                row.salaryAed != null ? (
                  <MonetaryAmount
                    value={row.salaryAed}
                    compact={false}
                    align="start"
                  />
                ) : (
                  <EmptyValue />
                )
              }
            />
          </InfoGrid>
        </SectionCard>

        <SectionCard
          compact
          title={individual ? "Individual details" : "Company details"}
        >
          <InfoGrid>
            {individual ? (
              <>
                <InfoField
                  label="Emirates ID"
                  value={
                    <Value value={identityValue(identity, "emirates_id")} />
                  }
                />
                <InfoField
                  label="Passport number"
                  value={
                    <Value value={identityValue(identity, "passport_number")} />
                  }
                />
                <InfoField
                  label="Employer"
                  value={<Value value={identityValue(identity, "employer")} />}
                />
              </>
            ) : (
              <InfoField
                label="Trade licence"
                value={
                  <Value value={identityValue(identity, "trade_license")} />
                }
              />
            )}
          </InfoGrid>
        </SectionCard>

        <SectionCard compact title="Contact information">
          <InfoGrid>
            {!individual ? (
              <InfoField
                label="Contact person"
                value={
                  <Value value={identityValue(identity, "contact_person")} />
                }
              />
            ) : null}
            <InfoField
              label="Mobile number"
              value={<Value value={identityValue(identity, "mobile")} />}
            />
            <InfoField
              label="Email address"
              value={<Value value={identityValue(identity, "email")} />}
            />
          </InfoGrid>
        </SectionCard>

        <SectionCard compact title="Record information">
          <InfoGrid>
            <InfoField label="Customer ID" value={row.customerId} />
          </InfoGrid>
        </SectionCard>

        {related.length ? (
          <RelatedRecordList title="Related Cases" items={related} />
        ) : (
          <SectionCard compact title="Related Cases">
            <EmptyState
              title="No related Cases"
              description="There are no authorized Cases linked to this record."
            />
          </SectionCard>
        )}
      </div>

      <Dialog
        open={correctOpen}
        title="Correct identity"
        size="md"
        busy={busy}
        onClose={() => {
          if (!busy) setCorrectOpen(false);
        }}
        footer={
          <>
            <Button
              variant="secondary"
              size="compact"
              disabled={busy}
              onClick={() => setCorrectOpen(false)}
            >
              Cancel
            </Button>
            <Button
              size="compact"
              loading={busy}
              disabled={busy}
              onClick={() => void submitCorrection()}
            >
              Save correction
            </Button>
          </>
        }
      >
        <div className={styles.correct}>
          {individual ? (
            <>
              <FormField label="Emirates ID" htmlFor="customer-eid">
                <EmiratesIdInput
                  id="customer-eid"
                  compact
                  value={emiratesId}
                  onValueChange={setEmiratesId}
                />
              </FormField>
              <FormField label="Passport Number" htmlFor="customer-passport">
                <TextInput
                  id="customer-passport"
                  compact
                  value={passportNumber}
                  onChange={(event) => setPassportNumber(event.target.value)}
                />
              </FormField>
            </>
          ) : (
            <FormField label="Trade License" htmlFor="customer-license">
              <TextInput
                id="customer-license"
                compact
                value={tradeLicense}
                onChange={(event) => setTradeLicense(event.target.value)}
              />
            </FormField>
          )}
          <FormField label="Reason" htmlFor="customer-reason" required>
            <CountedTextArea
              id="customer-reason"
              value={reason}
              maxLength={500}
              onChange={setReason}
            />
          </FormField>
          <Checkbox
            label="Confirm identity correction"
            checked={confirm}
            onChange={(event) => setConfirm(event.target.checked)}
          />
          {commandError ? (
            <InlineNotice tone="error" title="Unable to save">
              {commandError}
            </InlineNotice>
          ) : null}
        </div>
      </Dialog>
    </PageContainer>
  );
}
