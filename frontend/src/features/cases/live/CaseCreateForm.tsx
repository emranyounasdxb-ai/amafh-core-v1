import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
import { recordImageSrc, type ImageKind } from "../../../app/api/recordImages";
import { RecordImage } from "../../../shared/media/RecordImage";
import { ExistingCustomerChoice } from "./ExistingCustomerChoice";
import type { CustomerDetailRecord } from "../../customers/live/customerDetailPresentation";

type VariantChoices = {
  items: NamedRecord[];
  missingCriteriaCount: number;
  configuredCount: number;
  totalVariantsCount: number;
};

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
  const [eligibility, setEligibility] = useState<{
    key: string;
    status: "loading" | "ready" | "error";
    data?: VariantChoices;
    error?: string;
  } | null>(null);
  const [eligibilityAttempt, setEligibilityAttempt] = useState(0);
  const [eligibilityRevision, setEligibilityRevision] = useState(0);
  const [prefilling, setPrefilling] = useState(false);
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
          nextMappings,
          nextPeople,
          nextBranches,
          nextDepartments,
        ]) => {
          setProducts(nextProducts);
          setBanks(nextBanks);
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

  const salary = roundWholeText(form.salaryAed);
  const salaryValid =
    salary !== null &&
    !form.salaryAed.trim().startsWith("-") &&
    BigInt(salary) >= 0n &&
    salary.length <= 18;
  const eligibilityQuery =
    creditCard && form.bankId && (form.type === "Company" || salaryValid)
      ? new URLSearchParams({
          bankId: form.bankId,
          productTypeId: form.productTypeId,
          customerType: form.type,
          ...(form.type === "Individual" ? { salaryAed: salary! } : {}),
        }).toString()
      : "";
  const eligibilityKey = `${eligibilityQuery}:${eligibilityRevision}:${eligibilityAttempt}`;
  useEffect(() => {
    if (!eligibilityQuery) return;
    const controller = new AbortController();
    api
      .request<VariantChoices>(
        `/catalog/product-variants/eligibility?${eligibilityQuery}`,
        { signal: controller.signal },
      )
      .then((data) => {
        if (controller.signal.aborted) return;
        if (
          !Array.isArray(data.items) ||
          data.items.some(
            (row) =>
              !row ||
              typeof row.id !== "string" ||
              typeof row.name !== "string",
          )
        )
          throw new Error(
            "Invalid Variant eligibility response. Retry loading eligibility.",
          );
        setEligibility({ key: eligibilityKey, status: "ready", data });
        setVariants(data.items);
        setForm((current) =>
          data.items.some((row) => row.id === current.productVariantId)
            ? current
            : { ...current, productVariantId: "" },
        );
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setEligibility({
            key: eligibilityKey,
            status: "error",
            error:
              failure instanceof Error
                ? failure.message
                : "Variant eligibility could not be loaded.",
          });
      });
    return () => controller.abort();
  }, [api, eligibilityQuery, eligibilityKey]);
  const eligibleReady = Boolean(
    eligibilityQuery &&
    eligibility?.key === eligibilityKey &&
    eligibility.status === "ready",
  );
  const prefill = useCallback((customer: CustomerDetailRecord) => {
    setEligibilityRevision((value) => value + 1);
    const identity = customer.identity ?? {};
    const value = (key: string) => String(identity[key] ?? "");
    setForm((current) => ({
      ...current,
      type: customer.type === "Company" ? "Company" : "Individual",
      fullName: value("full_name"),
      nationality: value("nationality"),
      emiratesId: value("emirates_id"),
      passportNumber: value("passport_number"),
      employer: value("employer"),
      companyName: value("company_name"),
      contactPerson: value("contact_person"),
      tradeLicense: value("trade_license"),
      mobile: value("mobile"),
      email: value("email"),
      salaryAed: customer.salaryAed ?? "",
      productVariantId: "",
    }));
    setFieldError("");
    setFieldMessage("");
    setError("");
  }, []);

  const patch = (next: Partial<CaseCreateValues>) => {
    if (
      ["salaryAed", "bankId", "productTypeId", "type"].some(
        (key) => key in next,
      )
    )
      setEligibilityRevision((value) => value + 1);
    setForm((current) => {
      const updated = { ...current, ...next };
      if (
        "salaryAed" in next &&
        (roundWholeText(updated.salaryAed) === null ||
          updated.salaryAed.trim().startsWith("-"))
      )
        updated.productVariantId = "";
      return updated;
    });
    setFieldError("");
    setFieldMessage("");
    setError("");
  };

  const namedOptions = (rows: NamedRecord[], kind: ImageKind): SelectOption[] =>
    rows.map((row) => ({
      value: row.id,
      label: row.name,
      leading: recordImageSrc(kind, row) ? (
        <RecordImage src={recordImageSrc(kind, row)} label={row.name} />
      ) : undefined,
    }));

  const bankOptions = namedOptions(
    banks.filter((bank) =>
      mappings.some(
        (mapping) =>
          mapping.bank_id === bank.id &&
          mapping.product_type_id === form.productTypeId,
      ),
    ),
    "banks",
  );
  const variantOptions = namedOptions(
    (eligibleReady ? eligibility!.data!.items : []).filter(
      (variant) =>
        variant.bank_id === form.bankId &&
        variant.product_type_id === form.productTypeId,
    ),
    "product-variants",
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
      src: recordImageSrc("employee", person),
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
    if (prefilling || busy) return;
    const issue =
      step === 5
        ? [1, 2, 3, 4, 5]
            .map((index) => ({
              index,
              issue: caseCreateInvalidField(index, form, creditCard),
            }))
            .find((item) => item.issue)
        : {
            index: step,
            issue: caseCreateInvalidField(step, form, creditCard),
          };
    if (issue?.issue) {
      setStep(issue.index);
      setFieldError(issue.issue.field);
      setFieldMessage(issue.issue.message);
      setError(issue.issue.message);
      return;
    }
    if (
      (step === 3 || step === 5) &&
      creditCard &&
      (!eligibleReady ||
        !variantOptions.some(
          (option) => option.value === form.productVariantId,
        ))
    ) {
      setStep(3);
      setFieldError("productVariantId");
      setFieldMessage(
        "Load eligibility and select an eligible Variant before continuing.",
      );
      setError(
        "Load eligibility and select an eligible Variant before continuing.",
      );
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
            salaryAed: salary,
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
          if (field.field === "productVariantId") {
            setEligibility(null);
            setEligibilityAttempt((value) => value + 1);
          }
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
              disabled={busy || loading || prefilling}
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
                      options={namedOptions(products, "product-types")}
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
                          salaryAed: "",
                          productVariantId: "",
                        });
                      }}
                      options={[
                        { value: "Individual", label: "Individual" },
                        { value: "Company", label: "Company" },
                      ]}
                    />
                  </FormField>
                  <ExistingCustomerChoice
                    key={form.type}
                    type={form.type}
                    onSelect={prefill}
                    onBusy={setPrefilling}
                  />
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
                  {form.type === "Individual" ? (
                    <FormField
                      label="Customer salary (AED)"
                      htmlFor="case-create-salary"
                      required
                      error={
                        fieldError === "salaryAed" ? fieldMessage : undefined
                      }
                      hint={
                        creditCard
                          ? "Enter salary to load eligible Variants. Inclusive minimum and maximum; whole AED."
                          : "Salary is required and recorded for this Case. PF uses the manually entered amount, with no Variant or salary eligibility."
                      }
                    >
                      <CurrencyInput
                        id="case-create-salary"
                        compact
                        value={form.salaryAed}
                        inputMode="numeric"
                        onChange={(event) =>
                          patch({ salaryAed: event.target.value })
                        }
                        onBlur={(event) => {
                          const whole = roundWholeText(event.target.value);
                          if (
                            whole !== null &&
                            !event.target.value.trim().startsWith("-") &&
                            whole !== event.target.value
                          )
                            patch({ salaryAed: whole });
                        }}
                        invalid={fieldError === "salaryAed"}
                      />
                    </FormField>
                  ) : (
                    <p className={styles.support}>
                      Salary eligibility is not applicable to Company customers.
                    </p>
                  )}
                  {creditCard ? (
                    <FormField
                      label="Product Variant"
                      htmlFor="case-create-variant"
                      required
                      error={
                        fieldError === "productVariantId"
                          ? fieldMessage ||
                            "Select an eligible product variant."
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
                        disabled={!eligibilityQuery || !eligibleReady}
                        loading={Boolean(
                          eligibilityQuery &&
                          eligibility?.key !== eligibilityKey,
                        )}
                        placeholder={
                          !form.bankId
                            ? "Select a Bank first"
                            : form.type === "Individual" && !salaryValid
                              ? "Enter salary first"
                              : "Select Product Variant"
                        }
                        emptyLabel="No eligible Variants"
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
                  {creditCard && eligibilityQuery ? (
                    <div className={styles.support}>
                      {eligibility?.key !== eligibilityKey ? (
                        "Loading Variant eligibility…"
                      ) : eligibility.status === "error" ? (
                        <InlineNotice
                          tone="error"
                          title="Eligibility request failed"
                        >
                          {eligibility.error}{" "}
                          <Button
                            type="button"
                            size="compact"
                            variant="ghost"
                            onClick={() => {
                              setEligibility(null);
                              setEligibilityAttempt((value) => value + 1);
                            }}
                          >
                            Retry
                          </Button>
                        </InlineNotice>
                      ) : (
                        <>
                          {form.type === "Individual" &&
                          eligibility.data?.missingCriteriaCount ? (
                            <InlineNotice
                              tone="warning"
                              title="Missing salary criteria"
                            >
                              {eligibility.data.missingCriteriaCount} active
                              Variant(s) have no salary range and are excluded.
                              An authorized user must configure them in Settings
                              → Product Variants → Edit.
                            </InlineNotice>
                          ) : null}
                          {!eligibility.data?.items.length ? (
                            <p>
                              {eligibility.data?.totalVariantsCount === 0
                                ? "No active Variants for this Bank/Product."
                                : eligibility.data?.configuredCount === 0
                                  ? "No salary ranges are configured for this Bank/Product."
                                  : "No configured Variants match this salary."}
                            </p>
                          ) : null}
                        </>
                      )}
                    </div>
                  ) : null}
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
                    <InfoField
                      label="Case salary (AED)"
                      value={
                        form.type === "Individual" ? (
                          <MonetaryAmount
                            value={form.salaryAed}
                            compact={false}
                            align="start"
                          />
                        ) : (
                          "Not applicable"
                        )
                      }
                    />
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
