export type CustomerRow = {
  number: string;
  type: "Individual" | "Company";
  name: string;
  createdBranch: string;
  identityValue: string;
  identity: string;
  emiratesId?: string;
  passportNumber?: string;
  employer?: string;
  tradeLicense?: string;
  contactPerson?: string;
  email: string;
  mobile: string;
  cases: string;
};
