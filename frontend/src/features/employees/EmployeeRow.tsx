import type { AssignmentHistoryEntry } from "./AssignmentHistoryEntry";

export type EmployeeRow = {
  code: string;
  name: string;
  avatar: string;
  gender: string;
  nationality: string;
  countryCode?: string;
  maritalStatus?: string;
  emiratesId?: string;
  flag: string;
  branch: string;
  department: string;
  designation: string;
  employment: "Pending Setup" | "Active" | "Offboarded";
  access: "Not Provisioned" | "Active" | "Disabled";
  mobile: string;
  email: string;
  passport: string;
  joiningDate: string;
  assignmentHistory: AssignmentHistoryEntry[];
};
