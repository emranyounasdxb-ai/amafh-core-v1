import type { CustomerRow } from "./CustomerRow";

export type CustomerIdentity =
  | { type: "Individual"; emiratesId: string; passportNumber: string }
  | { type: "Company"; tradeLicense: string };

export type CustomerMatch =
  | { kind: "new" }
  | { kind: "match"; customer: CustomerRow }
  | {
      kind: "conflict";
      emiratesIdCustomer: CustomerRow;
      passportCustomer: CustomerRow;
    };

const normalize = (value: string) => value.trim().toLocaleUpperCase("en");
const normalizeEmiratesId = (value: string) => value.replace(/\D/g, "");

export function resolveCustomerIdentity(
  customers: readonly CustomerRow[],
  identity: CustomerIdentity,
): CustomerMatch {
  if (identity.type === "Company") {
    const license = normalize(identity.tradeLicense);
    const customer = customers.find(
      (item) =>
        item.type === "Company" &&
        normalize(item.tradeLicense ?? item.identityValue) === license,
    );
    return customer ? { kind: "match", customer } : { kind: "new" };
  }

  const emiratesId = normalizeEmiratesId(identity.emiratesId);
  const passportNumber = normalize(identity.passportNumber);
  const individuals = customers.filter((item) => item.type === "Individual");
  const byEmiratesId = individuals.find(
    (item) =>
      normalizeEmiratesId(item.emiratesId ?? item.identityValue) === emiratesId,
  );
  const byPassport = individuals.find((item) => {
    const recordedPassport =
      item.passportNumber ??
      item.identity.match(/Passport\s+([^·\s]+)/i)?.[1] ??
      "";
    return normalize(recordedPassport) === passportNumber;
  });
  if (byEmiratesId && byPassport && byEmiratesId.number !== byPassport.number) {
    return {
      kind: "conflict",
      emiratesIdCustomer: byEmiratesId,
      passportCustomer: byPassport,
    };
  }
  const customer = byEmiratesId ?? byPassport;
  return customer ? { kind: "match", customer } : { kind: "new" };
}
