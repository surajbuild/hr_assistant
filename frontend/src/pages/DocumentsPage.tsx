/** HR documents (RAG source): list for everyone; upload/delete for admin & hr. */
import { useRef, useState, type FormEvent } from "react";
import { Bot, FileText, FileType, Info, Trash2, Upload, UploadCloud } from "lucide-react";
import { DataTable } from "@/components/DataTable";
import { Field, SearchInput } from "@/components/Field";
import { ConfirmDialog, Modal } from "@/components/Modal";
import { PageHeader, Panel } from "@/components/PageHeader";
import { AsyncContent, EmptyState, Notice, Spinner } from "@/components/States";
import { StatusBadge } from "@/components/StatusBadge";
import { useToast } from "@/components/Toast";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import { navigate } from "@/lib/router";
import type { HrDocument } from "@/lib/types";
import { useFetch } from "@/lib/useFetch";
import { cn } from "@/lib/utils";

const MAX_BYTES = 10 * 1024 * 1024;
const ALLOWED = ["pdf", "docx", "txt"];

function FileIcon({ type }: { type: string }) {
  const t = (type || "").toLowerCase().replace(/^\./, "");
  const styles: Record<string, string> = {
    pdf: "bg-red-50 text-red-600",
    docx: "bg-blue-50 text-blue-600",
    doc: "bg-blue-50 text-blue-600",
    txt: "bg-slate-100 text-slate-600",
  };
  return (
    <span className={cn("relative flex size-9 shrink-0 items-center justify-center rounded-lg", styles[t] ?? "bg-slate-100 text-slate-600")}>
      {t === "txt" ? <FileType className="size-4" /> : <FileText className="size-4" />}
      <span className="absolute -bottom-1 rounded bg-white px-0.5 text-[8px] font-bold uppercase ring-1 ring-border">{t || "file"}</span>
    </span>
  );
}

export function DocumentsPage() {
  const { role } = useAuth();
  const canManage = role === "admin" || role === "hr";
  const toast = useToast();
  const { data, loading, error, reload } = useFetch<HrDocument[]>("/documents");
  const [search, setSearch] = useState("");
  const [uploadOpen, setUploadOpen] = useState(false);
  const [toDelete, setToDelete] = useState<HrDocument | null>(null);
  const [deleting, setDeleting] = useState(false);

  const q = search.toLowerCase();
  const rows = (data ?? []).filter((d) => !q || d.name.toLowerCase().includes(q) || d.file_name.toLowerCase().includes(q));

  async function confirmDelete() {
    if (!toDelete) return;
    setDeleting(true);
    try {
      await api.del(`/documents/${toDelete.id}`);
      toast.success(`“${toDelete.name}” removed.`);
      setToDelete(null);
      reload();
    } catch (err) {
      toast.error(errorMessage(err, "Failed to delete document."));
    } finally {
      setDeleting(false);
    }
  }

  return (
    <>
      <PageHeader
        title="Documents"
        subtitle="Company policies and HR documents"
        actions={
          canManage && (
            <Button onClick={() => setUploadOpen(true)}>
              <Upload className="size-4" /> Upload Document
            </Button>
          )
        }
      />

      <Notice tone="info" icon={<Bot />} className="mb-5">
        Uploaded policies are indexed for the AI Assistant — ask it questions about them.{" "}
        <button type="button" onClick={() => navigate("/assistant")} className="font-semibold underline underline-offset-2">
          Open AI Assistant
        </button>
      </Notice>

      <Panel
        title="Document Library"
        subtitle={loading ? undefined : `${rows.length} document${rows.length === 1 ? "" : "s"}`}
        icon={<FileText />}
        bodyClassName="p-0"
        actions={<SearchInput value={search} onChange={setSearch} placeholder="Search documents..." className="w-full sm:w-64" />}
      >
        <AsyncContent loading={loading} error={error} onRetry={reload} loadingLabel="Loading documents...">
          <DataTable
            rows={rows}
            rowKey={(d) => d.id}
            empty={
              <EmptyState
                icon={<FileText className="size-6" />}
                title={search ? "No documents match your search" : "No documents yet"}
                description={canManage && !search ? "Upload a policy (PDF, DOCX or TXT) so the AI assistant can answer questions about it." : undefined}
                action={
                  canManage && !search ? (
                    <Button size="sm" onClick={() => setUploadOpen(true)}>
                      <Upload className="size-3.5" /> Upload
                    </Button>
                  ) : undefined
                }
              />
            }
            columns={[
              {
                key: "name",
                header: "Document",
                render: (d) => (
                  <div className="flex items-center gap-3">
                    <FileIcon type={d.file_type} />
                    <div className="min-w-0">
                      <p className="max-w-[320px] truncate font-medium">{d.name}</p>
                      <p className="max-w-[320px] truncate text-xs text-ink-muted">{d.file_name}</p>
                    </div>
                  </div>
                ),
              },
              { key: "version", header: "Version", render: (d) => (d.version ? `v${d.version}` : "—") },
              { key: "status", header: "Status", render: (d) => <StatusBadge status={d.status} /> },
              { key: "chunks", header: "Indexed chunks", align: "right", render: (d) => <span className="tabular-nums">{d.chunk_count ?? "—"}</span> },
              { key: "by", header: "Uploaded by", render: (d) => d.uploaded_by_name ?? (d.uploaded_by ? `User #${d.uploaded_by}` : "—") },
              { key: "date", header: "Uploaded", render: (d) => formatDate(d.upload_date) },
              ...(canManage
                ? [
                    {
                      key: "actions",
                      header: <span className="sr-only">Actions</span>,
                      align: "right" as const,
                      render: (d: HrDocument) => (
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          onClick={() => setToDelete(d)}
                          aria-label={`Delete ${d.name}`}
                          title="Delete"
                          className="text-danger hover:bg-danger-light hover:text-danger"
                        >
                          <Trash2 className="size-4" />
                        </Button>
                      ),
                    },
                  ]
                : []),
            ]}
          />
        </AsyncContent>
      </Panel>

      {canManage && (
        <UploadModal
          open={uploadOpen}
          onClose={() => setUploadOpen(false)}
          onUploaded={() => {
            setUploadOpen(false);
            reload();
          }}
        />
      )}

      <ConfirmDialog
        open={!!toDelete}
        title="Delete document?"
        message={
          <>
            <strong className="text-ink">{toDelete?.name}</strong> will be archived and removed from the AI assistant's knowledge base.
          </>
        }
        confirmLabel="Delete"
        busy={deleting}
        onConfirm={confirmDelete}
        onCancel={() => setToDelete(null)}
      />
    </>
  );
}

function UploadModal({ open, onClose, onUploaded }: { open: boolean; onClose: () => void; onUploaded: () => void }) {
  const toast = useToast();
  const inputRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [name, setName] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  function pick(f: File | null | undefined) {
    setErr(null);
    if (!f) return;
    const ext = f.name.split(".").pop()?.toLowerCase() ?? "";
    if (!ALLOWED.includes(ext)) {
      setErr("Only PDF, DOCX and TXT files are allowed.");
      return;
    }
    if (f.size > MAX_BYTES) {
      setErr("File is larger than 10 MB.");
      return;
    }
    setFile(f);
    if (!name) setName(f.name.replace(/\.[^.]+$/, ""));
  }

  function reset() {
    setFile(null);
    setName("");
    setErr(null);
    if (inputRef.current) inputRef.current.value = "";
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!file) {
      setErr("Please choose a file.");
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      const form = new FormData();
      form.append("file", file);
      if (name.trim()) form.append("name", name.trim());
      await api.upload("/documents/upload", form);
      toast.success("Document uploaded and indexed.");
      reset();
      onUploaded();
    } catch (error) {
      setErr(errorMessage(error, "Upload failed."));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={busy ? () => undefined : onClose}
      title="Upload Document"
      description="PDF, DOCX or TXT · max 10 MB"
      footer={
        <>
          <Button variant="outline" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button type="submit" form="upload-doc-form" disabled={busy || !file}>
            {busy ? <Spinner /> : <Upload className="size-4" />} {busy ? "Uploading & indexing..." : "Upload"}
          </Button>
        </>
      }
    >
      <form id="upload-doc-form" onSubmit={submit} className="flex flex-col gap-4" noValidate>
        <label
          htmlFor="doc-file"
          onDragOver={(e) => {
            e.preventDefault();
            setDragOver(true);
          }}
          onDragLeave={() => setDragOver(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragOver(false);
            pick(e.dataTransfer.files?.[0]);
          }}
          className={cn(
            "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-4 py-8 text-center transition-colors",
            dragOver ? "border-brand bg-brand-light" : "border-slate-300 hover:border-brand/60 hover:bg-slate-50",
          )}
        >
          <UploadCloud className="size-8 text-brand" />
          {file ? (
            <>
              <p className="text-sm font-medium text-ink">{file.name}</p>
              <p className="text-xs text-ink-muted">{(file.size / 1024).toFixed(0)} KB · click to change</p>
            </>
          ) : (
            <>
              <p className="text-sm font-medium text-ink">Click to choose a file or drag it here</p>
              <p className="text-xs text-ink-muted">.pdf, .docx, .txt</p>
            </>
          )}
          <input
            ref={inputRef}
            id="doc-file"
            type="file"
            accept=".pdf,.docx,.txt"
            className="sr-only"
            onChange={(e) => pick(e.target.files?.[0])}
          />
        </label>
        <Field label="Display name" htmlFor="doc-name" hint="Optional — defaults to the file name">
          <Input id="doc-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Leave Policy" />
        </Field>
        <p className="flex items-start gap-2 text-xs text-ink-muted">
          <Info className="mt-0.5 size-3.5 shrink-0" /> The document is parsed and split into chunks so the AI assistant can cite it in answers.
        </p>
        {err && <Notice tone="danger">{err}</Notice>}
      </form>
    </Modal>
  );
}
