import type { Metadata } from "next";
import Link from "next/link";

import "./globals.css";

export const metadata: Metadata = {
  title: "RAG SaaS",
  description: "Multi-tenant RAG platform for PDF chat"
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <header className="border-b border-slate-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3">
            <div className="font-semibold text-slate-900">RAG SaaS</div>
            <nav className="flex gap-4 text-sm">
              <Link href="/documents">Documents</Link>
              <Link href="/chat">Chat</Link>
              <Link href="/login">Login</Link>
            </nav>
          </div>
        </header>
        <main className="mx-auto max-w-7xl p-4">{children}</main>
      </body>
    </html>
  );
}
