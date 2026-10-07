import { useEffect, useState } from "react";
import {
  Button,
  Combobox,
  FormField,
  InlineNotice,
  useDebouncedValue,
} from "../../../design-system";
import type { Page } from "../../../app/api/models";
import { useSession } from "../../../app/session/useSession";
import type { CustomerListRecord } from "../../customers/live/customerListPresentation";
import type { CustomerDetailRecord } from "../../customers/live/customerDetailPresentation";

/** Offers only Customers already visible through the requester's Case scope. */
export function ExistingCustomerChoice({
  type,
  onSelect,
  onBusy,
}: {
  type: "Individual" | "Company";
  onSelect: (customer: CustomerDetailRecord) => void;
  onBusy: (busy: boolean) => void;
}) {
  const { api } = useSession();
  const [query, setQuery] = useState("");
  const term = useDebouncedValue(query, 250);
  const [picked, setPicked] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [list, setList] = useState<{
    key: string;
    rows?: CustomerListRecord[];
    error?: string;
  } | null>(null);
  const [detail, setDetail] = useState<{
    key: string;
    customer?: CustomerDetailRecord;
    error?: string;
  } | null>(null);
  const path = `/case-customer-choices?${new URLSearchParams({ type, q: term, pageSize: "25" })}`;
  const listKey = `${path}:${attempt}`;
  const detailKey = `${picked}:${attempt}`;
  useEffect(() => {
    const controller = new AbortController();
    api
      .request<Page<CustomerListRecord>>(path, { signal: controller.signal })
      .then((page) => {
        if (!Array.isArray(page.items))
          throw new Error(
            "Invalid Customer choices response. Retry loading Customers.",
          );
        if (!controller.signal.aborted)
          setList({ key: listKey, rows: page.items });
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setList({
            key: listKey,
            error:
              failure instanceof Error
                ? failure.message
                : "Customers could not be loaded.",
          });
      });
    return () => controller.abort();
  }, [api, path, listKey]);
  useEffect(() => {
    if (!picked) return;
    const controller = new AbortController();
    api
      .request<CustomerDetailRecord>(`/customers/${picked}`, {
        signal: controller.signal,
      })
      .then((customer) => {
        if (controller.signal.aborted) return;
        setDetail({ key: detailKey, customer });
        onSelect(customer);
        onBusy(false);
      })
      .catch((failure: unknown) => {
        if (controller.signal.aborted) return;
        setDetail({
          key: detailKey,
          error:
            failure instanceof Error
              ? failure.message
              : "Customer could not be loaded.",
        });
        onBusy(false);
      });
    return () => controller.abort();
  }, [api, picked, detailKey, onSelect, onBusy]);
  useEffect(() => () => onBusy(false), [onBusy]);
  const rows = list?.key === listKey ? (list.rows ?? []) : [];
  const selection = detail?.customer;
  const options = rows.map((row) => ({
    value: row.id,
    label: `${row.name || row.customerId} · ${row.customerId}`,
  }));
  if (selection && !options.some((option) => option.value === selection.id))
    options.push({ value: selection.id, label: selection.customerId });
  const error =
    (list?.key === listKey ? list.error : "") ||
    (picked && detail?.key === detailKey ? detail.error : "");
  const loading =
    list?.key !== listKey || Boolean(picked && detail?.key !== detailKey);
  return (
    <>
      <FormField
        label="Existing Customer (optional)"
        htmlFor="case-create-existing-customer"
        hint="Search an authorized Customer to load saved details, nationality and salary, or enter a new Customer below."
      >
        <Combobox
          id="case-create-existing-customer"
          compact
          options={options}
          value={picked}
          onChange={(id) => {
            if (id === picked) return;
            onBusy(Boolean(id));
            setPicked(id);
          }}
          query={query}
          onQueryChange={setQuery}
          loading={loading}
          unavailable={Boolean(error)}
          placeholder="Search existing Customers"
          emptyLabel="No authorized Customers match this search"
        />
      </FormField>
      {error ? (
        <InlineNotice tone="error" title="Customer request failed">
          {error}{" "}
          <Button
            type="button"
            size="compact"
            variant="ghost"
            onClick={() => {
              onBusy(Boolean(picked));
              setAttempt((value) => value + 1);
            }}
          >
            Retry
          </Button>
        </InlineNotice>
      ) : null}
    </>
  );
}
