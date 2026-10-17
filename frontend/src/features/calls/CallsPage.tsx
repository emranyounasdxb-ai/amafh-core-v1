import { useEffect, useRef, useState } from "react";
import {
  Button,
  CompactMonthYear,
  DataTable,
  DsIcon,
  DropdownSelect,
  EmptyState,
  ErrorState,
  InlineNotice,
  LoadingState,
  PageContainer,
  PageHeader,
  Pagination,
  SectionCard,
  StatusBadge,
  formatMonthYearFull,
  type StatusTone,
} from "../../design-system";
import { ApiFailure } from "../../app/api/http";
import { useSession } from "../../app/session/useSession";
import {
  CATALOG_POLL_MS,
  CATALOG_READY_POLL_MS,
  shouldPollCatalog,
} from "./catalogRefresh";
import { CallsNumberSearch } from "./CallsNumberSearch";
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
    return source.catalogReady
      ? "More recordings are being added. You can search the available calls now."
      : "Your recording library is being prepared. Available months will appear here automatically.";
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
  const [applied, setApplied] = useState<
    (SearchResult & { owner: typeof session }) | null
  >(null);
  const [pending, setPending] = useState(false);
  const [bootError, setBootError] = useState("");
  const [searchError, setSearchError] = useState("");
  const [fieldError, setFieldError] = useState("");
  const [selectedRecording, setSelectedRecording] = useState<{
    owner: typeof session;
    row: Recording;
  } | null>(null);
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
      requestId.current += 1;
      playId.current += 1;
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
        sourceRef.current?.phase === "ready"
          ? CATALOG_READY_POLL_MS
          : CATALOG_POLL_MS;
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
            current && payload.months.includes(current)
              ? current
              : payload.months[0] || "",
          );
          setBootError("");
          setRefreshError("");
        })
        .catch((error: unknown) => {
          if (
            !active ||
            (error instanceof DOMException && error.name === "AbortError")
          )
            return;
          const message =
            error instanceof ApiFailure
              ? error.message
              : "Calls could not be loaded.";
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

  async function search(
    page: number,
    size: number,
    nextMonth: string,
    phone: string,
  ) {
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
      setApplied({ ...result, owner: session });
    } catch (error: unknown) {
      if (id !== requestId.current) return;
      if (error instanceof DOMException && error.name === "AbortError") return;
      if (error instanceof ApiFailure) {
        setFieldError(
          error.fieldErrors.customerNumber?.[0] ??
            error.fieldErrors.month?.[0] ??
            "",
        );
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
    setSelectedRecording({ owner: session, row });
    setPlayingId("");
    setBusy(true);
    setPlayError("");
    const url = `/api/v1/calls/recordings/${row.id}/stream`;
    try {
      const head = await fetch(url, { method: "HEAD", credentials: "include" });
      if (id !== playId.current) return;
      if (head.status === 401 || head.status === 403) {
        setApplied(null);
        setSelectedRecording(null);
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
      setPlayError(
        "This recording cannot be played in the browser. Use Download.",
      );
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
  const visible = signedIn && applied?.owner === session ? applied : null;
  const visibleRecording =
    signedIn && selectedRecording?.owner === session
      ? selectedRecording.row
      : null;
  const visibleSelected = visibleRecording?.id ?? "";
  const visiblePlaying = visibleRecording ? playingId : "";
  const notice = source ? sourceMessage(source) : "";
  const pageCount = visible
    ? Math.max(1, Math.ceil(visible.total / visible.pageSize))
    : 1;

  return (
    <PageContainer className="calls-page">
      <PageHeader
        title="Calls"
        subtitle="Find, listen to and download your call recordings."
        status={source ? PHASE_LABEL[source.phase] : undefined}
        statusTone={source ? phaseTone(source.phase) : "neutral"}
      />
      {bootError ? (
        <ErrorState
          description={bootError}
          retry={() => refreshCatalog.current()}
        />
      ) : null}
      {!source && !bootError ? (
        <LoadingState
          title="Loading Calls"
          description="Checking the recording catalog."
        />
      ) : null}
      {notice ? (
        <InlineNotice tone={source?.phase === "offline" ? "warning" : "info"}>
          {notice}
        </InlineNotice>
      ) : null}
      {refreshError ? (
        <InlineNotice tone="warning">{refreshError}</InlineNotice>
      ) : null}
      {searchError ? (
        <InlineNotice tone="error">{fieldError || searchError}</InlineNotice>
      ) : null}
      <SectionCard
        className="calls-search-card"
        title="Find a recording"
        description="Choose a month, then search a mobile number, landline or internal extension."
        actions={
          <span className="calls-library-count">
            <DsIcon name="calendar" size={16} />
            {months.length} {months.length === 1 ? "month" : "months"} available
          </span>
        }
      >
        <form
          className="calls-search-form"
          onSubmit={(event) => {
            event.preventDefault();
            submit(1);
          }}
        >
          <div className="calls-month-field">
            <label className="ds-field__label" htmlFor="calls-month">
              Recording month
            </label>
            <DropdownSelect
              id="calls-month"
              label="Month"
              compact
              clearable={false}
              value={month}
              disabled={!source?.catalogReady || !months.length}
              options={months.map((item) => ({
                value: item,
                label: formatMonthYearFull(item),
              }))}
              onChange={(value) => setMonth(String(value))}
            />
          </div>
          <CallsNumberSearch
            month={month}
            value={customerNumber}
            disabled={!source?.catalogReady || !month}
            onChange={setCustomerNumber}
            onSelect={(phone) => {
              void search(1, pageSize, month, phone);
            }}
          />
          <div className="calls-search-buttons calls-actions">
            <Button
              size="compact"
              type="submit"
              loading={pending}
              disabled={!month || !customerNumber.trim()}
            >
              <DsIcon name="search" size={16} /> Search calls
            </Button>
            <Button
              size="compact"
              variant="secondary"
              loading={refreshing}
              onClick={() => refreshCatalog.current()}
            >
              <DsIcon name="refresh" size={16} /> Refresh
            </Button>
          </div>
        </form>
      </SectionCard>
      <div className="calls-workspace">
        <SectionCard
          className="calls-results-card"
          title="Recordings"
          description={
            visible ? (
              <>
                {visible.customerNumber} · {formatMonthYearFull(visible.month)}
              </>
            ) : (
              "Your matching calls will appear here."
            )
          }
          actions={
            visible ? (
              <StatusBadge tone="brand">
                {visible.total}{" "}
                {visible.total === 1 ? "recording" : "recordings"}
              </StatusBadge>
            ) : undefined
          }
        >
          {pending ? (
            <div className="calls-results-status" role="status">
              Searching recordings…
            </div>
          ) : null}
          {visible ? (
            <>
              {visible.total === 0 ? (
                <EmptyState
                  title="No recordings"
                  description="No recordings match this exact phone number or extension in the selected month."
                />
              ) : (
                <DataTable
                  ariaLabel="Call recordings"
                  className="calls-recording-table"
                  density="compact"
                  rowKey={(row) => row.id}
                  rows={visible.recordings}
                  columns={[
                    {
                      key: "extension",
                      header: "Number 1",
                      kind: "text",
                      width: "130px",
                      minWidth: 110,
                      render: (row) => (
                        <span className="calls-number">{row.extension}</span>
                      ),
                    },
                    {
                      key: "customerNumber",
                      header: "Number 2",
                      kind: "text",
                      width: "160px",
                      minWidth: 130,
                      render: (row) => (
                        <span className="calls-number">
                          {row.customerNumber}
                        </span>
                      ),
                    },
                    {
                      key: "filename",
                      header: "Recording file",
                      kind: "text",
                      width: "240px",
                      render: (row) => (
                        <span className="calls-file" title={row.filename}>
                          <DsIcon name="pdf" size={16} />
                          <span>{row.filename}</span>
                        </span>
                      ),
                    },
                    {
                      key: "actions",
                      header: "Actions",
                      kind: "text",
                    width: "240px",
                    minWidth: 230,
                      render: (row) => (
                        <span className="calls-actions">
                          <Button
                            size="compact"
                            variant={
                              visiblePlaying === row.id
                                ? "primary"
                                : "secondary"
                            }
                            aria-pressed={visibleSelected === row.id}
                            onClick={() => void play(row)}
                          >
                            <DsIcon name="phone" size={14} />
                            {visiblePlaying === row.id
                              ? "Playing"
                              : busy && visibleSelected === row.id
                                ? "Opening"
                                : "Play"}
                          </Button>
                          <Button
                            size="compact"
                            variant="secondary"
                            onClick={() => download(row)}
                          >
                            <DsIcon name="download" size={14} /> Download
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
                  void search(
                    page,
                    visible.pageSize,
                    visible.month,
                    visible.customerNumber,
                  )
                }
                onPageSizeChange={(size) => {
                  setPageSize(size);
                  void search(1, size, visible.month, visible.customerNumber);
                }}
              />
            </>
          ) : !pending ? (
            <div className="calls-results-empty">
              <span className="calls-empty-icon">
                <DsIcon name="phone" size={24} />
              </span>
              <h3>Find the conversation you need</h3>
              <p>
                Select a month and enter a number above.
                <br />
                Choose a matching number to see its recordings.
              </p>
            </div>
          ) : null}
        </SectionCard>
        <aside
          className={`calls-player-aside${visibleRecording ? " calls-player-aside--selected" : ""}`}
          aria-label="Recording player"
        >
          <SectionCard
            className="calls-player"
            title="Recording player"
            description="Listen here or save a copy."
            actions={
              visiblePlaying && !busy ? (
                <StatusBadge tone="success">Playing</StatusBadge>
              ) : undefined
            }
          >
            <div className="calls-player-art" aria-hidden="true">
              <span>
                <DsIcon name="phone" size={24} />
              </span>
              <div className="calls-audio-bars">
                {[14, 26, 38, 22, 46, 32, 18, 40, 28, 16, 34, 22].map(
                  (height, index) => (
                    <i key={index} style={{ height }} />
                  ),
                )}
              </div>
            </div>
            {playError ? (
              <InlineNotice tone="error">{playError}</InlineNotice>
            ) : null}
            {visibleRecording ? (
              <div className="calls-selected-details">
                <div className="calls-player-title">
                  {busy ? "Opening recording…" : "Selected recording"}
                </div>
                <div className="calls-participant-pair">
                  <strong>{visibleRecording.extension}</strong>
                  <span>·</span>
                  <strong>{visibleRecording.customerNumber}</strong>
                </div>
                <p>
                  <DsIcon name="calendar" size={14} />
                  <CompactMonthYear value={visibleRecording.month} />
                </p>
                <div
                  className="calls-selected-filename"
                  title={visibleRecording.filename}
                >
                  {visibleRecording.filename}
                </div>
              </div>
            ) : (
              <div className="calls-player-placeholder">
                <h3>No recording selected</h3>
                <p>Choose Play beside a recording to start listening.</p>
              </div>
            )}
            <audio
              ref={audioRef}
              controls
              hidden={!visibleRecording}
              preload="none"
              aria-label="Selected recording"
              onWaiting={() => setBusy(true)}
              onPlaying={() => {
                setBusy(false);
                if (visibleRecording) setPlayingId(visibleRecording.id);
              }}
              onPause={() => setPlayingId("")}
              onEnded={() => setPlayingId("")}
              onError={() => {
                if (!visibleRecording) return;
                setBusy(false);
                setPlayingId("");
                setPlayError(
                  "This recording cannot be played in the browser. Use Download.",
                );
              }}
            />
            {visibleRecording ? (
              <Button
                variant="secondary"
                onClick={() => download(visibleRecording)}
              >
                <DsIcon name="download" size={16} />
                Download recording
              </Button>
            ) : null}
            <div className="calls-player-footer">
              <DsIcon name="locked" size={14} />
              Original recordings are kept unchanged.
            </div>
          </SectionCard>
        </aside>
      </div>
    </PageContainer>
  );
}
