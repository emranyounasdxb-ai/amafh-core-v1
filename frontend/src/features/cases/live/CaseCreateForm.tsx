import { useEffect, useMemo, useRef, useState } from "react";
import {
  Button,
  Checkbox,
  Dialog,
  DropdownSelect,
  FormField,
  FormSection,
  InfoField,
  InfoGrid,
  MonetaryAmount,
  InlineNotice,
  Combobox,
  CurrencyInput,
  LoadingState,
  PersonSelect,
  Stepper,
  TextInput,
  UnsavedChangesDialog,
  nationalityOptions,
  type PersonOption,
  type SelectOption,
  type StepItem,
} from "../../../design-system";
import { choices } from "../../../app/api/choices";
import { ApiFailure } from "../../../app/api/http";
import { roundWholeText } from "../../../app/numbers/wholeNumber";
import type {
  CaseRecord,
  EmployeeSummary,
  NamedRecord,
} from "../../../app/api/models";
import { useSession } from "../../../app/session/useSession";
import {
  CASE_CREATE_PERSONAL_LABELS,
  CASE_CREATE_STEPS,
  caseCreateInvalidField,
  caseCreateServerField,
  emptyCaseCreateValues,
  formatCaseCreateFailure,
  type CaseCreateValues,
} from "./caseCreatePresentation";
import styles from "./CaseCreateForm.module.css";

const nationalityChoices = nationalityOptions().filter(
  (option) => option.value !== "XK",
);

function optionName(rows: NamedRecord[], id: string) {
  return rows.find((row) => row.id === id)?.name || "Unavailable";
}

export function CaseCreateForm({
  close,
  saved,
  personal = false,
}: {
  close: () => void;
  saved: (item: CaseRecord) => void;
  personal?: boolean;
}) {
  const { api, session } = useSession();
  const [step, setStep] = useState(1);
  const [products, setProducts] = useState<NamedRecord[]>([]);
  const [banks, setBanks] = useState<NamedRecord[]>([]);
  const [variants, setVariants] = useState<NamedRecord[]>([]);
  const [mappings, setMappings] = useState<NamedRecord[]>([]);
  const [branches, setBranches] = useState<NamedRecord[]>([]);
  const [departments, setDepartments] = useState<NamedRecord[]>([]);
  const [people, setPeople] = useState<EmployeeSummary[]>([]);
  const [error, setError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [fieldMessage, setFieldMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [loading, setLoading] = useState(true);
  const [leaveOpen, setLeaveOpen] = useState(false);
  const replay = useRef({ payload: "", key: "" });
  const [form, setForm] = useState<CaseCreateValues>(
    emptyCaseCreateValues(session?.employeeId || ""),
  );
  const product = products.find((item) => item.id === form.productTypeId);
  const creditCard = product?.code === "CC";
  const initial = useRef(emptyCaseCreateValues(session?.employeeId || ""));
  const dirty = useMemo(
    () => JSON.stringify(form) !== JSON.stringify(initial.current) || step > 1,
    [form, step],
  );

  useEffect(() => {
    const controller = new AbortController();
    Promise.all([
      choices<NamedRecord>(
        api,
        "/catalog/product-types?active=true",
        controller.signal,
      ),
      choices<NamedRecord>(
        api,
        "/catalog/banks?active=true",
        controller.signal,
      ),
      choices<NamedRecord>(
        api,
        "/catalog/product-variants?active=true",
        controller.signal,
      ),
      choices<NamedRecord>(
        api,
        "/catalog/bank-product-mappings?active=true",
        controller.signal,
      ),
      choices<EmployeeSummary>(
        api,
        "/employees?status=Active",
        controller.signal,
      ),
      api.request<NamedRecord[]>("/branches", { signal: controller.signal }),
      api.request<NamedRecord[]>("/departments", {
        signal: controller.signal,
      }),
    ])
      .then(
        ([
          nextProducts,
          nextBanks,
          nextVariants,
          nextMappings,
          nextPeople,
          nextBranches,
          nextDepartments,
        ]) => {
          setProducts(nextProducts);
          setBanks(nextBanks);
          setVariants(nextVariants);
          setMappings(nextMappings);
          setPeople(nextPeople);
          setBranches(nextBranches);
          setDepartments(nextDepartments);
        },
      )
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setError(
            failure instanceof Error
              ? failure.message
              : "Unable to load choices",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
  }, [api]);

  const patch = (next: Partial<CaseCreateValues>) => {
    setForm((current) => ({ ...current, ...next }));
    setFieldError("");
    setFieldMessage("");
    setError("");
  };

  const namedOptions = (rows: NamedRecord[]): SelectOption[] =>
    rows.map((row) => ({ value: row.id, label: row.name }));

  const bankOptions = namedOptions(
    banks.filter((bank) =>
      mappings.some(
        (mapping) =>
          mapping.bank_id === bank.id &&
          mapping.product_type_id === form.productTypeId,
      ),
    ),
  );
  const variantOptions = namedOptions(
    variants.filter(
      (variant) =>
        variant.bank_id === form.bankId &&
        variant.product_type_id === form.productTypeId,
    ),
  );
  const ownerPeople: PersonOption[] = people
    .filter(
      (person) =>
        person.id === session?.employeeId ||
        (!personal &&
          session?.designation === "Team Leader" &&
          person.designation === "Sales Executive"),
    )
    .map((person) => ({
      value: person.id,
      name: person.fullName,
      subtitle: person.employeeCode,
    }));

  const stepLabel = (index: number) =>
    personal
      ? (CASE_CREATE_PERSONAL_LABELS[index] ?? CASE_CREATE_STEPS[index]?.label)
      : CASE_CREATE_STEPS[index]?.label;
  const stepperItems: StepItem[] = CASE_CREATE_STEPS.map((item, index) => ({
    id: item.id,
    label: stepLabel(index) ?? item.label,
    status:
      index + 1 < step
        ? "complete"
        : index + 1 === step
          ? "current"
          : "upcoming",
  }));

  const requestClose = () => {
    if (busy) return;
    if (dirty) {
      setLeaveOpen(true);
      return;
    }
    close();
  };

  const continueOrSubmit = async () => {
    const issue = caseCreateInvalidField(step, form, creditCard);
    if (issue) {
      setFieldError(issue.field);
      setFieldMessage(issue.message);
      setError(issue.message);
      return;
    }
    if (step < 5) {
      setStep((current) => current + 1);
      setError("");
      setFieldError("");
      setFieldMessage("");
      return;
    }
    const customer =
      form.type === "Individual"
        ? {
            type: form.type,
            fullName: form.fullName,
            nationality: form.nationality,
            emiratesId: form.emiratesId,
            passportNumber: form.passportNumber,
            employer: form.employer,
            mobile: form.mobile,
            email: form.email,
          }
        : {
            type: form.type,
            companyName: form.companyName,
            contactPerson: form.contactPerson,
            tradeLicense: form.tradeLicense,
            mobile: form.mobile,
            email: form.email,
          };
    const payload = JSON.stringify({
      confirmedInterest: true,
      customer,
      productTypeId: form.productTypeId,
      bankId: form.bankId,
      ...(personal ? {} : { ownerEmployeeId: form.ownerEmployeeId }),
      ...(creditCard
        ? { productVariantId: form.productVariantId }
        : {
            requestedPfAmount:
              roundWholeText(form.requestedPfAmount) ?? form.requestedPfAmount,
          }),
    });
    if (replay.current.payload !== payload)
      replay.current = { payload, key: crypto.randomUUID() };
    setBusy(true);
    setError("");
    try {
      saved(
        await api.request<CaseRecord>(personal ? "/my-cases" : "/cases", {
          method: "POST",
          body: payload,
          headers: { "Idempotency-Key": replay.current.key },
        }),
      );
    } catch (failure) {
      if (failure instanceof ApiFailure) {
        const field = caseCreateServerField(failure.fieldErrors);
        if (field) {
          setStep(field.step);
          setFieldError(field.field);
          setFieldMessage(field.message);
          setError(field.message);
          return;
        }
      }
      setError(
        failure instanceof ApiFailure
          ? formatCaseCreateFailure(
              failure.code,
              failure.message,
              failure.fieldErrors,
            )
          : "Unable to save. You can retry this request safely.",
      );
    } finally {
      setBusy(false);
    }
  };

  const nationalityName =
    nationalityChoices.find((option) => option.value === form.nationality)
      ?.label || "Unavailable";
  const selectedOwner = people.find(
    (person) => person.id === form.ownerEmployeeId,
  );
  const ownerName =
    ownerPeople.find((person) => person.value === form.ownerEmployeeId)?.name ||
    (personal ? session?.displayName : "") ||
    "Unavailable";
  const ownerBranch = optionName(branches, selectedOwner?.branchId ?? "");
  const ownerDepartment = optionName(
    departments,
    selectedOwner?.departmentId ?? "",
  );

  return (
    <>
      <Dialog
        open
        size="lg"
        busy={busy}
        title={stepLabel(step - 1) ?? (personal ? "Create Case" : "Add Case")}
        description={`Step ${step} of ${CASE_CREATE_STEPS.length}`}
        onClose={requestClose}
        footer={
          <div className={styles.footer}>
            <Button
              type="button"
              variant="ghost"
              size="compact"
              disabled={busy}
              onClick={requestClose}
            >
              Cancel
            </Button>
            {step > 1 ? (
              <Button
                type="button"
                variant="secondary"
                size="compact"
                disabled={busy}
                onClick={() => {
                  setStep((current) => current - 1);
                  setError("");
                  setFieldError("");
                  setFieldMessage("");
                }}
              >
                Back
              </Button>
            ) : null}
            <Button
              type="button"
              size="compact"
              loading={busy}
              disabled={busy || loading}
              onClick={() => void continueOrSubmit()}
            >
              {step === 5 ? "Create Case" : "Continue"}
            </Button>
          </div>
        }
      >
        <div className={styles.body}>
          <Stepper items={stepperItems} label="Case creation steps" />
          {loading ? (
            <LoadingState title="Loading authorized choices" />
          ) : (
            <form
              className={styles.form}
              onSubmit={(event) => {
                event.preventDefault();
                void continueOrSubmit();
              }}
            >
              {step === 1 ? (
                <FormSection title={stepLabel(0) ?? "Add Case"} columns={1}>
                  <FormField
                    label="Product"
                    htmlFor="case-create-product"
                    required
                    error={
                      fieldError === "productTypeId"
                        ? "Select a product."
                        : undefined
                    }
                  >
                    <DropdownSelect
                      id="case-create-product"
                      compact
                      value={form.productTypeId}
                      onChange={(value) =>
                        patch({
                          productTypeId: Array.isArray(value)
                            ? (value[0] ?? "")
                            : value,
                          bankId: "",
                          productVariantId: "",
                        })
                      }
                      options={namedOptions(products)}
                      placeholder="Select Product"
                      invalid={fieldError === "productTypeId"}
                    />
                  </FormField>
                </FormSection>
              ) : null}

              {step === 2 ? (
                <FormSection title="Customer details" columns={2}>
                  <FormField label="Customer type" htmlFor="case-create-type">
                    <DropdownSelect
                      id="case-create-type"
                      compact
                      value={form.type}
                      onChange={(value) => {
                        const type =
                          (Array.isArray(value) ? value[0] : value) ===
                          "Company"
                            ? "Company"
                            : "Individual";
                        patch({
                          type,
                          nationality:
                            type === "Company" ? "" : form.nationality,
                        });
                      }}
                      options={[
                        { value: "Individual", label: "Individual" },
                        { value: "Company", label: "Company" },
                      ]}
                    />
                  </FormField>
                  {form.type === "Individual" ? (
                    <>
                      <FormField
                        label="Full Name"
                        htmlFor="case-create-full-name"
                        required
                        error={
                          fieldError === "fullName"
                            ? "Enter the full name."
                            : undefined
                        }
                      >
                        <TextInput
                          id="case-create-full-name"
                          compact
                          value={form.fullName}
                          onChange={(event) =>
                            patch({ fullName: event.target.value })
                          }
                          invalid={fieldError === "fullName"}
                        />
                      </FormField>
                      <FormField
                        label="Nationality"
                        htmlFor="case-create-nationality"
                        required
                        error={
                          fieldError === "nationality"
                            ? "Select a nationality."
                            : undefined
                        }
                      >
                        <Combobox
                          id="case-create-nationality"
                          compact
                          value={form.nationality}
                          onChange={(value) => patch({ nationality: value })}
                          options={nationalityChoices}
                          placeholder="Search nationality or ISO code"
                          invalid={fieldError === "nationality"}
                        />
                      </FormField>
                      <FormField
                        label="Emirates ID"
                        htmlFor="case-create-eid"
                        required
                        error={
                          fieldError === "emiratesId" ? fieldMessage : undefined
                        }
                      >
                        <TextInput
                          id="case-create-eid"
                          compact
                          value={form.emiratesId}
                          onChange={(event) =>
                            patch({ emiratesId: event.target.value })
                          }
                          invalid={fieldError === "emiratesId"}
                        />
                      </FormField>
                      <FormField
                        label="Passport"
                        htmlFor="case-create-passport"
                        required
                        error={
                          fieldError === "passportNumber"
                            ? "Enter the passport number."
                            : undefined
                        }
                      >
                        <TextInput
                          id="case-create-passport"
                          compact
                          value={form.passportNumber}
                          onChange={(event) =>
                            patch({ passportNumber: event.target.value })
                          }
                          invalid={fieldError === "passportNumber"}
                        />
                      </FormField>
                      <FormField
                        label="Employer"
                        htmlFor="case-create-employer"
                        required
                        error={
                          fieldError === "employer"
                            ? "Enter the employer."
                            : undefined
                        }
                      >
                        <TextInput
                          id="case-create-employer"
                          compact
                          value={form.employer}
                          onChange={(event) =>
                            patch({ employer: event.target.value })
                          }
                          invalid={fieldError === "employer"}
                        />
                      </FormField>
                    </>
                  ) : (
                    <>
                      <FormField
                        label="Company Name"
                        htmlFor="case-create-company"
                        required
                        error={
                          fieldError === "companyName"
                            ? "Enter the company name."
                            : undefined
                        }
                      >
                        <TextInput
                          id="case-create-company"
                          compact
                          value={form.companyName}
                          onChange={(event) =>
                            patch({ companyName: event.target.value })
                          }
                          invalid={fieldError === "companyName"}
                        />
                      </FormField>
                      <FormField
                        label="Contact Person"
                        htmlFor="case-create-contact"
                        required
                        error={
                          fieldError === "contactPerson"
                            ? "Enter the contact person."
                            : undefined
                        }
                      >
                        <TextInput
                          id="case-create-contact"
                          compact
                          value={form.contactPerson}
                          onChange={(event) =>
                            patch({ contactPerson: event.target.value })
                          }
                          invalid={fieldError === "contactPerson"}
                        />
                      </FormField>
                      <FormField
                        label="Trade License"
                        htmlFor="case-create-license"
                        required
                        error={
                          fieldError === "tradeLicense"
                            ? "Enter the trade license."
                            : undefined
                        }
                      >
                        <TextInput
                          id="case-create-license"
                          compact
                          value={form.tradeLicense}
                          onChange={(event) =>
                            patch({ tradeLicense: event.target.value })
                          }
                          invalid={fieldError === "tradeLicense"}
                        />
                      </FormField>
                    </>
                  )}
                  <FormField
                    label="UAE Mobile Number"
                    htmlFor="case-create-mobile"
                    required
                    error={fieldError === "mobile" ? fieldMessage : undefined}
                  >
                    <TextInput
                      id="case-create-mobile"
                      compact
                      value={form.mobile}
                      onChange={(event) =>
                        patch({ mobile: event.target.value })
                      }
                      invalid={fieldError === "mobile"}
                    />
                  </FormField>
                  <FormField
                    label="Email"
                    htmlFor="case-create-email"
                    required
                    error={fieldError === "email" ? fieldMessage : undefined}
                  >
                    <TextInput
                      id="case-create-email"
                      compact
                      type="email"
                      value={form.email}
                      onChange={(event) => patch({ email: event.target.value })}
                      invalid={fieldError === "email"}
                    />
                  </FormField>
                </FormSection>
              ) : null}

              {step === 3 ? (
                <FormSection title="Bank & product" columns={2}>
                  <FormField
                    label="Bank"
                    htmlFor="case-create-bank"
                    required
                    error={
                      fieldError === "bankId" ? "Select a bank." : undefined
                    }
                  >
                    <DropdownSelect
                      id="case-create-bank"
                      compact
                      value={form.bankId}
                      onChange={(value) =>
                        patch({
                          bankId: Array.isArray(value)
                            ? (value[0] ?? "")
                            : value,
                          productVariantId: "",
                        })
                      }
                      options={bankOptions}
                      placeholder="Select Bank"
                      invalid={fieldError === "bankId"}
                    />
                  </FormField>
                  {creditCard ? (
                    <FormField
                      label="Product Variant"
                      htmlFor="case-create-variant"
                      required
                      error={
                        fieldError === "productVariantId"
                          ? "Select a product variant."
                          : undefined
                      }
                    >
                      <DropdownSelect
                        id="case-create-variant"
                        compact
                        value={form.productVariantId}
                        onChange={(value) =>
                          patch({
                            productVariantId: Array.isArray(value)
                              ? (value[0] ?? "")
                              : value,
                          })
                        }
                        options={variantOptions}
                        placeholder="Select Product Variant"
                        invalid={fieldError === "productVariantId"}
                      />
                    </FormField>
                  ) : (
                    <FormField
                      label="Requested amount (AED)"
                      htmlFor="case-create-amount"
                      required
                      error={
                        fieldError === "requestedPfAmount"
                          ? fieldMessage
                          : undefined
                      }
                    >
                      <CurrencyInput
                        id="case-create-amount"
                        compact
                        value={form.requestedPfAmount}
                        inputMode="numeric"
                        onChange={(event) =>
                          patch({ requestedPfAmount: event.target.value })
                        }
                        onBlur={(event) => {
                          const whole = roundWholeText(event.target.value);
                          if (whole !== null && whole !== event.target.value)
                            patch({ requestedPfAmount: whole });
                        }}
                        invalid={fieldError === "requestedPfAmount"}
                      />
                    </FormField>
                  )}
                </FormSection>
              ) : null}

              {step === 4 && personal ? (
                <FormSection title={stepLabel(3) ?? "Case Owner"} columns={1}>
                  <InfoGrid>
                    <InfoField label="Case Owner" value={ownerName} />
                    <InfoField label="Branch" value={ownerBranch} />
                    <InfoField label="Department" value={ownerDepartment} />
                  </InfoGrid>
                  <p className={styles.support}>
                    Cases created from Own Cases always belong to you.
                  </p>
                </FormSection>
              ) : null}

              {step === 4 && !personal ? (
                <FormSection title="Assign owner" columns={1}>
                  <FormField
                    label="Case Owner"
                    htmlFor="case-create-owner"
                    required
                    error={
                      fieldError === "ownerEmployeeId"
                        ? "Select a Case Owner."
                        : undefined
                    }
                  >
                    <PersonSelect
                      id="case-create-owner"
                      label="Case Owner"
                      compact
                      people={ownerPeople}
                      value={form.ownerEmployeeId}
                      onChange={(value) => patch({ ownerEmployeeId: value })}
                    />
                  </FormField>
                </FormSection>
              ) : null}

              {step === 5 ? (
                <FormSection title="Review" columns={1}>
                  <InfoGrid>
                    <InfoField
                      label="Customer"
                      value={form.fullName || form.companyName || "Unavailable"}
                    />
                    <InfoField label="Customer type" value={form.type} />
                    {form.type === "Individual" ? (
                      <InfoField label="Nationality" value={nationalityName} />
                    ) : null}
                    <InfoField
                      label="Product"
                      value={optionName(products, form.productTypeId)}
                    />
                    <InfoField
                      label="Bank"
                      value={optionName(banks, form.bankId)}
                    />
                    <InfoField
                      label={
                        creditCard
                          ? "Product Variant"
                          : "Requested amount (AED)"
                      }
                      value={
                        creditCard ? (
                          optionName(variants, form.productVariantId)
                        ) : (
                          <MonetaryAmount
                            value={form.requestedPfAmount}
                            compact={false}
                            align="start"
                          />
                        )
                      }
                    />
                    <InfoField label="Branch" value={ownerBranch} />
                    <InfoField label="Department" value={ownerDepartment} />
                    <InfoField label="Case Owner" value={ownerName} />
                    <InfoField
                      label="Coordinator"
                      value="Assigned after Sales Manager approval"
                    />
                  </InfoGrid>
                  <Checkbox
                    label="Customer interest is confirmed. Submit for approval."
                    checked={form.confirmedInterest}
                    onChange={(event) =>
                      patch({ confirmedInterest: event.target.checked })
                    }
                  />
                  {fieldError === "confirmedInterest" ? (
                    <InlineNotice tone="warning" title="Confirmation required">
                      Confirm customer interest before creating the Case.
                    </InlineNotice>
                  ) : null}
                  <p className={styles.support}>
                    The server checks identity and creates or reuses the
                    Customer in the same transaction.
                  </p>
                </FormSection>
              ) : null}
            </form>
          )}
          {error ? (
            <InlineNotice tone="error" title="Unable to continue">
              {error}
            </InlineNotice>
          ) : null}
        </div>
      </Dialog>
      <UnsavedChangesDialog
        open={leaveOpen}
        onStay={() => setLeaveOpen(false)}
        onLeave={close}
        busy={busy}
      />
    </>
  );
}
