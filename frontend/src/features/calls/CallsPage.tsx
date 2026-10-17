import { useEffect, useRef, useState } from "react";
import {
  Button,
  CompactMonthYear,
  DataTable,
  EmptyState,
  ErrorState,
  InlineNotice,
  LoadingState,
  PageContainer,
  PageHeader,
  Pagination,
  RecordCount,
  SearchFilterToolbar,
  formatMonthYearFull,
  type StatusTone,
} from "../../design-system";
import { ApiFailure } from "../../app/api/http";
import { useSession } from "../../app/session/useSession";
import { CATALOG_POLL_MS, CATALOG_READY_POLL_MS, shouldPollCatalog } from "./catalogRefresh";
import "./calls.css";

type SourceView = {
  configured: boolean;
  phase: "not_configured" | "indexing" | "ready" | "offline" | "updating";
  lastIndexedAt: string | null;
  lastSynchronizedAt: string | null;
  catalogReady: boolean;
};

type Recording = {
  id: string;
  month: string;
  customerNumber: string;
  extension: string;
  filename: string;
};

type SearchResult = {
  month: string;
  customerNumber: string;
  page: number;
  pageSize: number;
  total: number;
  source: SourceView;
  recordings: Recording[];
};

const PHASE_LABEL: Record<SourceView["phase"], string> = {
  not_configured: "Not configured",
  indexing: "Indexing",
  ready: "Ready",
  offline: "Offline",
  updating: "Updating",
};

function phaseTone(phase: SourceView["phase"]): StatusTone {
  if (phase === "ready") return "success";
  if (phase === "offline") return "warning";
  if (phase === "indexing" || phase === "updating") return "info";
  return "neutral";
}

function sourceMessage(source: SourceView): string {
  if (source.phase === "not_configured" || !source.configured) {
    return "Calls is not configured.";
  }
  if (!source.catalogReady || source.phase === "indexing") {
    return "The recording index is still being prepared.";
  }
  if (source.phase === "updating") {
    return "The recording index is updating. Results below are from the last completed catalog.";
  }
  if (source.phase === "offline") {
    return "The recording source is offline. Results below are from the last synchronized catalog.";
  }
  return "";
}

function stopAudio(audio: HTMLAudioElement | null) {
  if (!audio) return;
  audio.pause();
  audio.removeAttribute("src");
  audio.load();
}

export function CallsPage() {
  const { api, session } = useSession();
  const audioRef = useRef<HTMLAudioElement>(null);
  const searchAbort = useRef<AbortController | null>(null);
  const refreshCatalog = useRef<() => void>(() => {});
  const requestId = useRef(0);
  const playId = useRef(0);
  const [source, setSource] = useState<SourceView | null>(null);
  const [months, setMonths] = useState<string[]>([]);
  const [month, setMonth] = useState("");
  const [customerNumber, setCustomerNumber] = useState("");
  const [pageSize, setPageSize] = useState(25);
  const [applied, setApplied] = useState<SearchResult | null>(null);
  const [pending, setPending] = useState(false);
  const [bootError, setBootError] = useState("");
  const [searchError, setSearchError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [selectedId, setSelectedId] = useState("");
  const [playingId, setPlayingId] = useState("");
  const [busy, setBusy] = useState(false);
  const [playError, setPlayError] = useState("");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshError, setRefreshError] = useState("");
  const sourceRef = useRef(source);
  useEffect(() => {
    sourceRef.current = source;
  }, [source]);

  useEffect(() => {
    const audio = audioRef.current;
    return () => {
      searchAbort.current?.abort();
      stopAudio(audio);
    };
  }, [session]);

  useEffect(() => {
    if (!session) return;
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let inflight = false;
    const controller = new AbortController();

    const schedule = () => {
      if (!active) return;
      const hidden = document.visibilityState === "hidden";
      if (!shouldPollCatalog(sourceRef.current, hidden)) return;
      const interval =
        sourceRef.current?.phase === "ready" ? CATALOG_READY_POLL_MS : CATALOG_POLL_MS;
      timer = setTimeout(pull, interval);
    };

    const pull = () => {
      if (!active || inflight) return;
      inflight = true;
      setRefreshing(sourceRef.current !== null);
      api
        .request<{ months: string[]; source: SourceView }>("/calls/months", {
          signal: controller.signal,
        })
        .then((payload) => {
          if (!active) return;
          sourceRef.current = payload.source;
          setSource(payload.source);
          setMonths(payload.months);
          setMonth((current) =>
            current && payload.months.includes(current) ? current : payload.months[0] || "",
          );
          setBootError("");
          setRefreshError("");
        })
        .catch((error: unknown) => {
          if (!active || (error instanceof DOMException && error.name === "AbortError")) return;
          const message = error instanceof ApiFailure ? error.message : "Calls could not be loaded.";
          if (sourceRef.current) setRefreshError(message);
          else setBootError(message);
        })
        .finally(() => {
          inflight = false;
          if (active) setRefreshing(false);
          schedule();
        });
    };

    refreshCatalog.current = () => {
      if (timer) clearTimeout(timer);
      pull();
    };
    const onVisibility = () => {
      if (document.visibilityState === "hidden") {
        if (timer) clearTimeout(timer);
        return;
      }
      if (shouldPollCatalog(sourceRef.current, false)) {
        if (timer) clearTimeout(timer);
        pull();
      }
    };
    document.addEventListener("visibilitychange", onVisibility);
    pull();
    return () => {
      active = false;
      refreshCatalog.current = () => {};
      if (timer) clearTimeout(timer);
      controller.abort();
      document.removeEventListener("visibilitychange", onVisibility);
    };
  }, [api, session]);

  async function search(page: number, size: number, nextMonth: string, phone: string) {
    const id = requestId.current + 1;
    requestId.current = id;
    searchAbort.current?.abort();
    const controller = new AbortController();
    searchAbort.current = controller;
    setPending(true);
    setSearchError("");
    setFieldError("");
    try {
      const result = await api.request<SearchResult>("/calls/search", {
        method: "POST",
        body: JSON.stringify({
          month: nextMonth,
          customerNumber: phone,
          page,
          pageSize: size,
        }),
        signal: controller.signal,
      });
      if (id !== requestId.current) return;
      setSource(result.source);
      if (!result.source.configured || !result.source.catalogReady) return;
      setApplied(result);
    } catch (error: unknown) {
      if (id !== requestId.current) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (error instanceof ApiFailure) {
        setFieldError(error.fieldErrors.customerNumber?.[0] ?? error.fieldErrors.month?.[0] ?? "");
        setSearchError(error.message);
        return;
      }
      setSearchError("The search could not be completed.");
    } finally {
      if (id === requestId.current) setPending(false);
    }
  }

  function submit(page = 1) {
    void search(page, pageSize, month, customerNumber);
  }

  async function play(row: Recording) {
    const audio = audioRef.current;
    if (!audio) return;
    const id = playId.current + 1;
    playId.current = id;
    stopAudio(audio);
    setSelectedId(row.id);
    setPlayingId("");
    setBusy(true);
    setPlayError("");
    const url = `/api/v1/calls/recordings/${row.id}/stream`;
    try {
      const head = await fetch(url, { method: "HEAD", credentials: "include" });
      if (id !== playId.current) return;
      if (head.status === 401 || head.status === 403) {
        setApplied(null);
        setSelectedId("");
        setBusy(false);
        return;
      }
      if (head.status === 409) {
        setPlayError("This recording changed. Search again.");
        setBusy(false);
        return;
      }
      if (head.status === 404) {
        setPlayError("This recording is no longer available.");
        setBusy(false);
        return;
      }
      if (!head.ok) {
        setPlayError("The recording source is offline.");
        setBusy(false);
        return;
      }
      audio.src = url;
      audio.load();
      await audio.play();
      if (id !== playId.current) return;
      setPlayingId(row.id);
      setBusy(false);
    } catch {
      if (id !== playId.current) return;
      setBusy(false);
      setPlayError("This recording cannot be played in the browser. Use Download.");
    }
  }

  function download(row: Recording) {
    const link = document.createElement("a");
    link.href = `/api/v1/calls/recordings/${row.id}/download`;
    link.download = row.filename;
    document.body.appendChild(link);
    link.click();
    link.remove();
  }

  const signedIn = session !== null;
  const visible = signedIn ? applied : null;
  const visibleSelected = signedIn ? selectedId : "";
  const visiblePlaying = signedIn ? playingId : "";
  const notice = source ? sourceMessage(source) : "";
  const pageCount = visible ? Math.max(1, Math.ceil(visible.total / visible.pageSize)) : 1;

  return (
    <PageContainer>
      <PageHeader
        title="Calls"
        subtitle="Find mobile, landline and internal calls by exact number in the selected month."
        status={source ? PHASE_LABEL[source.phase] : undefined}
        statusTone={source ? phaseTone(source.phase) : "neutral"}
      />
      {bootError ? (
        <ErrorState description={bootError} retry={() => refreshCatalog.current()} />
      ) : null}
      {!source && !bootError ? (
        <LoadingState title="Loading Calls" description="Checking the recording catalog." />
      ) : null}
      {notice ? (
        <InlineNotice tone={source?.phase === "offline" ? "warning" : "info"}>{notice}</InlineNotice>
      ) : null}
      {refreshError ? <InlineNotice tone="warning">{refreshError}</InlineNotice> : null}
      {searchError ? <InlineNotice tone="error">{fieldError || searchError}</InlineNotice> : null}
      <div
        onKeyDown={(event) => {
          if (event.key === "Enter" && event.target instanceof HTMLInputElement) {
            event.preventDefault();
            submit(1);
          }
        }}
      >
        <SearchFilterToolbar
          searchId="calls-customer-number"
          searchLabel="Phone number or extension"
          searchPlaceholder="Full phone number or extension"
          searchValue={customerNumber}
          onSearchChange={setCustomerNumber}
          disabled={!source?.catalogReady}
          filters={[
            {
              id: "calls-month",
              label: "Month",
              value: month,
              options: months.map((item) => ({
                value: item,
                label: formatMonthYearFull(item),
              })),
              onChange: setMonth,
              disabled: months.length === 0,
            },
          ]}
          actions={
            <span className="calls-actions">
              <Button
                size="compact"
                variant="secondary"
                loading={refreshing}
                onClick={() => refreshCatalog.current()}
              >
                Refresh
              </Button>
              <Button size="compact" loading={pending} disabled={!month} onClick={() => submit(1)}>
                Search
              </Button>
            </span>
          }
        />
      </div>
      {visible ? (
        <>
          <InlineNotice>
            Showing {visible.total} {visible.total === 1 ? "match" : "matches"} for{" "}
            {visible.customerNumber} in <CompactMonthYear value={visible.month} />
            {pending ? " Searching…" : ""}
          </InlineNotice>
          <RecordCount count={visible.total} />
          {visible.total === 0 ? (
            <EmptyState
              title="No recordings"
              description="No recordings match this exact phone number or extension in the selected month."
            />
          ) : (
            <DataTable
              ariaLabel="Call recordings"
              density="compact"
              rowKey={(row) => row.id}
              rows={visible.recordings}
              columns={[
                {
                  key: "month",
                  header: "Month",
                  kind: "text",
                  render: (row) => <CompactMonthYear value={row.month} />,
                },
                {
                  key: "extension",
                  header: "Number 1",
                  kind: "text",
                  render: (row) => row.extension,
                },
                {
                  key: "customerNumber",
                  header: "Number 2",
                  kind: "text",
                  render: (row) => row.customerNumber,
                },
                {
                  key: "filename",
                  header: "Filename",
                  kind: "text",
                  render: (row) => row.filename,
                },
                {
                  key: "actions",
                  header: "Actions",
                  kind: "text",
                  render: (row) => (
                    <span className="calls-actions">
                      <Button
                        size="compact"
                        variant={visiblePlaying === row.id ? "primary" : "secondary"}
                        aria-pressed={visibleSelected === row.id}
                        onClick={() => void play(row)}
                      >
                        {visiblePlaying === row.id
                          ? "Playing"
                          : busy && visibleSelected === row.id
                            ? "Opening"
                            : "Play"}
                      </Button>
                      <Button size="compact" variant="secondary" onClick={() => download(row)}>
                        Download
                      </Button>
                    </span>
                  ),
                },
              ]}
            />
          )}
          <Pagination
            page={visible.page}
            pageCount={pageCount}
            pageSize={visible.pageSize}
            pageSizeOptions={[25, 50]}
            onPageChange={(page) =>
              void search(page, visible.pageSize, visible.month, visible.customerNumber)
            }
            onPageSizeChange={(size) => {
              setPageSize(size);
              void search(1, size, visible.month, visible.customerNumber);
            }}
          />
        </>
      ) : null}
      <section className="calls-player" aria-label="Recording player">
        {playError ? <InlineNotice tone="error">{playError}</InlineNotice> : null}
        {visibleSelected ? (
          <InlineNotice>
            {busy
              ? "Opening the selected recording."
              : visiblePlaying
                ? "Playing the selected recording."
                : "Selected recording."}
          </InlineNotice>
        ) : null}
        <audio
          ref={audioRef}
          controls
          preload="none"
          aria-label="Selected recording"
          onWaiting={() => setBusy(true)}
          onPlaying={() => setBusy(false)}
          onError={() => {
            setBusy(false);
            setPlayingId("");
            setPlayError("This recording cannot be played in the browser. Use Download.");
          }}
        />
      </section>
    </PageContainer>
  );
}
