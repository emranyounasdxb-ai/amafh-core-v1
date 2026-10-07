import { roundWholeText } from "../../../app/numbers/wholeNumber.ts";

export const CASE_CREATE_STEPS = [
  { id: "product", label: "Add Case" },
  { id: "customer", label: "Customer details" },
  { id: "bank", label: "Bank & product" },
  { id: "owner", label: "Assign owner" },
  { id: "review", label: "Review" },
] as const;

export const CASE_CREATE_PERSONAL_LABELS: readonly string[] = [
  "Create Case",
  "Customer details",
  "Bank & product",
  "Case Owner",
  "Review",
];

export const CASE_CREATE_FIELD_LABELS: Record<string, string> = {
  productTypeId: "Product",
  type: "Customer type",
  fullName: "Full Name",
  nationality: "Nationality",
  emiratesId: "Emirates ID",
  passportNumber: "Passport",
  employer: "Employer",
  companyName: "Company Name",
  contactPerson: "Contact Person",
  tradeLicense: "Trade License",
  mobile: "UAE Mobile Number",
  email: "Email",
  bankId: "Bank",
  productVariantId: "Product Variant",
  requestedPfAmount: "Requested amount (AED)",
  salaryAed: "Customer salary (AED)",
  ownerEmployeeId: "Case Owner",
  confirmedInterest: "Customer interest",
  customer: "Customer",
};

export type CaseCreateValues = {
  type: "Individual" | "Company";
  productTypeId: string;
  bankId: string;
  productVariantId: string;
  ownerEmployeeId: string;
  fullName: string;
  nationality: string;
  emiratesId: string;
  passportNumber: string;
  employer: string;
  companyName: string;
  tradeLicense: string;
  contactPerson: string;
  mobile: string;
  email: string;
  requestedPfAmount: string;
  salaryAed: string;
  confirmedInterest: boolean;
};

export function emptyCaseCreateValues(
  ownerEmployeeId: string,
): CaseCreateValues {
  return {
    type: "Individual",
    productTypeId: "",
    bankId: "",
    productVariantId: "",
    ownerEmployeeId,
    fullName: "",
    nationality: "",
    emiratesId: "",
    passportNumber: "",
    employer: "",
    companyName: "",
    tradeLicense: "",
    contactPerson: "",
    mobile: "",
    email: "",
    requestedPfAmount: "",
    salaryAed: "",
    confirmedInterest: false,
  };
}

export function caseCreateRequiredField(
  step: number,
  values: CaseCreateValues,
  creditCard: boolean,
): string | null {
  if (step === 1) return values.productTypeId ? null : "productTypeId";
  if (step === 2) {
    if (values.type === "Individual") {
      if (!values.fullName) return "fullName";
      if (!values.nationality) return "nationality";
      if (!values.emiratesId) return "emiratesId";
      if (!values.passportNumber) return "passportNumber";
      if (!values.employer) return "employer";
    } else {
      if (!values.companyName) return "companyName";
      if (!values.contactPerson) return "contactPerson";
      if (!values.tradeLicense) return "tradeLicense";
    }
    if (!values.mobile) return "mobile";
    if (!values.email) return "email";
    return null;
  }
  if (step === 3) {
    if (!values.bankId) return "bankId";
    if (values.type === "Individual" && !values.salaryAed) return "salaryAed";
    return creditCard
      ? values.productVariantId
        ? null
        : "productVariantId"
      : values.requestedPfAmount
        ? null
        : "requestedPfAmount";
  }
  if (step === 4) return values.ownerEmployeeId ? null : "ownerEmployeeId";
  if (step === 5) return values.confirmedInterest ? null : "confirmedInterest";
  return null;
}

export function caseCreateInvalidField(
  step: number,
  values: CaseCreateValues,
  creditCard: boolean,
): { field: string; message: string } | null {
  if (step === 3 && values.type === "Individual" && values.salaryAed) {
    const salary = roundWholeText(values.salaryAed);
    if (
      salary === null ||
      values.salaryAed.trim().startsWith("-") ||
      BigInt(salary) < 0n ||
      salary.length > 18
    )
      return {
        field: "salaryAed",
        message:
          "Enter a non-negative salary in whole AED (at most 18 digits).",
      };
  }
  const required = caseCreateRequiredField(step, values, creditCard);
  if (required)
    return {
      field: required,
      message:
        required === "confirmedInterest"
          ? "Confirm customer interest before creating the Case."
          : `Complete ${CASE_CREATE_FIELD_LABELS[required] ?? "the required information"} before continuing.`,
    };
  if (step === 2) {
    if (
      values.type === "Individual" &&
      !/^[0-9 -]+$/.test(values.emiratesId.trim())
    )
      return {
        field: "emiratesId",
        message: "Emirates ID may contain only digits, spaces and hyphens.",
      };
    if (!/^\+?[0-9][0-9\s()-]*$/.test(values.mobile.trim()))
      return {
        field: "mobile",
        message: "Enter a mobile number containing digits, not letters.",
      };
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(values.email.trim()))
      return { field: "email", message: "Enter a valid email address." };
  }
  if (step === 3 && !creditCard) {
    const amount = roundWholeText(values.requestedPfAmount);
    if (amount === null || BigInt(amount) <= 0n)
      return {
        field: "requestedPfAmount",
        message: "Enter an amount greater than zero in AED.",
      };
  }
  return null;
}

export function caseCreateServerField(
  fieldErrors: Record<string, string[]>,
): { field: string; step: number; message: string } | null {
  for (const [path, messages] of Object.entries(fieldErrors)) {
    const field = path.replace(/^customer\./, "");
    if (!(field in CASE_CREATE_FIELD_LABELS)) continue;
    const step = ["productTypeId"].includes(field)
      ? 1
      : [
            "bankId",
            "productVariantId",
            "requestedPfAmount",
            "salaryAed",
          ].includes(field)
        ? 3
        : field === "ownerEmployeeId"
          ? 4
          : field === "confirmedInterest"
            ? 5
            : 2;
    return {
      field,
      step,
      message: `${CASE_CREATE_FIELD_LABELS[field]}: ${messages.join(" ")}`,
    };
  }
  return null;
}

export function formatCaseCreateFieldError(
  fieldErrors: Record<string, string[]>,
): string {
  return Object.entries(fieldErrors)
    .map(([key, messages]) => {
      const label = CASE_CREATE_FIELD_LABELS[key] ?? "Field";
      return `${label}: ${messages.join(" ")}`;
    })
    .join(" · ");
}

export function formatCaseCreateFailure(
  code: string,
  message: string,
  fieldErrors: Record<string, string[]>,
) {
  if (code === "CUSTOMER_IDENTITY_CONFLICT") {
    return "Emirates ID and Passport Number match different Customers. Ask the Owner to review the identity records.";
  }
  return [message, formatCaseCreateFieldError(fieldErrors)]
    .filter(Boolean)
    .join(" · ");
}
