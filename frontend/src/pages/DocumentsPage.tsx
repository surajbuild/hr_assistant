/**
 * HR documents (RAG source).
 * Everyone: list (GET /documents) + download (GET /documents/{id}/download).
 * HR / Admin: upload with progress (POST /documents/upload), re-index (POST /documents/{id}/reindex), archive with
 * confirm (DELETE /documents/{id}), and "Include archived" (GET /documents?include_archived=true; archived files are
 * downloadable only by HR / Admin — the backend enforces both).
 *
 * NB: helpers live in this file on purpose — the repo .gitignore pattern `documents/` would ignore a
 * `pages/documents/` folder.
 */
import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { Archive, Bot, Download, FileText, FileType, Info, MoreHorizontal, RefreshCw, Upload, UploadCloud, X } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { Field, SearchInput } from "@/components/Field";
import { ConfirmDialog, Modal } from "@/components/Modal";
import { PageHeader } from "@/components/PageHeader";
import { Segmented } from "@/components/Segmented";
import { AsyncContent, EmptyState, Notice, Spinner } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { api, ApiError, errorMessage, formatDetail, getToken, NETWORK_ERROR_MESSAGE, qs, setToken } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate, formatNumber } from "@/lib/format";
import { navigate } from "@/lib/router";
import type { HrDocument } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { cn } from "@/lib/utils";

// ---------------------------------------------------------------------------------------------------------------------
// Multipart upload with byte progress (XMLHttpRequest — fetch has no upload progress). Mirrors `api.upload`: `/api`
// prefix, Bearer token, `detail` error messages, 401 → clear token + /login. TODO(lead): move into lib/api.ts.
// ---------------------------------------------------------------------------------------------------------------------

interface UploadHandle<T> {
  promise: Promise<T>;
  abort: () => void;
}

function uploadWithProgress<T>(path: string, form: FormData, onProgress: (fraction: number) => void): UploadHandle<T> {
  const xhr = new XMLHttpRequest();
  const promise = new Promise<T>((resolve, reject) => {
    xhr.open("POST", `/api${path}`);
    const token = getToken();
    if (token) xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.setRequestHeader("Accept", "application/json");
    xhr.upload.onprogress = (e) => {
      if (e.lengthComputable && e.total > 0) onProgress(e.loaded / e.total);
    };
    xhr.upload.onload = () => onProgress(1);
    xhr.onerror = () => reject(new ApiError(NETWORK_ERROR_MESSAGE, 0));
    xhr.onabort = () => reject(new ApiError("Upload cancelled.", 0));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = xhr.responseText ? JSON.parse(xhr.responseText) : null;
      } catch {
        body = null;
      }
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(body as T);
        return;
      }
      if (xhr.status === 401) {
        setToken(null);
        if (window.location.pathname !== "/login") window.location.assign("/login");
      }
      const fallback =
        xhr.status === 413
          ? "File is too large. Maximum size is 10 MB."
          : xhr.status === 403
            ? "You do not have permission to perform this action."
            : xhr.status === 502 || xhr.status === 503 || xhr.status === 504
              ? NETWORK_ERROR_MESSAGE
              : `Upload failed (status ${xhr.status}).`;
      const detail = body && typeof body === "object" ? (body as { detail?: unknown }).detail : null;
      reject(new ApiError(formatDetail(detail, fallback), xhr.status));
    };
    xhr.send(form);
  });
  return { promise, abort: () => xhr.abort() };
}

// ---------------------------------------------------------------------------------------------------------------------
// Upload dialog (HR / Admin): drag-and-drop or pick one PDF / DOCX / TXT (≤ 10 MB), optional display name, byte
// progress, then an "indexing" phase while the server parses + chunks the file (the upload request is synchronous).
// Same-name uploads create a new version and archive the previous one (document_service.upload_document).
// ---------------------------------------------------------------------------------------------------------------------

const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED = ["pdf", "docx", "txt"];

type DocRow = HrDocument & { error_message?: string | null };

type Phase = "idle" | "uploading" | "indexing";

/** The name the server will use when the display name is left empty. */
function defaultDisplayName(fileName: string): string {
  const stem = fileName.replace(/\.[^.]+$/, "").replace(/[_-]/g, " ").trim();
  return stem || "Untitled document";
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

function validate(f: File): string | null {
  const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
  if (!f.name.includes(".") || !ALLOWED.includes(ext)) return "Only PDF, DOCX and TXT files are allowed.";
  if (f.size === 0) return "This file is empty.";
  if (f.size > MAX_BYTES) return `This file is ${formatBytes(f.size)} — the maximum is 10 MB.`;
  return null;
}

function UploadDialog({
  open,
  onClose,
  onUploaded,
  existing,
}: {
  open: boolean;
  onClose: () => void;
  onUploaded: (doc: DocRow) => void;
  /** Current (non-archived) documents, to warn about versioning. */
  existing: DocRow[];
}) {
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const handle = useRef<UploadHandle<DocRow> | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [phase, setPhase] = useState<Phase>("idle");
  const [progress, setProgress] = useState(0);
  const [fileError, setFileError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const busy = phase !== "idle";

  const effectiveName = file ? (name.trim() || defaultDisplayName(file.name)).slice(0, 255) : name.trim();
  const previous = effectiveName
    ? existing.filter((d) => d.status !== "archived" && d.name.toLowerCase() === effectiveName.toLowerCase())
    : [];
  const prevVersion = previous.reduce((m, d) => Math.max(m, Number(d.version) || 0), 0);

  function pick(f: File | null | undefined) {
    setSubmitError(null);
    if (!f) return;
    const err = validate(f);
    setFileError(err);
    setFile(err ? null : f);
    if (inputRef.current) inputRef.current.value = "";
  }

  function reset() {
    setFile(null);
    setName("");
    setFileError(null);
    setSubmitError(null);
    setProgress(0);
    setPhase("idle");
    if (inputRef.current) inputRef.current.value = "";
  }

  function close() {
    if (phase === "indexing") return; // the server is already processing — wait for the result
    if (phase === "uploading") handle.current?.abort();
    reset();
    onClose();
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setFileError("Choose a file to upload.");
      return;
    }
    const form = new FormData();
    form.append("file", file);
    if (name.trim()) form.append("name", name.trim());
    setSubmitError(null);
    setProgress(0);
    setPhase("uploading");
    const h = uploadWithProgress<DocRow>("/documents/upload", form, (f) => {
      setProgress(f);
      if (f >= 1) setPhase("indexing");
    });
    handle.current = h;
    try {
      const doc = await h.promise;
      if (doc.status === "failed") {
        toast.error(`“${doc.name}” was uploaded but could not be indexed${doc.error_message ? `: ${doc.error_message}` : "."}`);
      } else {
        toast.success(`“${doc.name}” uploaded (v${doc.version}) · ${doc.chunk_count ?? 0} chunks indexed.`);
      }
      reset();
      onUploaded(doc);
    } catch (err) {
      const msg = errorMessage(err, "Upload failed.");
      setPhase("idle");
      setProgress(0);
      if (msg !== "Upload cancelled.") {
        setSubmitError(msg);
        toast.error(msg);
      }
    } finally {
      handle.current = null;
    }
  }

  function onDrop(e: DragEvent<HTMLElement>) {
    e.preventDefault();
    setDragOver(false);
    if (busy) return;
    const files = e.dataTransfer.files;
    if (files.length > 1) {
      setFileError("Drop one file at a time.");
      return;
    }
    pick(files[0]);
  }

  const pct = Math.round(progress * 100);

  return (
    <Modal
      open={open}
      onClose={close}
      title="Upload document"
      description="PDF, DOCX or TXT · max 10 MB · indexed for the AI assistant"
      footer={
        <>
          <Button variant="outline" onClick={close} disabled={phase === "indexing"}>
            Cancel
          </Button>
          <Button type="submit" form="upload-doc-form" loading={busy} disabled={!file && !busy}>
            {!busy && <Upload />} {phase === "uploading" ? `Uploading ${pct}%` : phase === "indexing" ? "Indexing..." : "Upload"}
          </Button>
        </>
      }
    >
      <form id="upload-doc-form" onSubmit={submit} className="flex flex-col gap-4" noValidate>
        {!file ? (
          <div className="flex flex-col gap-1.5">
            <label
              htmlFor="doc-file"
              onDragOver={(e) => {
                e.preventDefault();
                setDragOver(true);
              }}
              onDragLeave={() => setDragOver(false)}
              onDrop={onDrop}
              className={cn(
                "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-4 py-10 text-center transition-colors duration-150 has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
                dragOver ? "border-brand bg-brand-subtle" : fileError ? "border-status-absent bg-surface" : "border-border-strong bg-surface hover:border-brand hover:bg-accent",
              )}
            >
              <span className="flex size-11 items-center justify-center rounded-full bg-brand-subtle text-brand-subtle-foreground">
                <UploadCloud className="size-5" aria-hidden="true" />
              </span>
              <span className="text-sm font-medium text-foreground">
                {dragOver ? "Drop to add the file" : (
                  <>
                    Drag a file here or <span className="text-brand underline underline-offset-2">browse</span>
                  </>
                )}
              </span>
              <span className="text-xs text-muted-foreground">.pdf, .docx or .txt up to 10 MB</span>
              <input
                ref={inputRef}
                id="doc-file"
                type="file"
                accept=".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
                className="sr-only"
                aria-invalid={!!fileError}
                aria-describedby={fileError ? "doc-file-error" : undefined}
                onChange={(e) => pick(e.target.files?.[0])}
              />
            </label>
            {fileError && (
              <p id="doc-file-error" role="alert" className="text-xs text-status-absent-fg">
                {fileError}
              </p>
            )}
          </div>
        ) : (
          <div className="flex flex-col gap-3 rounded-xl border border-border bg-surface-muted p-3.5">
            <div className="flex items-center gap-3">
              <span className="flex size-10 shrink-0 items-center justify-center rounded-lg bg-surface text-muted-foreground ring-1 ring-border">
                <FileText className="size-5" aria-hidden="true" />
              </span>
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">{file.name}</p>
                <p className="text-xs text-muted-foreground tabular-nums">
                  {formatBytes(file.size)} · {file.name.split(".").pop()?.toUpperCase()}
                </p>
              </div>
              {!busy && (
                <Button type="button" variant="ghost" size="icon-sm" aria-label="Remove file" onClick={() => reset()}>
                  <X />
                </Button>
              )}
            </div>
            {busy && (
              <div className="flex flex-col gap-1.5">
                <div
                  role="progressbar"
                  aria-label={phase === "indexing" ? "Indexing document" : "Upload progress"}
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={phase === "indexing" ? undefined : pct}
                  className="relative h-1.5 w-full overflow-hidden rounded-full bg-border"
                >
                  {phase === "indexing" ? (
                    <div className="skeleton absolute inset-0 rounded-full bg-brand-subtle" />
                  ) : (
                    <div className="h-full rounded-full bg-brand transition-[width] duration-200" style={{ width: `${pct}%` }} />
                  )}
                </div>
                <p className="text-xs text-muted-foreground tabular-nums" aria-live="polite">
                  {phase === "uploading" ? `Uploading… ${pct}%` : "Uploaded — parsing and indexing for the AI assistant…"}
                </p>
              </div>
            )}
          </div>
        )}

        <Field label="Display name" htmlFor="doc-name" hint={file && !name.trim() ? `Defaults to “${defaultDisplayName(file.name)}”` : "Optional — defaults to the file name"}>
          <Input
            id="doc-name"
            value={name}
            maxLength={255}
            disabled={busy}
            onChange={(e) => setName(e.target.value)}
            placeholder={file ? defaultDisplayName(file.name) : "e.g. Leave Policy"}
          />
        </Field>

        {previous.length > 0 && (
          <Notice tone="info" icon={<Info />}>
            “{previous[0]?.name}” already exists (v{prevVersion}). Uploading creates <strong>v{prevVersion + 1}</strong> and archives the previous version.
          </Notice>
        )}
        {submitError && <Notice tone="danger">{submitError}</Notice>}
      </form>
    </Modal>
  );
}

// ---------------------------------------------------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------------------------------------------------

type Scope = "current" | "all";

const STATUS_LABEL: Record<string, string> = { active: "Indexed", processing: "Processing", failed: "Failed", archived: "Archived" };

function FileBadge({ type }: { type: string }) {
  const t = (type || "").toLowerCase().replace(/^\./, "");
  return (
    <span className="relative flex size-9 shrink-0 items-center justify-center rounded-lg bg-surface-muted text-muted-foreground" aria-hidden="true">
      {t === "txt" ? <FileType className="size-4" /> : <FileText className="size-4" />}
      <span className="absolute -bottom-1 rounded bg-surface px-0.5 text-[8px] leading-3 font-bold text-foreground uppercase ring-1 ring-border">{t || "file"}</span>
    </span>
  );
}

function DocStatus({ d }: { d: DocRow }) {
  return (
    <span className="inline-flex flex-col items-start gap-0.5">
      <StatusBadge status={d.status} label={STATUS_LABEL[d.status] ?? undefined} />
      {d.status === "failed" && d.error_message && <span className="max-w-[220px] truncate text-xs text-status-absent-fg" title={d.error_message}>{d.error_message}</span>}
    </span>
  );
}

export function DocumentsPage() {
  const { role } = useAuth();
  const canManage = role === "admin" || role === "hr";
  const toast = useToast();
  const [scope, setScope] = useState<Scope>("current");
  const { data, loading, error, reload, setData } = useFetch<DocRow[]>(`/documents${qs({ include_archived: canManage && scope === "all" ? true : undefined })}`);
  const [search, setSearch] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [toArchive, setToArchive] = useState<DocRow | null>(null);
  const [archiving, setArchiving] = useState(false);
  const [busy, setBusy] = useState<Record<number, "download" | "reindex">>({});

  const all = data ?? [];
  const q = search.trim().toLowerCase();
  const rows = all.filter((d) => !q || d.name.toLowerCase().includes(q) || d.file_name.toLowerCase().includes(q));
  const live = all.filter((d) => d.status !== "archived");
  const indexedChunks = live.reduce((t, d) => t + (d.status === "active" ? Number(d.chunk_count ?? 0) : 0), 0);
  const failedCount = live.filter((d) => d.status === "failed").length;

  function setRowBusy(id: number, kind: "download" | "reindex" | null) {
    setBusy((prev) => {
      const next = { ...prev };
      if (kind) next[id] = kind;
      else delete next[id];
      return next;
    });
  }

  function replaceRow(doc: DocRow) {
    setData((prev) => (prev ? prev.map((d) => (d.id === doc.id ? { ...d, ...doc } : d)) : prev));
  }

  async function download(d: DocRow) {
    setRowBusy(d.id, "download");
    try {
      const filename = await api.download(`/documents/${d.id}/download`, d.file_name);
      toast.success(`Downloaded ${filename}`);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to download document."));
    } finally {
      setRowBusy(d.id, null);
    }
  }

  async function reindex(d: DocRow) {
    setRowBusy(d.id, "reindex");
    try {
      const doc = await api.post<DocRow>(`/documents/${d.id}/reindex`);
      replaceRow(doc);
      if (doc.status === "failed") toast.error(`Re-indexing “${doc.name}” failed${doc.error_message ? `: ${doc.error_message}` : "."}`);
      else toast.success(`“${doc.name}” re-indexed · ${doc.chunk_count ?? 0} chunks.`);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to re-index document."));
    } finally {
      setRowBusy(d.id, null);
    }
  }

  async function confirmArchive() {
    if (!toArchive) return;
    setArchiving(true);
    try {
      const doc = await api.del<DocRow>(`/documents/${toArchive.id}`);
      toast.success(`“${toArchive.name}” archived and removed from the AI assistant.`);
      if (scope === "all" && doc) replaceRow(doc);
      else setData((prev) => (prev ? prev.filter((x) => x.id !== toArchive.id) : prev));
      setToArchive(null);
    } catch (err) {
      toast.error(errorMessage(err, "Failed to archive document."));
    } finally {
      setArchiving(false);
    }
  }

  /** Actions: plain render function (not a component) so open menus survive re-renders. */
  function actions(d: DocRow) {
    const b = busy[d.id];
    if (!canManage) {
      return (
        <Button variant="ghost" size="icon-sm" aria-label={`Download ${d.name}`} title="Download" loading={b === "download"} onClick={(e) => {
          e.stopPropagation();
          void download(d);
        }}>
          {b !== "download" && <Download />}
        </Button>
      );
    }
    const archived = d.status === "archived";
    return (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="icon-sm" aria-label={`Actions for ${d.name}`} disabled={!!b} onClick={(e) => e.stopPropagation()}>
            {b ? <Spinner /> : <MoreHorizontal />}
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent onClick={(e) => e.stopPropagation()}>
          <DropdownMenuItem onSelect={() => void download(d)}>
            <Download /> Download original
          </DropdownMenuItem>
          {!archived && (
            <DropdownMenuItem onSelect={() => void reindex(d)}>
              <RefreshCw /> Re-index
            </DropdownMenuItem>
          )}
          {!archived && (
            <>
              <DropdownMenuSeparator />
              <DropdownMenuItem destructive onSelect={() => setToArchive(d)}>
                <Archive /> Archive
              </DropdownMenuItem>
            </>
          )}
        </DropdownMenuContent>
      </DropdownMenu>
    );
  }

  const empty = (
    <EmptyState
      icon={<FileText />}
      title={q ? "No documents match your search" : scope === "all" ? "No documents yet" : "No documents in the knowledge base"}
      description={
        q ? "Try a different name." : canManage ? "Upload a policy (PDF, DOCX or TXT) so the AI assistant can answer questions about it." : "HR hasn't published any documents yet."
      }
      action={
        q ? (
          <Button variant="outline" size="sm" onClick={() => setSearch("")}>
            Clear search
          </Button>
        ) : canManage ? (
          <Button size="sm" onClick={() => setUploadOpen(true)}>
            <Upload /> Upload document
          </Button>
        ) : undefined
      }
    />
  );

  return (
    <>
      <PageHeader
        title="Documents"
        subtitle="Company policies and HR documents the AI assistant can cite"
        actions={
          canManage && (
            <Button onClick={() => setUploadOpen(true)}>
              <Upload /> Upload document
            </Button>
          )
        }
      />

      <Notice tone="info" icon={<Bot />} className="mb-5">
        Indexed documents are searchable by the AI Assistant — ask it questions about them.{" "}
        <button type="button" onClick={() => navigate("/assistant")} className="font-semibold underline underline-offset-2">
          Open AI Assistant
        </button>
      </Notice>

      {canManage && failedCount > 0 && !loading && (
        <Notice tone="danger" className="mb-5">
          {failedCount === 1 ? "1 document" : `${failedCount} documents`} could not be indexed and won't be used by the assistant. Re-index or upload a new version.
        </Notice>
      )}

      <section className="hr-card min-w-0">
        <header className="flex flex-col gap-3 border-b border-border px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="flex min-w-0 items-center gap-2.5">
            <FileText className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            <div className="min-w-0">
              <h2 className="truncate text-base font-semibold text-foreground">Document library</h2>
              <p className="truncate text-xs font-medium text-muted-foreground tabular-nums" aria-live="polite">
                {loading ? "Loading…" : `${rows.length} document${rows.length === 1 ? "" : "s"} · ${formatNumber(indexedChunks)} indexed chunks`}
              </p>
            </div>
          </div>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            {canManage && (
              <Segmented<Scope>
                label="Documents shown"
                value={scope}
                onChange={setScope}
                options={[
                  { value: "current", label: "Current" },
                  { value: "all", label: "Include archived" },
                ]}
              />
            )}
            <SearchInput value={search} onChange={setSearch} placeholder="Search documents..." className="w-full sm:w-64" />
          </div>
        </header>

        <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading documents...">
          <DataTable
            rows={rows}
            rowKey={(d) => d.id}
            pageSize={20}
            empty={empty}
            mobileCard={(d) => (
              <div className="flex items-center gap-3 px-4 py-3">
                <FileBadge type={d.file_type} />
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium text-foreground">{d.name}</p>
                  <p className="truncate text-xs text-muted-foreground tabular-nums">
                    {d.version ? `v${d.version} · ` : ""}
                    {formatDate(d.upload_date)}
                    {d.status === "active" ? ` · ${d.chunk_count ?? 0} chunks` : ""}
                  </p>
                  <div className="mt-1">
                    <DocStatus d={d} />
                  </div>
                </div>
                {actions(d)}
              </div>
            )}
            columns={[
              {
                key: "name",
                header: "Document",
                label: "document",
                sortValue: (d) => d.name,
                render: (d) => (
                  <div className="flex items-center gap-3">
                    <FileBadge type={d.file_type} />
                    <div className="min-w-0">
                      <p className="max-w-[300px] truncate font-medium text-foreground">{d.name}</p>
                      <p className="max-w-[300px] truncate text-xs text-muted-foreground">{d.file_name}</p>
                    </div>
                  </div>
                ),
              },
              { key: "version", header: "Version", sortValue: (d) => Number(d.version) || 0, render: (d) => <span className="tabular-nums">{d.version ? `v${d.version}` : "—"}</span> },
              { key: "status", header: "Status", sortValue: (d) => d.status, render: (d) => <DocStatus d={d} /> },
              {
                key: "chunks",
                header: "Chunks",
                label: "indexed chunks",
                align: "right",
                sortValue: (d) => Number(d.chunk_count ?? 0),
                render: (d) => <span className="tabular-nums">{d.status === "active" ? formatNumber(d.chunk_count ?? 0) : "—"}</span>,
              },
              { key: "by", header: "Uploaded by", sortValue: (d) => d.uploaded_by_name ?? "", render: (d) => <span className="text-muted-foreground">{d.uploaded_by_name ?? (d.uploaded_by ? `User #${d.uploaded_by}` : "—")}</span> },
              { key: "date", header: "Uploaded", sortValue: (d) => d.upload_date ?? "", render: (d) => <span className="tabular-nums">{formatDate(d.upload_date)}</span> },
              {
                key: "actions",
                header: <span className="sr-only">Actions</span>,
                align: "right",
                render: (d) => <div className="flex justify-end">{actions(d)}</div>,
              },
            ]}
          />
        </AsyncContent>
      </section>

      {canManage && (
        <UploadDialog
          open={uploadOpen}
          existing={live}
          onClose={() => setUploadOpen(false)}
          onUploaded={() => {
            setUploadOpen(false);
            reload();
          }}
        />
      )}

      <ConfirmDialog
        open={!!toArchive}
        title="Archive document?"
        message={
          <div className="flex flex-col gap-2">
            <p>
              <strong className="text-foreground">{toArchive?.name}</strong>
              {toArchive?.version ? ` (v${toArchive.version})` : ""} will be removed from the AI assistant's knowledge base.
            </p>
            <p>The record and the original file are kept for audit and stay visible under “Include archived”.</p>
          </div>
        }
        confirmLabel="Archive"
        busy={archiving}
        onConfirm={confirmArchive}
        onCancel={() => setToArchive(null)}
      />
    </>
  );
}
