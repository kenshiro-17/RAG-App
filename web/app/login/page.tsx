"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";

import { Button, Card, Input } from "@/components/ui";
import { login, register } from "@/lib/api";
import { saveTokens } from "@/lib/auth";

export default function LoginPage() {
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [workspaceName, setWorkspaceName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const data =
        mode === "login"
          ? await login(email, password)
          : await register(email, password, workspaceName || undefined);
      saveTokens(data.access_token, data.refresh_token);
      router.replace("/documents");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="mx-auto max-w-md">
      <Card>
        <h1 className="mb-4 text-xl font-semibold">{mode === "login" ? "Login" : "Register"}</h1>
        <div className="mb-4 flex gap-2">
          <Button className={mode === "login" ? "" : "bg-slate-500 hover:bg-slate-600"} onClick={() => setMode("login")}>
            Login
          </Button>
          <Button className={mode === "register" ? "" : "bg-slate-500 hover:bg-slate-600"} onClick={() => setMode("register")}>
            Register
          </Button>
        </div>

        <form className="space-y-3" onSubmit={onSubmit}>
          <Input type="email" placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} required />
          <Input
            type="password"
            placeholder="Password (min 8 chars)"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          {mode === "register" ? (
            <Input
              placeholder="Workspace name (optional)"
              value={workspaceName}
              onChange={(e) => setWorkspaceName(e.target.value)}
            />
          ) : null}
          {error ? <p className="text-sm text-red-600">{error}</p> : null}
          <Button disabled={loading} type="submit">
            {loading ? "Please wait..." : mode === "login" ? "Login" : "Create account"}
          </Button>
        </form>
      </Card>
    </div>
  );
}
