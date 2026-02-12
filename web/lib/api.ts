import { getAccessToken } from "@/lib/auth";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Tokens = {
  access_token: string;
  refresh_token: string;
  token_type: string;
};

export type Workspace = {
  id: string;
  name: string;
};

export type DocumentItem = {
  id: string;
  workspace_id: string;
  title: string;
  status: "UPLOADING" | "PROCESSING" | "READY" | "FAILED";
  file_size: number;
  error_message?: string | null;
  created_at: string;
};

export type Citation = {
  chunk_id: string;
  document_id: string;
  title: string;
  page: number;
  snippet: string;
};

export type ChatFinal = {
  answer: string;
  citations: Citation[];
  retrieved_chunks?: Array<Record<string, unknown>>;
};

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAccessToken();
  const headers = new Headers(init?.headers ?? {});
  headers.set("Content-Type", headers.get("Content-Type") ?? "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const res = await fetch(`${API_URL}${path}`, { ...init, headers });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `Request failed with status ${res.status}`);
  }
  return (await res.json()) as T;
}

export function register(email: string, password: string, workspaceName?: string) {
  return request<Tokens>("/auth/register", {
    method: "POST",
    body: JSON.stringify({ email, password, workspace_name: workspaceName ?? null }),
  });
}

export function login(email: string, password: string) {
  return request<Tokens>("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password }),
  });
}

export function getMe() {
  return request<{ user: { id: string; email: string }; workspaces: Workspace[] }>("/me");
}

export function listWorkspaces() {
  return request<Workspace[]>("/workspaces");
}

export function createWorkspace(name: string) {
  return request<Workspace>("/workspaces", {
    method: "POST",
    body: JSON.stringify({ name }),
  });
}

export function listDocuments(workspaceId: string) {
  const query = new URLSearchParams({ workspace_id: workspaceId });
  return request<DocumentItem[]>(`/documents?${query.toString()}`);
}

export async function uploadDocument(workspaceId: string, file: File) {
  const token = getAccessToken();
  const formData = new FormData();
  formData.append("workspace_id", workspaceId);
  formData.append("file", file);

  const res = await fetch(`${API_URL}/documents/upload`, {
    method: "POST",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
    body: formData,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || "Upload failed");
  }

  return (await res.json()) as DocumentItem;
}

export async function deleteDocument(workspaceId: string, documentId: string) {
  const token = getAccessToken();
  const query = new URLSearchParams({ workspace_id: workspaceId });
  const res = await fetch(`${API_URL}/documents/${documentId}?${query.toString()}`, {
    method: "DELETE",
    headers: token ? { Authorization: `Bearer ${token}` } : undefined,
  });
  if (!res.ok && res.status !== 204) throw new Error("Delete failed");
}

export function reindexDocument(workspaceId: string, documentId: string) {
  return request<DocumentItem>(`/documents/${documentId}/reindex`, {
    method: "POST",
    body: JSON.stringify({ workspace_id: workspaceId }),
  });
}

export async function streamChat(params: {
  workspaceId: string;
  message: string;
  debug: boolean;
  onToken: (token: string) => void;
  onFinal: (payload: ChatFinal) => void;
}) {
  const token = getAccessToken();
  const res = await fetch(`${API_URL}/chat`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({
      workspace_id: params.workspaceId,
      message: params.message,
      debug: params.debug,
      top_k: 8,
      mmr: true,
    }),
  });

  if (!res.ok || !res.body) {
    throw new Error(`Chat failed: ${res.status}`);
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;

    buffer += decoder.decode(value, { stream: true });
    const events = buffer.split("\n\n");
    buffer = events.pop() ?? "";

    for (const rawEvent of events) {
      const lines = rawEvent.split("\n");
      const eventType = lines.find((line) => line.startsWith("event:"))?.replace("event:", "").trim();
      const dataLine = lines.find((line) => line.startsWith("data:"));
      if (!dataLine || !eventType) continue;
      const data = JSON.parse(dataLine.replace("data:", "").trim()) as any;

      if (eventType === "token") params.onToken(data.token ?? "");
      if (eventType === "final") params.onFinal(data as ChatFinal);
    }
  }
}
