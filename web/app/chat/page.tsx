"use client";

import { FormEvent, useEffect, useState } from "react";

import { Button, Card, Input } from "@/components/ui";
import { listWorkspaces, streamChat, type ChatFinal, type Citation, type Workspace } from "@/lib/api";

type Message = {
  role: "user" | "assistant";
  text: string;
};

export default function ChatPage() {
  const [workspaces, setWorkspaces] = useState<Workspace[]>([]);
  const [workspaceId, setWorkspaceId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [debug, setDebug] = useState(false);
  const [citations, setCitations] = useState<Citation[]>([]);
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null);
  const [retrievedChunks, setRetrievedChunks] = useState<Array<Record<string, unknown>>>([]);
  const [error, setError] = useState<string | null>(null);

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

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    if (!workspaceId || !input.trim() || loading) return;

    const question = input.trim();
    setInput("");
    setError(null);
    setMessages((prev) => [...prev, { role: "user", text: question }, { role: "assistant", text: "" }]);
    setLoading(true);

    try {
      await streamChat({
        workspaceId,
        message: question,
        debug,
        onToken(token) {
          setMessages((prev) => {
            const next = [...prev];
            const last = next[next.length - 1];
            if (last && last.role === "assistant") {
              last.text += token;
            }
            return next;
          });
        },
        onFinal(payload: ChatFinal) {
          setCitations(payload.citations ?? []);
          setRetrievedChunks(payload.retrieved_chunks ?? []);
        },
      });
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="grid gap-4 lg:grid-cols-[1fr_360px]">
      <Card className="space-y-4">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-lg font-semibold">Chat</h1>
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
          <label className="ml-auto flex items-center gap-2 text-sm">
            <input type="checkbox" checked={debug} onChange={(e) => setDebug(e.target.checked)} />
            Debug retrieval
          </label>
        </div>

        {error ? <p className="text-sm text-red-600">{error}</p> : null}

        <div className="h-[500px] space-y-3 overflow-y-auto rounded-lg border border-slate-200 bg-slate-50 p-3">
          {messages.map((message, idx) => (
            <div
              key={`${message.role}-${idx}`}
              className={message.role === "user" ? "text-right" : "text-left"}
            >
              <div
                className={
                  message.role === "user"
                    ? "inline-block max-w-[85%] rounded-lg bg-brand-700 px-3 py-2 text-sm text-white"
                    : "inline-block max-w-[85%] rounded-lg bg-white px-3 py-2 text-sm text-slate-900"
                }
              >
                {message.text}
              </div>
            </div>
          ))}
          {messages.length === 0 ? <div className="text-sm text-slate-500">Ask a question about your uploaded PDFs.</div> : null}
        </div>

        <form className="flex gap-2" onSubmit={onSubmit}>
          <Input
            placeholder="Ask something from your documents..."
            value={input}
            onChange={(e) => setInput(e.target.value)}
            disabled={loading}
          />
          <Button disabled={loading || !workspaceId || !input.trim()} type="submit">
            {loading ? "Streaming..." : "Send"}
          </Button>
        </form>
      </Card>

      <div className="space-y-4">
        <Card>
          <h2 className="mb-2 text-base font-semibold">Citations</h2>
          <div className="space-y-2">
            {citations.map((citation) => (
              <button
                className="w-full rounded-lg border border-slate-200 p-2 text-left text-sm hover:bg-slate-50"
                key={citation.chunk_id}
                onClick={() => setSelectedCitation(citation)}
              >
                <div className="font-medium">{citation.title}</div>
                <div className="text-xs text-slate-500">Page {citation.page}</div>
              </button>
            ))}
            {citations.length === 0 ? <div className="text-sm text-slate-500">No citations yet.</div> : null}
          </div>
          {selectedCitation ? (
            <div className="mt-3 rounded-lg bg-slate-50 p-3 text-xs text-slate-700">
              <div className="mb-1 font-medium">
                {selectedCitation.title} (p.{selectedCitation.page})
              </div>
              <p>{selectedCitation.snippet}</p>
            </div>
          ) : null}
        </Card>

        {debug ? (
          <Card>
            <h2 className="mb-2 text-base font-semibold">Retrieved Chunks (Debug)</h2>
            <pre className="max-h-80 overflow-auto rounded bg-slate-900 p-2 text-xs text-slate-100">
              {JSON.stringify(retrievedChunks, null, 2)}
            </pre>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
