export type FinancialRule = {
  bank: string;
  product: "CC" | "PF";
  variantOrSlab: string;
  points: number;
  commission: number;
  minimum: number | null;
  maximum: number | null;
  effectiveDate: string;
};
