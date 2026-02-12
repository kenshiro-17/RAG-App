"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { getAccessToken } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    if (getAccessToken()) {
      router.replace("/chat");
      return;
    }
    router.replace("/login");
  }, [router]);

  return <div className="p-8 text-sm text-slate-600">Redirecting...</div>;
}
