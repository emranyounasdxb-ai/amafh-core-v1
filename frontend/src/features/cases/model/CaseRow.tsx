import type { CaseHistoryEvent } from "./CaseHistoryEvent";

export type CaseRow = {
  id: string;
  customer: string;
  customerNumber: string;
  product: "CC" | "PF";
  bank: string;
  variant: string;
  createdBy: string;
  owner: string;
  coordinator: string;
  branch: string;
  status:
    | "Pending for Approval"
    | "Approved"
    | "Booked"
    | "Completed"
    | "Rejected"
    | "Case Reopened by Owner";
  bankRef: string;
  stage: string;
  remarks: string;
  date: string;
  history: CaseHistoryEvent[];
};
