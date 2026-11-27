import { useCallback, useEffect, useState } from "react";
import { apiFetch } from "../api";

export type Conversation = {
  id: string;
  title: string;
  channel: string;
  kind: string;
  is_demo: boolean;
  preview: string;
  updated_at: string;
  latest: number;
  unread: number;
  needs_review: boolean;
  topics: string[];
  order_codes: string[];
};
export type Entry = {
  position: number;
  sender: string;
  direction: string;
  text: string;
  created_at: string;
  inbound_id: string | null;
  quarantined: boolean;
  needs_review: boolean;
  sample_photo: boolean;
};
export type Timeline = {
  id: string;
  participants: string[];
  messages: Entry[];
  before: number | null;
  orders: { id: string; code: string; product: string; quantity: number; status: string }[];
};
export type Notice = { id: string; title: string; text: string; channel: string; created_at: string };
export const channels: Record<string, string> = {
  whatsapp_smartphone: "WhatsApp",
  basic_phone_voice: "Voice calls",
  janai_cafe: "JanAI Café",
  leader_manual: "Manual entry",
};

export function useInbox(shgId: string, leaderId: string, query: string) {
  const root = `/api/leader/shgs/${shgId}/communications`;
  const request = useCallback(
    <T>(path: string, init?: RequestInit) =>
      apiFetch<T>(root + path, { ...init, headers: { "X-Leader-Id": leaderId } }),
    [root, leaderId],
  );
  const [threads, setThreads] = useState<Conversation[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const refresh = useCallback(() => setRevision((n) => n + 1), []);
  useEffect(() => {
    const timer = window.setInterval(refresh, 30000);
    window.addEventListener("focus", refresh);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("focus", refresh);
    };
  }, [refresh]);
  useEffect(() => {
    const abort = new AbortController();
    const timer = window.setTimeout(
      async () => {
        try {
          const data = await request<{ conversations: Conversation[] }>(
            `/conversations?q=${encodeURIComponent(query.trim())}`,
            { signal: abort.signal },
          );
          if (!abort.signal.aborted) {
            setThreads(data.conversations);
            setError("");
          }
        } catch (e) {
          if (!abort.signal.aborted) setError((e as Error).message);
        } finally {
          if (!abort.signal.aborted) setLoading(false);
        }
      },
      query ? 150 : 0,
    );
    return () => {
      abort.abort();
      window.clearTimeout(timer);
    };
  }, [request, query, revision]);
  const read = useCallback(
    async (id: string, position: number, signal: AbortSignal) => {
      await request(`/conversations/${id}/read`, {
        method: "PUT",
        body: JSON.stringify({ position }),
        signal,
      });
      if (!signal.aborted)
        setThreads((rows) =>
          rows.map((t) => (t.id === id && t.latest === position ? { ...t, unread: 0 } : t)),
        );
    },
    [request],
  );
  return { request, threads, refresh, read, error, loading, revision };
}
export type Inbox = ReturnType<typeof useInbox>;

const clock = new Intl.DateTimeFormat("en-IN", { hour: "numeric", minute: "2-digit" });
const date = new Intl.DateTimeFormat("en-IN", { day: "numeric", month: "short" });
export const time = (stamp: string) => clock.format(new Date(stamp));
export function day(stamp: string) {
  const d = new Date(stamp),
    today = new Date();
  if (d.toDateString() === today.toDateString()) return "Today";
  today.setDate(today.getDate() - 1);
  return d.toDateString() === today.toDateString()
    ? "Yesterday"
    : date.format(d) + (d.getFullYear() !== today.getFullYear() ? ` ${d.getFullYear()}` : "");
}
export function subtitle(thread: Conversation, timeline?: Timeline | null) {
  if (thread.kind === "workspace") {
    const count = timeline?.participants.length;
    return [count === undefined ? "Group conversation" : `${count} members`, thread.is_demo && "Demo"]
      .filter(Boolean)
      .join(" · ");
  }
  const who =
    thread.kind === "unknown"
      ? "Unverified contact"
      : thread.kind.charAt(0).toUpperCase() + thread.kind.slice(1);
  return `${who} · ${channels[thread.channel] || "Conversation"}`;
}
