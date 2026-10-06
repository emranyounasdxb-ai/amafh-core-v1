export type TargetRule = {
  branch: string;
  department: string;
  designation: string;
  product: "CC" | "PF";
  value: number;
  effectiveDate: string;
};
