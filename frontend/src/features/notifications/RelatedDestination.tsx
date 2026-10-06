import { useState } from "react";
import type { PageId } from "../../access";
import { useSession } from "../../app/session/useSession";
import {
  apiPathFromDestination,
  routeFromApiPath,
} from "../../app/navigation/destinationRoute";
import { useResource } from "../../app/api/useResource";
import type { DataRecord } from "../../app/api/models";
import { relatedRecordFields } from "../../app/presentation/labels";
import {
  Button,
  InfoField,
  InfoGrid,
  InlineNotice,
  LoadingState,
  UnavailableState,
} from "../../design-system";

export function RelatedDestination({
  endpoint,
  onOpen,
}: {
  endpoint: string;
  onOpen: (page: PageId, recordId?: string) => void;
}) {
  const { api, session } = useSession();
  const [path, setPath] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [route, setRoute] = useState<{
    page: PageId;
    recordId?: string;
  } | null>(null);
  const apiPath = path ? apiPathFromDestination(path) : "";
  const record = useResource<DataRecord>(apiPath || null);
  const resolve = async () => {
    setError("");
    setPath("");
    setRoute(null);
    setBusy(true);
    try {
      const result = await api.request<{ path: string }>(endpoint);
      if (!result.path.startsWith("/api/v1/"))
        throw new Error("Record unavailable");
      setPath(result.path);
      setRoute(
        session
          ? routeFromApiPath(result.path, session)
          : null,
      );
    } catch (failure) {
      setError(
        failure instanceof Error ? failure.message : "Record unavailable",
      );
    } finally {
      setBusy(false);
    }
  };
  const fields =
    record.data && !Array.isArray(record.data)
      ? relatedRecordFields(record.data)
      : [];
  return (
    <>
      <Button
        variant="secondary"
        loading={busy}
        onClick={() => void resolve()}
      >
        Open related record
      </Button>
      {error ? <UnavailableState title={error} /> : null}
      {path && !record.denied && record.loading ? <LoadingState /> : null}
      {path && record.denied ? (
        <UnavailableState title="Record unavailable" />
      ) : null}
      {fields.length ? (
        <InfoGrid>
          {fields.map((field) => (
            <InfoField
              key={field.key}
              label={field.label}
              value={field.value}
            />
          ))}
        </InfoGrid>
      ) : null}
      {record.error && path ? (
        <InlineNotice tone="error">{record.error}</InlineNotice>
      ) : null}
      {route ? (
        <Button
          variant="secondary"
          onClick={() => onOpen(route.page, route.recordId)}
        >
          Go to record
        </Button>
      ) : null}
    </>
  );
}
