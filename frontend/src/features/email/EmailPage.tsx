import { useEffect, useMemo, useRef, useState } from "react";
import type { PageId } from "../../access";
import { ApiFailure } from "../../app/api/http";
import { useSession } from "../../app/session/useSession";
import {
  Button,
  CompactDateTime,
  Dialog,
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
  ResponsiveDataTable,
  RetryState,
  SearchFilterToolbar,
  SectionCard,
  StatusBadge,
  TextInput,
  UnavailableState,
  type DataTableColumn,
} from "../../design-system";
import "./email.css";

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
};

type MailMessage = MailRow & {
  html: string;
  cc: string;
  bcc: string;
  attachments: { index: number; filename: string; contentType: string; size: number }[];
  messageId: string;
  replyTo: string;
};

type ComposeFile = { id?: string; remoteIndex?: number; filename: string; size: number };

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

function documentHtml(body: string) {
  return `<!DOCTYPE html><html><head><meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src data:;"><base target="_blank"></head><body>${body}</body></html>`;
}

function applySignatureOnce(html: string, signature: string) {
  if (!signature || html.includes('data-amafh-signature="true"')) return html;
  return `${html}<div data-amafh-signature="true">${signature}</div>`;
}

export function EmailPage({ page }: { page: PageId }) {
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
  const [composeMode, setComposeMode] = useState<"new" | "reply" | "reply-all" | "forward" | "draft">("new");
  const openCompose = (mode: "new" | "reply" | "reply-all" | "forward" | "draft") => {
    setComposeMode(mode);
    setComposeOpen(true);
  };
  const [signatureOpen, setSignatureOpen] = useState(false);
  const [signature, setSignature] = useState("");
  const [signatureDraft, setSignatureDraft] = useState("");
  const urls = useRef<string[]>([]);

  useEffect(() => {
    const owned = urls.current;
    return () => {
      for (const url of owned) URL.revokeObjectURL(url);
      owned.length = 0;
    };
  }, [employeeId]);

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
    const load = () => {
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
            setMessages(value);
            setPageError("");
          }
        })
        .catch((reason: unknown) => {
          if (cancelled) return;
          setMessages(null);
          setPageError(textOf(reason));
          if (reason instanceof ApiFailure && reason.code === "MAIL_RECONNECT") {
            setConnection((current) =>
              current ? { ...current, connected: false, reconnectRequired: true } : current,
            );
          }
        })
        .finally(() => {
          if (!cancelled) setLoadingList(false);
        });
    };
    load();
    const seconds = limits?.refreshSeconds ?? 60;
    const timer = window.setInterval(load, seconds * 1000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [api, connection?.connected, employeeId, limits?.refreshSeconds, pageNumber, query, refreshKey, role]);

  const columns = useMemo<DataTableColumn<MailRow>[]>(
    () => [
      {
        key: "who",
        header: role === "sent" || role === "drafts" ? "To" : "From",
        render: (row) => (role === "sent" || role === "drafts" ? row.recipients : row.sender) || "—",
      },
      { key: "subject", header: "Subject", render: (row) => row.subject },
      { key: "preview", header: "Preview", render: (row) => row.preview || "—" },
      {
        key: "date",
        header: "Date",
        kind: "datetime",
        render: (row) => (row.date ? <CompactDateTime value={row.date} /> : "—"),
      },
      {
        key: "unread",
        header: "Status",
        render: (row) => (
          <StatusBadge tone={row.unread ? "brand" : "neutral"}>
            {row.unread ? "Unread" : "Read"}
          </StatusBadge>
        ),
      },
      {
        key: "attachment",
        header: "Attachment",
        render: (row) => (row.hasAttachment ? "Yes" : "—"),
      },
    ],
    [role],
  );

  const connect = async () => {
    setBusy(true);
    setError("");
    try {
      const value = await api.request<Connection>("/mailbox/connection", {
        method: "POST",
        body: JSON.stringify({ password }),
      });
      setPassword("");
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
      setSelected(null);
      setMessages(null);
      setConnection((current) =>
        current ? { ...current, connected: false, reconnectRequired: false } : current,
      );
    } catch (reason) {
      setError(textOf(reason));
    } finally {
      setBusy(false);
    }
  };

  const openMessage = async (row: MailRow) => {
    try {
      const message = await api.request<MailMessage>(`/mailbox/messages/${row.ref}`);
      setSelected(message);
    } catch (reason) {
      setError(textOf(reason));
    }
  };

  const hideOrRestore = async (ref: string, action: "hide" | "restore") => {
    await api.request(`/mailbox/messages/${ref}/${action}`, { method: "POST" });
    setSelected(null);
    setPageNumber(1);
    setRefreshKey((current) => current + 1);
  };

  const download = async (ref: string, index: number, filename: string) => {
    const response = await api.response(`/mailbox/messages/${ref}/attachments/${index}`);
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

  return (
    <PageContainer className="email-page">
      <PageHeader
        title={TITLE[role]}
        subtitle={
          connection?.address
            ? `Mailbox ${connection.address}`
            : "Your Official/Login email mailbox"
        }
        actions={
          connection?.connected ? (
            <>
              <Button size="compact" onClick={() => openCompose("new")}>
                Compose
              </Button>
              <Button variant="secondary" size="compact" onClick={() => setSignatureOpen(true)}>
                Signature
              </Button>
              <Button variant="ghost" size="compact" onClick={() => void disconnect()} disabled={busy}>
                Disconnect
              </Button>
            </>
          ) : null
        }
      />
      {!connection && !pageError ? <LoadingState /> : null}
      {pageError && !connection ? (
        <ErrorState description={pageError} retry={() => window.location.reload()} />
      ) : null}
      {connection && !connection.connected ? (
        <SectionCard
          title={connection.reconnectRequired ? "Reconnect mailbox" : "Connect mailbox"}
          description="The InMotion mailbox password may differ from the AMAFH Core password. AMAFH Core does not create the mailbox."
        >
          <ReadOnlyField label="Official/Login email" value={connection.address} />
          <FormField label="Mailbox password" htmlFor="mailbox-password" error={error || undefined}>
            <PasswordInput
              id="mailbox-password"
              name="mailbox-password"
              autoComplete="new-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </FormField>
          <Button onClick={() => void connect()} disabled={busy || !password}>
            {connection.reconnectRequired ? "Reconnect" : "Connect mailbox"}
          </Button>
        </SectionCard>
      ) : null}
      {connection?.connected ? (
        <>
          {role === "deleted" ? (
            <InlineNotice tone="info" title="Deleted in AMAFH Core only">
              Hiding a message here leaves it in its original InMotion folder. Restore shows it
              in AMAFH Core again. There is no permanent delete. Mail removed in Webmail or
              another mail client is outside this protection.
            </InlineNotice>
          ) : null}
          {role === "drafts" ? (
            <InlineNotice tone="info" title="Draft versions stay in the mailbox">
              Saving a draft adds a new copy in the mailbox Drafts folder and hides the previous
              version in AMAFH Core. Discard hides a version here. Neither action deletes the
              mailbox copy.
            </InlineNotice>
          ) : null}
          <SearchFilterToolbar
            searchId="mailbox-search"
            searchLabel="Search mailbox"
            searchValue={search}
            onSearchChange={setSearch}
            searchPlaceholder="Search this mailbox"
            actions={
              <Button
                variant="secondary"
                size="compact"
                onClick={() => {
                  setPageNumber(1);
                  setQuery(search.trim());
                  setRefreshKey((current) => current + 1);
                }}
              >
                Refresh
              </Button>
            }
            applied={
              query
                ? [
                    {
                      id: "search",
                      field: "Search",
                      value: query,
                      label: `Search: ${query}`,
                      onRemove: () => {
                        setSearch("");
                        setQuery("");
                        setPageNumber(1);
                      },
                    },
                  ]
                : []
            }
            onClearFilters={() => {
              setSearch("");
              setQuery("");
            }}
          />
          {loadingList && !messages ? <LoadingState /> : null}
          {folderMissing ? (
            <UnavailableState description="This mailbox does not have that folder. AMAFH Core does not create folders." />
          ) : pageError && connection.connected ? (
            <RetryState
              description={pageError}
              retry={() => setRefreshKey((current) => current + 1)}
            />
          ) : messages && messages.total === 0 ? (
            <EmptyState title="No messages" description="This folder has nothing to show." />
          ) : messages ? (
            <div className="email-workspace">
              <div>
                <ResponsiveDataTable
                  columns={columns}
                  rows={messages.items}
                  rowKey={(row) => row.ref}
                  ariaLabel={`${TITLE[role]} messages`}
                  page={pageNumber}
                  pageCount={pageCount}
                  onPageChange={setPageNumber}
                  pageSize={25}
                  onRowActivate={(row) => void openMessage(row)}
                />
              </div>
              {selected ? (
                <SectionCard title={selected.subject}>
                  <div>
                    {selected.sender || selected.recipients}{" "}
                    {selected.date ? <CompactDateTime value={selected.date} /> : null}
                  </div>
                  <iframe
                    className="email-frame"
                    title="Message"
                    sandbox=""
                    referrerPolicy="no-referrer"
                    srcDoc={documentHtml(selected.html)}
                  />
                  {selected.attachments.map((item) => (
                    <Button
                      key={item.index}
                      variant="secondary"
                      size="compact"
                      onClick={() => void download(selected.ref, item.index, item.filename)}
                    >
                      {item.filename}
                    </Button>
                  ))}
                  <div>
                    {role === "deleted" ? (
                      <Button size="compact" onClick={() => void hideOrRestore(selected.ref, "restore")}>
                        Restore
                      </Button>
                    ) : (
                      <Button
                        variant="secondary"
                        size="compact"
                        onClick={() => void hideOrRestore(selected.ref, "hide")}
                      >
                        {role === "drafts" ? "Discard draft" : "Delete"}
                      </Button>
                    )}
                    {role !== "deleted" ? (
                      <>
                        <Button variant="ghost" size="compact" onClick={() => openCompose("reply")}>
                          Reply
                        </Button>
                        <Button variant="ghost" size="compact" onClick={() => openCompose("reply-all")}>
                          Reply all
                        </Button>
                        <Button variant="ghost" size="compact" onClick={() => openCompose("forward")}>
                          Forward
                        </Button>
                        {role === "drafts" ? (
                          <Button variant="ghost" size="compact" onClick={() => openCompose("draft")}>
                            Edit draft
                          </Button>
                        ) : null}
                      </>
                    ) : null}
                  </div>
                </SectionCard>
              ) : null}
            </div>
          ) : null}
        </>
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
