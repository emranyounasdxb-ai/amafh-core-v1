import {
  branchField,
  departmentField,
  designationField,
  effectiveField,
  employeeSource,
  type Command,
  type Field,
} from "../../app/api/commands";
import { dubaiTodayDateOnly } from "../../design-system";

const reportingManagerDesignations = [
  "Owner",
  "Managing Director",
  "Sales Manager",
  "Team Leader",
];

/** Owner enrollment and reassignment are refused by the server outside the local command. */
const enrollableDesignations = [
  "Managing Director",
  "Sales Manager",
  "Coordinator",
  "Team Leader",
  "Sales Executive",
  "Admin Staff",
  "HR",
  "Finance",
];

function designationChoices(current?: string | null, isOwner = true): Field {
  const allowed = isOwner
    ? enrollableDesignations
    : enrollableDesignations.filter((name) => name !== "Managing Director");
  return {
    ...designationField,
    source: {
      ...designationField.source!,
      allowed: {
        name:
          current === "Owner" || (current === "HR" && !isOwner)
            ? [current]
            : allowed,
      },
    },
  };
}

export const profileFields: Field[] = [
  { key: "fullName", label: "Full name", required: true, section: "Personal" },
  {
    key: "nationality",
    label: "Nationality",
    required: true,
    control: "nationality",
    section: "Personal",
  },
  {
    key: "gender",
    label: "Gender",
    options: ["Male", "Female"],
    required: true,
    section: "Personal",
  },
  {
    key: "maritalStatus",
    label: "Marital status",
    options: ["Single", "Married"],
    required: true,
    section: "Personal",
  },
  { key: "mobile", label: "Mobile", required: true, section: "Contact" },
  {
    key: "personalEmail",
    label: "Personal email",
    type: "email",
    required: true,
    section: "Contact",
  },
  {
    key: "passportNumber",
    label: "Passport number",
    required: true,
    section: "Identity documents",
  },
  {
    key: "emiratesIdNumber",
    label: "Emirates ID",
    section: "Identity documents",
  },
];

const assignmentBranchField: Field = {
  ...branchField,
  clearOnChange: ["departmentId"],
};
const employeeDepartmentField: Field = {
  ...departmentField,
  choiceLabel: "departmentWithBranch",
};
const reportingManagerField: Field = {
  key: "reportingManagerId",
  label: "Reporting Manager",
  source: {
    ...employeeSource,
    allowed: { designation: reportingManagerDesignations },
  },
};

export function assignmentCommand(
  employee: {
    id: string;
    designation?: string | null;
  },
  isOwner = true,
): Command {
  const section = "Assignment";
  return {
    title: "Change assignment",
    path: `/employees/${employee.id}/assignments`,
    submitLabel: "Save assignment",
    fields: [
      { ...assignmentBranchField, section },
      { ...employeeDepartmentField, section },
      {
        ...designationChoices(employee.designation, isOwner),
        section,
        initialChoiceLabel: String(employee.designation || ""),
      },
      {
        ...reportingManagerField,
        section,
        source: {
          ...reportingManagerField.source!,
          exclude: [employee.id],
        },
      },
      { ...effectiveField, section, initial: dubaiTodayDateOnly() },
    ],
  };
}

export function profileCommand(
  employeeId: string,
  canChangeLoginEmail = true,
): Command {
  return {
    title: "Edit profile",
    path: `/employees/${employeeId}`,
    method: "PATCH",
    submitLabel: "Save profile",
    fields: canChangeLoginEmail
      ? profileFields
      : profileFields.filter((field) => field.key !== "personalEmail"),
  };
}

export function createEmployeeCommand(isOwner = true): Command {
  const employment = "Employment";
  const assignment = "Assignment";
  return {
    title: "Add Employee",
    path: "/employees",
    submitLabel: "Add employee",
    fields: [
      {
        key: "companyEmployeeCode",
        label: "Company Employee Code",
        required: true,
        section: employment,
      },
      {
        key: "dateOfJoining",
        label: "Joining date",
        type: "date",
        required: true,
        section: employment,
      },
      {
        ...designationChoices(undefined, isOwner),
        section: employment,
      },
      ...profileFields,
      {
        ...assignmentBranchField,
        required: false,
        section: assignment,
      },
      {
        ...employeeDepartmentField,
        required: false,
        section: assignment,
      },
      { ...reportingManagerField, section: assignment },
    ],
  };
}
