"use client";

import { ChangeEvent, useEffect, useMemo, useState } from "react";

import { Button, Card, Input } from "@/components/ui";
import {
  createWorkspace,
  deleteDocument,
  listDocuments,
  listWorkspaces,
  reindexDocument,
  type DocumentItem,
  type Workspace,
  uploadDocument,
} from "@/lib/api";

export default function DocumentsPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState<string>("");
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [workspaceName, setWorkspaceName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const activeWorkspace = useMemo(
    () => workspaces.find((workspace) => workspace.id === workspaceId) ?? null,
    [workspaceId, workspaces],
  );

  useEffect(() => {
    async function init() {
      try {
        const ws = await listWorkspaces();
        setWorkspaces(ws);
        if (ws.length > 0) setWorkspaceId(ws[0].id);
      } catch (err) {
        setError((err as Error).message);
      }
    }

    void init();
  }, []);

  useEffect(() => {
    if (!workspaceId) return;

    async function loadDocs() {
      try {
        const data = await listDocuments(workspaceId);
        setDocuments(data);
      } catch (err) {
        setError((err as Error).message);
      }
    }

    void loadDocs();
    const id = setInterval(() => void loadDocs(), 4000);
    return () => clearInterval(id);
  }, [workspaceId]);

  async function onUpload() {
    if (!workspaceId || !file) return;
    setLoading(true);
    setError(null);
    try {
      await uploadDocument(workspaceId, file);
      setFile(null);
      setDocuments(await listDocuments(workspaceId));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  async function onDelete(documentId: string) {
    if (!workspaceId) return;
    await deleteDocument(workspaceId, documentId);
    setDocuments(await listDocuments(workspaceId));
  }

  async function onReindex(documentId: string) {
    if (!workspaceId) return;
    await reindexDocument(workspaceId, documentId);
    setDocuments(await listDocuments(workspaceId));
  }

  async function onCreateWorkspace() {
    if (!workspaceName.trim()) return;
    const ws = await createWorkspace(workspaceName.trim());
    const updated = await listWorkspaces();
    setWorkspaces(updated);
    setWorkspaceId(ws.id);
    setWorkspaceName("");
  }

  return (
    <div className="space-y-4">
      <Card>
        <h1 className="mb-3 text-lg font-semibold">Documents</h1>
        {error ? <p className="mb-2 text-sm text-red-600">{error}</p> : null}

        <div className="mb-3 grid gap-2 md:grid-cols-[1fr_1fr_auto]">
          <select
            className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm"
            value={workspaceId}
            onChange={(e) => setWorkspaceId(e.target.value)}
          >
            {workspaces.map((workspace) => (
              <option key={workspace.id} value={workspace.id}>
                {workspace.name}
              </option>
            ))}
          </select>
          <Input
            placeholder="New workspace name"
            value={workspaceName}
            onChange={(e) => setWorkspaceName(e.target.value)}
          />
          <Button onClick={onCreateWorkspace}>Create Workspace</Button>
        </div>

        <div className="grid gap-2 md:grid-cols-[1fr_auto]">
          <Input type="file" accept="application/pdf" onChange={(e: ChangeEvent<HTMLInputElement>) => setFile(e.target.files?.[0] ?? null)} />
          <Button disabled={!file || loading || !workspaceId} onClick={onUpload}>
            {loading ? "Uploading..." : "Upload PDF"}
          </Button>
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 text-base font-semibold">{activeWorkspace ? `${activeWorkspace.name} Documents` : "Documents"}</h2>
        <div className="space-y-2">
          {documents.map((document) => (
            <div key={document.id} className="rounded-lg border border-slate-200 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div>
                  <div className="font-medium">{document.title}</div>
                  <div className="text-xs text-slate-500">Status: {document.status}</div>
                  {document.error_message ? <div className="text-xs text-red-600">{document.error_message}</div> : null}
                </div>
                <div className="flex gap-2">
                  <Button className="bg-slate-600 hover:bg-slate-700" onClick={() => void onReindex(document.id)}>
                    Reindex
                  </Button>
                  <Button className="bg-red-600 hover:bg-red-700" onClick={() => void onDelete(document.id)}>
                    Delete
                  </Button>
                </div>
              </div>
            </div>
          ))}
          {documents.length === 0 ? <div className="text-sm text-slate-500">No documents uploaded yet.</div> : null}
        </div>
      </Card>
    </div>
  );
}
