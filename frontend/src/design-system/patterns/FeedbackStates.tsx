import { Button } from "../components/Button";
import {
  ErrorState,
  FeedbackState,
  LoadingState,
  NoResultsState,
  NotFoundState,
  OfflineState,
  PermissionDeniedState,
  RetryState,
  UnavailableState,
} from "../components/FeedbackState";
import { EmptyState } from "../components/EmptyState";

export {
  FeedbackState,
  LoadingState,
  EmptyState,
  ErrorState,
  NoResultsState,
  NotFoundState,
  OfflineState,
  PermissionDeniedState,
  RetryState,
  UnavailableState,
};

export function FeedbackStates({
  kind,
  retry,
}: {
  kind:
    | "loading"
    | "empty"
    | "error"
    | "permission"
    | "unavailable"
    | "offline"
    | "no-results"
    | "not-found"
    | "retry"
    | "validation";
  retry?: () => void;
}) {
  if (kind === "loading") return <LoadingState />;
  if (kind === "error")
    return (
      <ErrorState
        description="The last request failed. Retained results were not replaced."
        retry={retry}
      />
    );
  if (kind === "offline") return <OfflineState />;
  if (kind === "no-results") return <NoResultsState />;
  if (kind === "permission") return <PermissionDeniedState />;
  if (kind === "not-found") return <NotFoundState />;
  if (kind === "retry")
    return (
      <RetryState
        retry={retry}
        secondary={
          retry ? (
            <Button variant="secondary" size="compact" onClick={retry}>
              Back
            </Button>
          ) : undefined
        }
      />
    );
  if (kind === "validation")
    return (
      <FeedbackState
        kind="validation"
        title="Check the highlighted fields"
        description="Validation messages stay next to their fields. This card is for section-level issues only."
      />
    );
  if (kind === "unavailable")
    return (
      <UnavailableState
        action={
          retry ? (
            <Button variant="secondary" size="compact" onClick={retry}>
              Back
            </Button>
          ) : undefined
        }
      />
    );
  return (
    <EmptyState
      title="No records"
      description="No authorized rows match the current filters."
    />
  );
}
