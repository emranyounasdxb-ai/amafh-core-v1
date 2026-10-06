import type { Designation } from "../../access";

// Session identity is supplied by /auth/me; cookies remain HttpOnly.
export type AuthenticatedSession = {
  employeeId: string;
  displayName: string;
  designation: Designation;
  branchId: string | null;
  departmentId: string | null;
  teamId: string | null;
  permissions: string[];
};

export interface SessionGateway {
  restore(): Promise<AuthenticatedSession | null>;
  signIn(credentials: {
    systemEmployeeCode: string;
    password: string;
  }): Promise<AuthenticatedSession>;
  signOut(): Promise<void>;
}

export type AuthorizedPage<T> = {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
};

export type ListQuery = {
  page: number;
  pageSize: 25 | 50 | 100 | "All";
  sort?: string;
  direction?: "asc" | "desc";
  filters?: Record<string, string>;
};

export type ReportExportRequest = {
  reportId: string;
  from: string;
  to: string;
  format: "CSV" | "PDF";
  filters: Record<string, string>;
};

export interface ReportExportGateway {
  generate(
    request: ReportExportRequest,
  ): Promise<{ file: Blob; fileName: string }>;
}
