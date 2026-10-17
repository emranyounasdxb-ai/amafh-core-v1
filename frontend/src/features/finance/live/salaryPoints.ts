import type { DataRecord } from "../../../app/api/models";

export type SalaryPoints = {
  salaryMin: string;
  salaryMax: string;
  points: number | string;
};

export function financialRulePayload(body: DataRecord): DataRecord {
  const { ccPointsMode, ...result } = body;
  if (result.productVariantId && ccPointsMode === "Salary ranges") {
    delete result.ccPoints;
    if (!Array.isArray(result.ccSalaryPoints) || !result.ccSalaryPoints.length)
      result.ccSalaryPoints = [{ salaryMin: "", salaryMax: "", points: "" }];
  } else {
    delete result.ccSalaryPoints;
  }
  return result;
}
