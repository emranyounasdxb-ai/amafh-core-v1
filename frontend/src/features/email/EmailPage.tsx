import { useEffect, useRef, useState } from "react";
import type { PageId } from "../../access";
import { ApiFailure } from "../../app/api/http";
import { useSession } from "../../app/session/useSession";
import {
  Button,
  CompactDateTime,
  Dialog,
  DsIcon,
  type DsIconName,
  EmptyState,
  ErrorState,
  FileUpload,
  FormField,
  InlineNotice,
  LoadingState,
  PageContainer,
  PageHeader,
  PasswordInput,
  ReadOnlyField,
  RetryState,
  SectionCard,
  TextInput,
  UnavailableState,
} from "../../design-system";
import {
  MAIL_DOCUMENT_STYLE,
  mailDate,
  mailIdentity,
  mailPreview,
} from "./presentation";
import "./email.css";
import { EmailSplitPane } from "./EmailSplitPane";
import { MailViewCache } from "./viewCache";

type FolderRole = "inbox" | "drafts" | "sent" | "deleted" | "spam" | "archive";

type Connection = {
  address: string;
  connected: boolean;
  reconnectRequired: boolean;
};

type Limits = {
  attachmentBytes: number;
  attachmentsBytes: number;
  effectiveMessageBytes: number;
  refreshSeconds: number;
};

type MailRow = {
  ref: string;
  subject: string;
  sender: string;
  recipients: string;
  preview: string;
  date: string | null;
  unread: boolean;
  hasAttachment: boolean;
};

type MailPage = {
  items: MailRow[];
  total: number;
  page: number;
  pageSize: number;
  folder: string;
  appOnlyDeleted: boolean;
  syncState?: "initial" | "updating" | "ready" | "failed" | "offline";
  syncedAt?: string | null;
};

type MailMessage = MailRow & {
  html: string;
  cc: string;
  bcc: string;
  attachments: {
    index: number;
    filename: string;
    contentType: string;
    size: number;
  }[];
  messageId: string;
  replyTo: string;
  references?: string;
};

type ComposeFile = {
  id?: string;
  remoteIndex?: number;
  filename: string;
  size: number;
};

type SendResult = {
  status: string;
  detail: string;
  accepted?: string[];
  refused?: string[];
};

const ROLE: Record<string, FolderRole> = {
  "email-inbox": "inbox",
  "email-drafts": "drafts",
  "email-sent": "sent",
  "email-deleted": "deleted",
  "email-spam": "spam",
  "email-archive": "archive",
};

const TITLE: Record<FolderRole, string> = {
  inbox: "Inbox",
  drafts: "Drafts",
  sent: "Sent",
  deleted: "Deleted",
  spam: "Spam/Junk",
  archive: "Archive",
};

function textOf(error: unknown) {
  return error instanceof Error ? error.message : "The mailbox request failed.";
}

function splitAddresses(value: string) {
  return value
    .split(/[;,]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function documentHtml(body: string, received = false) {
  // Only received HTML may contain server-filtered style attributes. The fixed
  // stylesheet is hash-authorized; received <style> elements remain blocked.
  const attributePolicy = received ? "'unsafe-inline'" : "'none'";
  return `<!DOCTYPE html><html><head><meta charset="utf-8"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'none'; img-src 'none'; font-src 'none'; connect-src 'none'; object-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'; style-src 'sha256-z86pM5dj2saOjO8AtjbcbE43TyFWd3eUlUD32dOxryM='; style-src-elem 'sha256-z86pM5dj2saOjO8AtjbcbE43TyFWd3eUlUD32dOxryM='; style-src-attr ${attributePolicy};"><base target="_blank"><style>${MAIL_DOCUMENT_STYLE}</style></head><body>${body}</body></html>`;
}

function applySignatureOnce(html: string, signature: string) {
  if (!signature || html.includes('data-amafh-signature="true"')) return html;
  return `${html}<div data-amafh-signature="true">${signature}</div>`;
}

export function EmailPage({
  page,
  navigate,
}: {
  page: PageId;
  navigate: (page: PageId) => void;
}) {
  const role = ROLE[page] ?? "inbox";
  const { api, session } = useSession();
  const employeeId = session?.employeeId ?? "";
  const [connection, setConnection] = useState<Connection | null>(null);
  const [limits, setLimits] = useState<Limits | null>(null);
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [pageError, setPageError] = useState("");
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);
  const [pageNumber, setPageNumber] = useState(1);
  const [messages, setMessages] = useState<MailPage | null>(null);
  const [loadingList, setLoadingList] = useState(false);
  const [selected, setSelected] = useState<MailMessage | null>(null);
  const [composeOpen, setComposeOpen] = useState(false);
  const [composeMode, setComposeMode] = useState<
    "new" | "reply" | "reply-all" | "forward" | "draft"
  >("new");
  const openCompose = (
    mode: "new" | "reply" | "reply-all" | "forward" | "draft",
  ) => {
    setComposeMode(mode);
    setComposeOpen(true);
  };
  const [signatureOpen, setSignatureOpen] = useState(false);
  const [signature, setSignature] = useState("");
  const [signatureDraft, setSignatureDraft] = useState("");
  const urls = useRef<string[]>([]);
  const readSequence = useRef(0);
  const [activeRef, setActiveRef] = useState<string | null>(null);
  const [reading, setReading] = useState(false);
  const [pageCache] = useState(
    () => new MailViewCache<MailPage>(8, 2 * 1024 * 1024),
  );
  const [messageCache] = useState(
    () => new MailViewCache<MailMessage>(12, 8 * 1024 * 1024),
  );
  const [pendingReads] = useState(
    () => new Map<string, Promise<MailMessage>>(),
  );
  const refreshSeconds = useRef(60);
  useEffect(() => {
    refreshSeconds.current = limits?.refreshSeconds ?? 60;
  }, [limits?.refreshSeconds]);
  const pageKey = (folder: FolderRole, number: number, term: string) =>
    JSON.stringify([api.sessionGeneration, folder, number, term]);
  const messageKey = (ref: string) => `${api.sessionGeneration}:${ref}`;
  const [trackedFolder, setTrackedFolder] = useState(role);
  // Reset before rendering another folder, including browser back/forward.
  // This also prevents issuing its first request with the previous folder's page.
  if (trackedFolder !== role) {
    setTrackedFolder(role);
    setPageNumber(1);
    setMessages(pageCache.peek(pageKey(role, 1, "")));
    setSelected(null);
    setActiveRef(null);
    setReading(false);
    setSearch("");
    setQuery("");
    setError("");
    setPageError("");
  }
  useEffect(
    () => () => {
      readSequence.current += 1;
    },
    [role],
  );

  useEffect(() => {
    const owned = urls.current;
    return () => {
      for (const url of owned) URL.revokeObjectURL(url);
      owned.length = 0;
    };
  }, [employeeId]);

  useEffect(
    () => () => {
      pageCache.clear();
      messageCache.clear();
      pendingReads.clear();
    },
    [pageCache, messageCache, pendingReads, employeeId],
  );

  useEffect(() => {
    let cancelled = false;
    void api
      .request<Connection>("/mailbox")
      .then((value) => {
        if (!cancelled) setConnection(value);
      })
      .catch((reason: unknown) => {
        if (!cancelled) setPageError(textOf(reason));
      });
    void api
      .request<Limits>("/mailbox/limits")
      .then((value) => {
        if (!cancelled) setLimits(value);
      })
      .catch(() => undefined);
    void api
      .request<{ html: string }>("/mailbox/signature")
      .then((value) => {
        if (!cancelled) setSignature(value.html);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
    };
  }, [api, employeeId]);

  useEffect(() => {
    if (!connection?.connected) return;
    let cancelled = false;
    let pending = false;
    const cacheKey = JSON.stringify([
      api.sessionGeneration,
      role,
      pageNumber,
      query,
    ]);
    const load = () => {
      if (pending) return;
      pending = true;
      setLoadingList(true);
      const params = new URLSearchParams({
        page: String(pageNumber),
        pageSize: "25",
      });
      if (query) params.set("q", query);
      void api
        .request<MailPage>(`/mailbox/folders/${role}/messages?${params}`)
        .then((value) => {
          if (!cancelled) {
            pageCache.set(cacheKey, value);
            setMessages(value);
            setPageError("");
          }
        })
        .catch((reason: unknown) => {
          if (cancelled) return;
          const text = textOf(reason);
          if (
            reason instanceof ApiFailure &&
            reason.code === "MAIL_RECONNECT"
          ) {
            pageCache.clear();
            messageCache.clear();
            setMessages(null);
            setPageError(text);
            setConnection((current) =>
              current
                ? { ...current, connected: false, reconnectRequired: true }
                : current,
            );
            return;
          }
          setPageError(text);
          setMessages((current) =>
            current && current.items.length > 0 ? current : null,
          );
        })
        .finally(() => {
          pending = false;
          if (!cancelled) setLoadingList(false);
        });
    };
    load();
    const timer = window.setInterval(
      load,
      refreshSeconds.current * 1000,
    );
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [
    api,
    connection?.connected,
    employeeId,
    pageNumber,
    query,
    refreshKey,
    role,
    pageCache,
    messageCache,
  ]);

  const connect = async () => {
    setBusy(true);
    setError("");
    try {
      const value = await api.request<Connection>("/mailbox/connection", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      setPassword("");
      closeMessage();
      pendingReads.clear();
      pageCache.clear();
      messageCache.clear();
      setConnection(value);
    } catch (reason) {
      setError(textOf(reason));
    } finally {
      setBusy(false);
    }
  };

  const disconnect = async () => {
    setBusy(true);
    try {
      await api.request("/mailbox/connection", { method: "DELETE" });
      pageCache.clear();
      messageCache.clear();
      pendingReads.clear();
      readSequence.current += 1;
      setSelected(null);
      setActiveRef(null);
      setReading(false);
      setMessages(null);
      setConnection((current) =>
        current
          ? { ...current, connected: false, reconnectRequired: false }
          : current,
      );
    } catch (reason) {
      setError(textOf(reason));
    } finally {
      setBusy(false);
    }
  };

  const closeMessage = () => {
    readSequence.current += 1;
    setSelected(null);
    setActiveRef(null);
    setReading(false);
  };
  const openMessage = async (row: MailRow) => {
    if (activeRef === row.ref && (selected || reading)) return;
    const request = ++readSequence.current;
    const cacheKey = messageKey(row.ref);
    const cached = messageCache.peek(cacheKey);
    setActiveRef(row.ref);
    setSelected(cached);
    setReading(true);
    setError("");
    try {
      let pending = pendingReads.get(cacheKey);
      if (!pending) {
        pending = api.request<MailMessage>(`/mailbox/messages/${row.ref}`);
        pendingReads.set(cacheKey, pending);
        void pending
          .finally(() => {
            if (pendingReads.get(cacheKey) === pending)
              pendingReads.delete(cacheKey);
          })
          .catch(() => undefined);
      }
      const message = await pending;
      if (request === readSequence.current) {
        messageCache.set(cacheKey, message);
        const currentPageKey = pageKey(role, pageNumber, query);
        const cachedPage = pageCache.peek(currentPageKey);
        if (cachedPage && role !== "drafts")
          pageCache.set(currentPageKey, {
            ...cachedPage,
            items: cachedPage.items.map((item) =>
              item.ref === row.ref ? { ...item, unread: false } : item,
            ),
          });
        setSelected(message);
        setMessages((current) =>
          current
            ? {
                ...current,
                items: current.items.map((item) =>
                  item.ref === row.ref && role !== "drafts"
                    ? { ...item, unread: false }
                    : item,
                ),
              }
            : current,
        );
      }
    } catch (reason) {
      if (request === readSequence.current) {
        messageCache.clear();
        pageCache.clear();
        setSelected(null);
        setError(textOf(reason));
      }
    } finally {
      if (request === readSequence.current) setReading(false);
    }
  };

  const hideOrRestore = async (ref: string, action: "hide" | "restore") => {
    await api.request(`/mailbox/messages/${ref}/${action}`, { method: "POST" });
    pageCache.clear();
    messageCache.clear();
    closeMessage();
    setPageNumber(1);
    setRefreshKey((current) => current + 1);
  };

  const download = async (ref: string, index: number, filename: string) => {
    const response = await api.response(
      `/mailbox/messages/${ref}/attachments/${index}`,
    );
    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    urls.current.push(url);
    const link = document.createElement("a");
    link.href = url;
    link.download = filename || "attachment";
    link.click();
  };

  const pageCount = Math.max(1, Math.ceil((messages?.total ?? 0) / 25));
  const folderMissing = pageError.includes("folder is not available");
  const syncState = messages?.syncState;
  const synchronizing = syncState === "initial" || syncState === "updating";
  const syncProblem = syncState === "failed" || syncState === "offline";
  const keepList = Boolean(messages && messages.items.length > 0);

  const folders: { role: FolderRole; page: PageId; icon: DsIconName }[] = [
    { role: "inbox", page: "email-inbox", icon: "mail" },
    { role: "drafts", page: "email-drafts", icon: "edit" },
    { role: "sent", page: "email-sent", icon: "forward" },
    { role: "deleted", page: "email-deleted", icon: "delete" },
    { role: "spam", page: "email-spam", icon: "warning" },
    { role: "archive", page: "email-archive", icon: "assets" },
  ];
  const applySearch = () => {
    setPageNumber(1);
    setQuery(search.trim());
    setMessages(pageCache.peek(pageKey(role, 1, search.trim())));
    setRefreshKey((current) => current + 1);
    closeMessage();
  };
  const from = selected ? mailIdentity(selected.sender) : null;
  const total = messages?.total ?? 0;

  return (
    <PageContainer className="email-page">
      <PageHeader
        title="Email"
        subtitle={connection?.address || "Your Official/Login email mailbox"}
        actions={
          connection?.connected ? (
            <>
              <Button
                variant="secondary"
                size="compact"
                onClick={() => setSignatureOpen(true)}
              >
                <DsIcon name="edit" size={14} /> Signature
              </Button>
              <Button
                variant="ghost"
                size="compact"
                onClick={() => void disconnect()}
                disabled={busy}
              >
                Disconnect
              </Button>
            </>
          ) : undefined
        }
      />
      {!connection && !pageError ? <LoadingState /> : null}
      {pageError && !connection ? (
        <ErrorState
          description={pageError}
          retry={() => window.location.reload()}
        />
      ) : null}
      {connection && !connection.connected ? (
        <div className="email-connect">
          <div className="email-connect-icon">
            <DsIcon name="mail" size={24} />
          </div>
          <SectionCard
            title={
              connection.reconnectRequired
                ? "Reconnect your mailbox"
                : "Your email, in one place"
            }
            description="Connect your Official/Login email to read and send messages without leaving AMAFH Core."
          >
            <ReadOnlyField
              label="Official/Login email"
              value={connection.address}
            />
            <FormField
              label="Mailbox password"
              htmlFor="mailbox-password"
              error={error || undefined}
            >
              <PasswordInput
                id="mailbox-password"
                name="mailbox-password"
                autoComplete="new-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
              />
            </FormField>
            <p className="email-help">
              Use your mailbox password. It may be different from your AMAFH
              Core password.
            </p>
            <Button
              onClick={() => void connect()}
              disabled={busy || !password}
              loading={busy}
            >
              {connection.reconnectRequired
                ? "Reconnect mailbox"
                : "Connect mailbox"}
            </Button>
          </SectionCard>
        </div>
      ) : null}
      {connection?.connected ? (
        <div className="email-layout" data-reading={Boolean(activeRef)}>
          <aside className="email-folders" aria-label="Mailbox folders">
            <Button
              className="email-compose"
              onClick={() => openCompose("new")}
            >
              <DsIcon name="edit" size={16} /> Compose
            </Button>
            <nav aria-label="Email folders">
              {folders.map((folder) => (
                <button
                  key={folder.role}
                  type="button"
                  className={`email-folder ${role === folder.role ? "email-folder--active" : ""}`}
                  aria-current={role === folder.role ? "page" : undefined}
                  onClick={() => {
                    if (folder.role !== role) navigate(folder.page);
                  }}
                >
                  <DsIcon name={folder.icon} size={18} />
                  <span>{TITLE[folder.role]}</span>
                </button>
              ))}
            </nav>
            <div className="email-connection-status">
              <span aria-hidden="true" />
              <div>
                <strong>Connected</strong>
                <small>Your private mailbox</small>
              </div>
            </div>
          </aside>
          <EmailSplitPane>
            <section
              id="email-message-list-panel"
              className="email-list-panel"
              aria-label={`${TITLE[role]} messages`}
              aria-busy={loadingList}
            >
              <div className="email-list-header">
                <div>
                  <h2>{TITLE[role]}</h2>
                  <span>
                    {query
                      ? "Search results"
                      : `${total} ${total === 1 ? "message" : "messages"}`}
                  </span>
                </div>
                <Button
                  variant="ghost"
                  size="compact"
                  aria-label="Refresh mailbox"
                  title="Refresh mailbox"
                  disabled={loadingList}
                  onClick={() => {
                    pageCache.clear();
                    messageCache.clear();
                    setRefreshKey((current) => current + 1);
                  }}
                >
                  <DsIcon name="refresh" size={16} />
                </Button>
              </div>
              <form
                className="email-search"
                role="search"
                aria-label="Search mailbox"
                onSubmit={(event) => {
                  event.preventDefault();
                  applySearch();
                }}
              >
                <TextInput
                  id="mailbox-search"
                  type="search"
                  aria-label="Search mailbox"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder={`Search ${TITLE[role].toLowerCase()}`}
                  prefix={<DsIcon name="search" size={16} />}
                />
                <button
                  type="submit"
                  className="email-search-submit"
                  aria-label="Search messages"
                >
                  <DsIcon name="forward" size={16} />
                </button>
              </form>
              {query ? (
                <div className="email-search-applied">
                  <span>“{query}”</span>
                  <button
                    type="button"
                    aria-label="Clear mailbox search"
                    onClick={() => {
                      setSearch("");
                      setQuery("");
                      setPageNumber(1);
                      setMessages(pageCache.peek(pageKey(role, 1, "")));
                    }}
                  >
                    <DsIcon name="close" size={14} />
                  </button>
                </div>
              ) : null}
              {role === "deleted" ? (
                <p className="email-folder-note">
                  Hidden in AMAFH Core only. Original mailbox messages are kept.
                  Restore brings them back here.
                </p>
              ) : null}
              {role === "drafts" ? (
                <p className="email-folder-note">
                  Saving adds a new draft. Older versions are hidden here and
                  kept in your mailbox.
                </p>
              ) : null}
              {keepList && pageError ? (
                <InlineNotice tone="warning">{pageError}</InlineNotice>
              ) : null}
              {keepList && syncState === "updating" ? (
                <div className="email-folder-note">
                  Updating this folder. Messages already synchronized stay open.
                </div>
              ) : null}
              {keepList && syncProblem ? (
                <InlineNotice tone="warning">
                  The mailbox could not be refreshed. Messages from the last
                  successful synchronization stay available.
                </InlineNotice>
              ) : null}
              {messages?.syncedAt ? (
                <div className="email-folder-note">
                  Last synchronized{" "}
                  <CompactDateTime value={messages.syncedAt} />
                </div>
              ) : null}
              <div className="email-list-scroll">
                {loadingList && !messages ? (
                  <LoadingState title="Loading messages" />
                ) : folderMissing ? (
                  <UnavailableState description="This folder is not available in your mailbox." />
                ) : pageError && !keepList ? (
                  <RetryState
                    description={pageError}
                    retry={() => setRefreshKey((current) => current + 1)}
                  />
                ) : messages && total === 0 && synchronizing ? (
                  <LoadingState title="Synchronizing mailbox" />
                ) : messages && total === 0 && syncProblem ? (
                  <RetryState
                    description="Mailbox synchronization failed. Nothing already synchronized was discarded."
                    retry={() => setRefreshKey((current) => current + 1)}
                  />
                ) : messages && total === 0 ? (
                  <EmptyState
                    title={
                      query ? "No matching messages" : "You're all caught up"
                    }
                    description={
                      query
                        ? "Try another name or subject."
                        : "There are no messages in this folder."
                    }
                  />
                ) : (
                  <ul className="email-message-list">
                    {messages?.items.map((row) => {
                      const identity = mailIdentity(
                        role === "sent" || role === "drafts"
                          ? row.recipients
                          : row.sender,
                      );
                      return (
                        <li key={row.ref}>
                          <button
                            type="button"
                            className={`email-message ${row.unread ? "email-message--unread" : ""} ${activeRef === row.ref ? "email-message--selected" : ""}`}
                            aria-label={`Open message: ${row.subject}`}
                            aria-pressed={activeRef === row.ref}
                            onClick={() => void openMessage(row)}
                          >
                            <span
                              className="email-message-avatar"
                              aria-hidden="true"
                            >
                              {identity.initials}
                            </span>
                            <span className="email-message-summary">
                              <span className="email-message-top">
                                <span
                                  className="email-message-person"
                                  title={
                                    role === "sent" || role === "drafts"
                                      ? row.recipients
                                      : row.sender
                                  }
                                >
                                  {identity.label}
                                </span>
                                <time dateTime={row.date || undefined}>
                                  {mailDate(row.date)}
                                </time>
                              </span>
                              <span className="email-message-subject">
                                {row.unread ? (
                                  <span
                                    className="email-unread-dot"
                                    aria-label="Unread"
                                  />
                                ) : null}
                                <span>{row.subject || "(no subject)"}</span>
                                {row.hasAttachment ? (
                                  <span
                                    title="Has attachments"
                                    aria-label="Has attachments"
                                  >
                                    <DsIcon name="download" size={14} />
                                  </span>
                                ) : null}
                              </span>
                              <span className="email-message-preview">
                                {mailPreview(row.preview)}
                              </span>
                            </span>
                          </button>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </div>
              <div className="email-pagination">
                <span>
                  {total
                    ? `${(pageNumber - 1) * 25 + 1}–${Math.min(pageNumber * 25, total)} of ${total}`
                    : "0 messages"}
                </span>
                <div>
                  <Button
                    variant="ghost"
                    size="compact"
                    aria-label="Previous page"
                    disabled={pageNumber <= 1 || loadingList}
                    onClick={() => {
                      closeMessage();
                      setMessages(
                        pageCache.peek(pageKey(role, pageNumber - 1, query)),
                      );
                      setPageNumber((current) => current - 1);
                    }}
                  >
                    <DsIcon name="previous" size={16} />
                  </Button>
                  <span aria-label={`Page ${pageNumber} of ${pageCount}`}>
                    {pageNumber} / {pageCount}
                  </span>
                  <Button
                    variant="ghost"
                    size="compact"
                    aria-label="Next page"
                    disabled={pageNumber >= pageCount || loadingList}
                    onClick={() => {
                      closeMessage();
                      setMessages(
                        pageCache.peek(pageKey(role, pageNumber + 1, query)),
                      );
                      setPageNumber((current) => current + 1);
                    }}
                  >
                    <DsIcon name="next" size={16} />
                  </Button>
                </div>
              </div>
            </section>
            <section
              className={`email-reader ${!activeRef ? "email-reader--empty" : ""}`}
              aria-label="Message reading pane"
              aria-busy={reading}
            >
              {reading && !selected ? (
                <LoadingState title="Opening message" />
              ) : selected ? (
                <>
                  {error ? (
                    <InlineNotice tone="error">{error}</InlineNotice>
                  ) : null}
                  <header className="email-reader-header">
                    <div className="email-reader-top">
                      <Button
                        variant="ghost"
                        size="compact"
                        className="email-reader-back"
                        onClick={closeMessage}
                      >
                        <DsIcon name="back" size={16} /> Messages
                      </Button>
                      <span>
                        {TITLE[role]}
                        {reading ? " · Updating…" : ""}
                      </span>
                      <Button
                        variant="ghost"
                        size="compact"
                        aria-label="Close message"
                        onClick={closeMessage}
                      >
                        <DsIcon name="close" size={16} />
                      </Button>
                    </div>
                    <h2>{selected.subject || "(no subject)"}</h2>
                    <div className="email-sender">
                      <span className="email-message-avatar" aria-hidden="true">
                        {from?.initials}
                      </span>
                      <div>
                        <strong>{from?.label}</strong>
                        <span>{from?.email}</span>
                      </div>
                      {selected.date ? (
                        <CompactDateTime value={selected.date} />
                      ) : null}
                    </div>
                    <dl className="email-message-details">
                      <div>
                        <dt>To</dt>
                        <dd>{selected.recipients || "—"}</dd>
                      </div>
                      {selected.cc ? (
                        <div>
                          <dt>CC</dt>
                          <dd>{selected.cc}</dd>
                        </div>
                      ) : null}
                      {selected.bcc &&
                      (role === "drafts" || role === "sent") ? (
                        <div>
                          <dt>BCC</dt>
                          <dd>{selected.bcc}</dd>
                        </div>
                      ) : null}
                    </dl>
                  </header>
                  <div className="email-reader-body">
                    <iframe
                      className="email-frame"
                      title="Message"
                      sandbox=""
                      referrerPolicy="no-referrer"
                      srcDoc={documentHtml(selected.html, true)}
                    />
                  </div>
                  {selected.attachments.length ? (
                    <div
                      className="email-attachments"
                      aria-label="Message attachments"
                    >
                      {selected.attachments.map((item) => (
                        <Button
                          key={item.index}
                          variant="secondary"
                          size="compact"
                          onClick={() =>
                            void download(
                              selected.ref,
                              item.index,
                              item.filename,
                            ).catch((reason) => setError(textOf(reason)))
                          }
                        >
                          <DsIcon name="download" size={14} />
                          {item.filename}
                          <span className="email-attachment-size">
                            {item.size < 1024
                              ? `${item.size} B`
                              : `${Math.ceil(item.size / 1024)} KB`}
                          </span>
                        </Button>
                      ))}
                    </div>
                  ) : null}
                  <footer className="email-reader-actions">
                    {role === "deleted" ? (
                      <Button
                        size="compact"
                        onClick={() =>
                          void hideOrRestore(selected.ref, "restore").catch(
                            (reason) => setError(textOf(reason)),
                          )
                        }
                      >
                        <DsIcon name="back" size={14} /> Restore
                      </Button>
                    ) : (
                      <>
                        <Button
                          size="compact"
                          onClick={() =>
                            openCompose(role === "drafts" ? "draft" : "reply")
                          }
                        >
                          <DsIcon
                            name={role === "drafts" ? "edit" : "back"}
                            size={14}
                          />
                          {role === "drafts" ? "Edit draft" : "Reply"}
                        </Button>
                        {role !== "drafts" ? (
                          <>
                            <Button
                              variant="secondary"
                              size="compact"
                              onClick={() => openCompose("reply-all")}
                            >
                              Reply all
                            </Button>
                            <Button
                              variant="ghost"
                              size="compact"
                              onClick={() => openCompose("forward")}
                            >
                              Forward <DsIcon name="forward" size={14} />
                            </Button>
                          </>
                        ) : null}
                        <Button
                          className="email-delete"
                          variant="ghost"
                          size="compact"
                          onClick={() =>
                            void hideOrRestore(selected.ref, "hide").catch(
                              (reason) => setError(textOf(reason)),
                            )
                          }
                        >
                          <DsIcon name="delete" size={14} />
                          {role === "drafts" ? "Discard" : "Delete"}
                        </Button>
                      </>
                    )}
                  </footer>
                </>
              ) : (
                <div className="email-reader-placeholder">
                  <span>
                    <DsIcon name="mail" size={24} />
                  </span>
                  <h2>
                    {error ? "Message could not be opened" : "Choose a message"}
                  </h2>
                  <p>
                    {error ||
                      "Select an email to read it here. Your messages stay in your connected mailbox."}
                  </p>
                  {activeRef ? (
                    <Button
                      variant="secondary"
                      size="compact"
                      onClick={closeMessage}
                    >
                      Back to messages
                    </Button>
                  ) : null}
                </div>
              )}
            </section>
          </EmailSplitPane>
        </div>
      ) : null}
      {error && !activeRef && connection?.connected ? (
        <InlineNotice tone="error">{error}</InlineNotice>
      ) : null}
      {composeOpen && connection?.connected ? (
        <ComposeDialog
          mode={composeMode}
          source={composeMode === "new" ? null : selected}
          ownAddress={connection.address}
          signature={signature}
          limits={limits}
          onClose={() => setComposeOpen(false)}
          onSent={() => {
            pageCache.clear();
            messageCache.clear();
            setComposeOpen(false);
            setRefreshKey((current) => current + 1);
          }}
        />
      ) : null}
      {signatureOpen ? (
        <SignatureDialog
          initial={signature}
          draft={signatureDraft}
          onDraft={setSignatureDraft}
          onClose={() => setSignatureOpen(false)}
          onSaved={(html) => {
            setSignature(html);
            setSignatureOpen(false);
          }}
        />
      ) : null}
    </PageContainer>
  );
}

function ComposeDialog({
  mode,
  source,
  ownAddress,
  signature,
  limits,
  onClose,
  onSent,
}: {
  mode: "new" | "reply" | "reply-all" | "forward" | "draft";
  source: MailMessage | null;
  ownAddress: string;
  signature: string;
  limits: Limits | null;
  onClose: () => void;
  onSent: () => void;
}) {
  const { api } = useSession();
  const editor = useRef<HTMLDivElement>(null);
  const attemptId = useRef(crypto.randomUUID());
  const draftRef = useRef<string | undefined>(mode === "draft" ? source?.ref : undefined);
  const others = (value: string) =>
    splitAddresses(value).filter((address) => address.toLowerCase() !== ownAddress.toLowerCase());
  const [to, setTo] = useState(() => {
    if (mode === "reply") return source?.replyTo || source?.sender || "";
    if (mode === "reply-all")
      return [source?.replyTo || source?.sender || "", ...others(source?.recipients || "")]
        .filter(Boolean)
        .join(", ");
    if (mode === "draft") return source?.recipients || "";
    return "";
  });
  const [cc, setCc] = useState(mode === "reply-all" || mode === "draft" ? source?.cc || "" : "");
  const [bcc, setBcc] = useState(mode === "draft" ? source?.bcc || "" : "");
  const [subject, setSubject] = useState(() => {
    if (!source) return "";
    if (mode === "forward") return `Fwd: ${source.subject}`;
    if (mode === "reply" || mode === "reply-all") return `Re: ${source.subject}`;
    return source.subject;
  });
  const [status, setStatus] = useState("");
  const [outcome, setOutcome] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [files, setFiles] = useState<ComposeFile[]>(() =>
    mode === "draft"
      ? (source?.attachments ?? []).map((item) => ({
          remoteIndex: item.index,
          filename: item.filename,
          size: item.size,
        }))
      : [],
  );
  const started = useRef(false);

  useEffect(() => {
    if (started.current || !editor.current) return;
    started.current = true;
    const quoted =
      mode === "draft"
        ? source?.html || "<p></p>"
        : mode === "new" || !source
          ? "<p></p>"
          : `<p></p><blockquote>${source.html}</blockquote>`;
    editor.current.innerHTML =
      mode === "draft" ? quoted : applySignatureOnce(quoted, signature);
  }, [mode, signature, source]);

  const upload = async (list: FileList | null) => {
    if (!list) return;
    const next = [...files];
    let total = next.reduce((sum, file) => sum + file.size, 0);
    for (const file of list) {
      if (limits && file.size > limits.attachmentBytes) {
        setError(`Each attachment must be ${limits.attachmentBytes} bytes or smaller.`);
        return;
      }
      if (limits && total + file.size > limits.attachmentsBytes) {
        setError(`Combined attachments must be ${limits.attachmentsBytes} bytes or smaller.`);
        return;
      }
      const body = new FormData();
      body.append("file", file);
      const saved = await api.request<{ id: string; filename: string; size: number }>(
        "/mailbox/attachments",
        { method: "POST", body },
      );
      next.push({ id: saved.id, filename: saved.filename, size: file.size });
      total += file.size;
    }
    setFiles(next);
  };

  const send = async (allowUnknownRetry: boolean) => {
    if (status === "unknown" && !allowUnknownRetry) return;
    if (allowUnknownRetry) attemptId.current = crypto.randomUUID();
    setBusy(true);
    setError("");
    setOutcome("");
    setStatus("sending");
    try {
      const result = await api.request<SendResult>("/mailbox/send", {
        method: "POST",
        body: JSON.stringify({
          attemptId: attemptId.current,
          to: splitAddresses(to),
          cc: splitAddresses(cc),
          bcc: splitAddresses(bcc),
          subject,
          html: editor.current?.innerHTML ?? "",
          attachmentIds: files.flatMap((file) => (file.id ? [file.id] : [])),
          keptAttachmentIndexes: files.flatMap((file) =>
            file.remoteIndex === undefined ? [] : [file.remoteIndex],
          ),
          previousRef: draftRef.current,
          inReplyTo:
            mode === "reply" || mode === "reply-all" ? source?.messageId || null : null,
          references:
            mode === "reply" || mode === "reply-all"
              ? [source?.references, source?.messageId].filter(Boolean).join(" ") || null
              : null,
        }),
      });
      setStatus(result.status);
      setOutcome(result.detail);
      if (
        result.status !== "accepted" &&
        result.status !== "accepted_unrecorded" &&
        result.status !== "partial"
      ) {
        setError(result.detail);
      }
    } catch (reason) {
      if (reason instanceof ApiFailure && reason.status === 401) {
        setStatus("");
        setError(textOf(reason));
        return;
      }
      setStatus("failed");
      setError(textOf(reason));
    } finally {
      setBusy(false);
    }
  };

  const saveDraft = async () => {
    setBusy(true);
    setError("");
    try {
      const saved = await api.request<{ ref: string }>("/mailbox/drafts", {
        method: "POST",
        body: JSON.stringify({
          to: splitAddresses(to),
          cc: splitAddresses(cc),
          bcc: splitAddresses(bcc),
          subject,
          html: editor.current?.innerHTML ?? "",
          attachmentIds: files.flatMap((file) => (file.id ? [file.id] : [])),
          keptAttachmentIndexes: files.flatMap((file) =>
            file.remoteIndex === undefined ? [] : [file.remoteIndex],
          ),
          previousRef: draftRef.current,
        }),
      });
      draftRef.current = saved.ref;
      onSent();
    } catch (reason) {
      setError(textOf(reason));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open
      title={
        mode === "reply"
          ? "Reply"
          : mode === "reply-all"
            ? "Reply all"
            : mode === "forward"
              ? "Forward"
              : mode === "draft"
                ? "Draft"
                : "New email"
      }
      onClose={onClose}
      busy={busy}
      size="xl"
      footer={
        <>
          <Button variant="secondary" disabled={busy} onClick={() => void saveDraft()}>
            Save draft
          </Button>
          <Button
            disabled={
              busy ||
              status === "sending" ||
              status === "failed" ||
              status === "unknown" ||
              status === "partial"
            }
            onClick={() => void send(false)}
          >
            {status === "sending" ? "Sending" : "Send"}
          </Button>
          {status === "failed" ? (
            <Button variant="secondary" disabled={busy} onClick={() => void send(true)}>
              Send again
            </Button>
          ) : null}
          {status === "unknown" ? (
            <Button variant="secondary" disabled={busy} onClick={() => void send(true)}>
              Send as a new attempt
            </Button>
          ) : null}
        </>
      }
    >
      <div className="email-compose-grid">
        {status === "sending" ? <InlineNotice>Sending is in progress.</InlineNotice> : null}
        {status === "accepted" || status === "accepted_unrecorded" ? (
          <InlineNotice tone={status === "accepted" ? "success" : "warning"}>{outcome}</InlineNotice>
        ) : null}
        {status === "unknown" ? (
          <InlineNotice tone="warning">
            The connection ended before acceptance could be confirmed. The message was not sent
            again. Sending as a new attempt might deliver a duplicate.
          </InlineNotice>
        ) : null}
        {status === "partial" ? (
          <InlineNotice tone="warning">
            {outcome} Do not send this same message again. Recipients the server already accepted
            could receive a duplicate.
          </InlineNotice>
        ) : null}
        {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}
        <FormField label="To" htmlFor="mail-to">
          <TextInput id="mail-to" value={to} onChange={(event) => setTo(event.target.value)} />
        </FormField>
        <FormField label="CC" htmlFor="mail-cc">
          <TextInput id="mail-cc" value={cc} onChange={(event) => setCc(event.target.value)} />
        </FormField>
        <FormField label="BCC" htmlFor="mail-bcc">
          <TextInput id="mail-bcc" value={bcc} onChange={(event) => setBcc(event.target.value)} />
        </FormField>
        <FormField label="Subject" htmlFor="mail-subject">
          <TextInput id="mail-subject" value={subject} onChange={(event) => setSubject(event.target.value)} />
        </FormField>
        <div>
          <Button
            type="button"
            variant="ghost"
            size="compact"
            onClick={() => document.execCommand("bold")}
          >
            Bold
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="compact"
            onClick={() => document.execCommand("insertUnorderedList")}
          >
            List
          </Button>
          <Button
            type="button"
            variant="ghost"
            size="compact"
            onClick={() => {
              const href = window.prompt("Link address");
              if (href && /^(https?:|mailto:)/i.test(href)) document.execCommand("createLink", false, href);
            }}
          >
            Link
          </Button>
        </div>
        <div
          ref={editor}
          className="email-editor"
          contentEditable
          role="textbox"
          aria-label="Message"
          suppressContentEditableWarning
        />
        <FileUpload
          id="mail-file"
          label="Attachment"
          hint={
            limits
              ? `Up to ${limits.attachmentBytes} bytes each and ${limits.attachmentsBytes} bytes combined.`
              : undefined
          }
          onChange={(list) => void upload(list)}
        />
        {files.map((file) => (
          <div key={file.id ?? `draft-${file.remoteIndex}`}>
            <span>{file.filename}</span>
            <Button
              type="button"
              variant="ghost"
              size="compact"
              onClick={() => {
                setFiles((current) =>
                  current.filter(
                    (item) => item.id !== file.id || item.remoteIndex !== file.remoteIndex,
                  ),
                );
                if (file.id) {
                  void api.request(`/mailbox/attachments/${file.id}`, { method: "DELETE" });
                }
              }}
            >
              Remove
            </Button>
          </div>
        ))}
      </div>
    </Dialog>
  );
}

function SignatureDialog({
  initial,
  draft,
  onDraft,
  onClose,
  onSaved,
}: {
  initial: string;
  draft: string;
  onDraft: (value: string) => void;
  onClose: () => void;
  onSaved: (html: string) => void;
}) {
  const { api } = useSession();
  const editor = useRef<HTMLDivElement>(null);
  const [html, setHtml] = useState(draft || initial);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const started = useRef(false);
  useEffect(() => {
    if (started.current || !editor.current) return;
    started.current = true;
    editor.current.innerHTML = draft || initial || "<p></p>";
  }, [draft, initial]);
  const save = async () => {
    setBusy(true);
    try {
      const saved = await api.request<{ html: string }>("/mailbox/signature", {
        method: "PUT",
        body: JSON.stringify({ html }),
      });
      onSaved(saved.html);
    } catch (reason) {
      setError(textOf(reason));
    } finally {
      setBusy(false);
    }
  };
  const remove = async () => {
    setBusy(true);
    try {
      await api.request("/mailbox/signature", { method: "DELETE" });
      onSaved("");
    } catch (reason) {
      setError(textOf(reason));
    } finally {
      setBusy(false);
    }
  };
  return (
    <Dialog
      open
      title="Signature"
      onClose={onClose}
      busy={busy}
      footer={
        <>
          <Button variant="secondary" disabled={busy} onClick={() => void remove()}>
            Remove
          </Button>
          <Button disabled={busy} onClick={() => void save()}>
            Save signature
          </Button>
        </>
      }
    >
      {error ? <InlineNotice tone="error">{error}</InlineNotice> : null}
      <InlineNotice>
        Saving changes the signature added to a newly composed message. Editing the signature
        inside one message does not change this saved signature.
      </InlineNotice>
      <div>
        <Button type="button" variant="ghost" size="compact" onClick={() => document.execCommand("bold")}>
          Bold
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="compact"
          onClick={() => document.execCommand("insertUnorderedList")}
        >
          List
        </Button>
        <Button
          type="button"
          variant="ghost"
          size="compact"
          onClick={() => {
            const href = window.prompt("Link address");
            if (href && /^(https?:|mailto:)/i.test(href)) document.execCommand("createLink", false, href);
          }}
        >
          Link
        </Button>
      </div>
      <div
        ref={editor}
        className="email-editor"
        contentEditable
        role="textbox"
        aria-label="Signature"
        suppressContentEditableWarning
        onInput={(event) => {
          const next = event.currentTarget.innerHTML;
          setHtml(next);
          onDraft(next);
        }}
      />
      <p>Preview</p>
      <iframe
        className="email-frame"
        title="Signature preview"
        sandbox=""
        referrerPolicy="no-referrer"
        srcDoc={documentHtml(html)}
      />
    </Dialog>
  );
}
