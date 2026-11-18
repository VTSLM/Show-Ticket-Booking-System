"use client";
// TicketFlow assistant: a chat panel available on customer pages.
// The conversation lives only in this tab's memory; nothing is saved.
import { Fragment, useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuth } from "@/contexts/AuthContext";
import { chatApi, ChatContext, ChatMessage } from "@/lib/api";

const MAX_LENGTH = 500;
const HISTORY_SENT = 10;
const HIDDEN_ON = ["/manager", "/admin", "/auth"];

function contextFromPath(path: string): ChatContext {
  const id = "([0-9a-fA-F-]{36})";
  const event = path.match(new RegExp(`^/events/${id}`));
  const show = path.match(new RegExp(`^/shows/${id}`));
  const booking = path.match(new RegExp(`^/bookings/${id}`));
  return {
    ...(event && { event_id: event[1] }),
    ...(show && { show_id: show[1] }),
    ...(booking && { booking_id: booking[1] }),
  };
}

function suggestionsFor(context: ChatContext, loggedIn: boolean): string[] {
  if (context.event_id || context.show_id) {
    return ["Are there seats left?", "What do people think of this?", "Suggest something similar"];
  }
  if (context.booking_id) {
    return ["Can I still cancel this booking?", "How do I get my ticket?", "When is my show?"];
  }
  return loggedIn
    ? ["My upcoming bookings", "What's on this weekend?", "Recommend something for me", "How do refunds work?"]
    : ["What's on this weekend?", "Top rated movies", "How does booking work?", "How do refunds work?"];
}

/** Renders text with markdown-style [label](/path) links. Only in-app paths become links. */
function RichText({ text, onNavigate }: { text: string; onNavigate: () => void }) {
  const parts = text.split(/(\[[^\]]+\]\([^)\s]+\))/g);
  return (
    <>
      {parts.map((part, i) => {
        const m = part.match(/^\[([^\]]+)\]\(([^)\s]+)\)$/);
        if (m && m[2].startsWith("/") && !m[2].startsWith("//")) {
          return (
            <Link key={i} href={m[2]} onClick={onNavigate}
                  className="font-semibold text-[#4a91ff] underline underline-offset-2 hover:text-white">
              {m[1]}
            </Link>
          );
        }
        // Drop markdown bold markers, keep everything else as plain text
        return <Fragment key={i}>{(m ? m[1] : part).replace(/\*\*/g, "")}</Fragment>;
      })}
    </>
  );
}

export default function ChatWidget() {
  const pathname = usePathname() || "/";
  const { profile } = useAuth();
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const context = useMemo(() => contextFromPath(pathname), [pathname]);
  const suggestions = suggestionsFor(context, !!profile);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, sending]);

  useEffect(() => {
    if (open) inputRef.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  if (HIDDEN_ON.some(prefix => pathname.startsWith(prefix))) return null;

  const send = async (text: string) => {
    const message = text.trim().slice(0, MAX_LENGTH);
    if (!message || sending) return;
    const history = messages.slice(-HISTORY_SENT);
    setMessages(m => [...m, { role: "user", content: message }]);
    setInput("");
    setError(null);
    setSending(true);
    let started = false;
    // Updaters stay pure (React may run them twice in development)
    const appendText = (text: string) => {
      if (!started) {
        started = true;
        setMessages(m => [...m, { role: "assistant", content: text }]);
      } else {
        setMessages(m => {
          const last = m[m.length - 1];
          return [...m.slice(0, -1), { ...last, content: last.content + text }];
        });
      }
    };
    try {
      await chatApi.stream(message, history, context, event => {
        if (event.type === "status") setStatus(event.text);
        else if (event.type === "delta") { setStatus(null); appendText(event.text); }
        else if (event.type === "error") setError(event.message);
      });
    } catch (err) {
      const detail = err instanceof Error ? err.message : "";
      setError(detail.startsWith("Too many requests") || detail.includes("available")
        ? detail : "Something went wrong. Please try again.");
    } finally {
      setSending(false);
      setStatus(null);
    }
  };

  return (
    <>
      {!open && (
        <button
          onClick={() => setOpen(true)}
          className="fixed bottom-5 right-5 z-50 flex items-center gap-2 rounded-full bg-[var(--blue)] px-5 py-3 font-bold text-white shadow-[0_12px_32px_rgba(40,124,255,0.35)] transition hover:-translate-y-0.5 hover:bg-[var(--blue-hover)]"
          aria-label="Open the TicketFlow assistant"
        >
          <span aria-hidden>💬</span> Ask TicketFlow
        </button>
      )}

      {open && (
        <section
          role="dialog"
          aria-label="TicketFlow assistant"
          className="card fixed bottom-0 right-0 z-50 flex h-[100dvh] w-full flex-col sm:bottom-5 sm:right-5 sm:h-[min(620px,80vh)] sm:w-[390px]"
        >
          <header className="flex items-center justify-between border-b border-[var(--border)] bg-[var(--surface-raised)] px-4 py-3">
            <div>
              <p className="font-bold text-white">TicketFlow Assistant</p>
              <p className="text-xs text-[var(--muted)]">Find shows, check bookings, get help</p>
            </div>
            <div className="flex items-center gap-1">
              {messages.length > 0 && (
                <button onClick={() => { setMessages([]); setError(null); }}
                        className="rounded-lg px-2 py-1 text-xs text-[var(--muted)] hover:bg-white/5 hover:text-white">
                  New chat
                </button>
              )}
              <button onClick={() => setOpen(false)} aria-label="Close assistant"
                      className="rounded-lg px-2 py-1 text-lg leading-none text-[var(--muted)] hover:bg-white/5 hover:text-white">
                ×
              </button>
            </div>
          </header>

          <div ref={listRef} className="flex-1 space-y-3 overflow-y-auto px-4 py-4" aria-live="polite">
            {messages.length === 0 && (
              <div className="text-sm text-[var(--muted)]">
                <p className="mb-1 text-base text-white">
                  Hi{profile?.name ? ` ${String(profile.name).split(" ")[0]}` : ""}! 👋
                </p>
                <p>Ask me about shows, prices, seats, reviews{profile ? ", your bookings" : ""} or how TicketFlow works. You can write in English, Hindi or Gujarati.</p>
                {!profile && (
                  <p className="mt-2">
                    <Link href="/auth/login" className="text-[#4a91ff] underline">Log in</Link> to ask about your own bookings.
                  </p>
                )}
              </div>
            )}

            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "flex justify-end" : "flex justify-start"}>
                <div className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-3.5 py-2.5 text-sm leading-relaxed ${
                  m.role === "user"
                    ? "rounded-br-sm bg-[var(--blue)] text-white"
                    : "rounded-bl-sm border border-[var(--border)] bg-[var(--surface-raised)] text-[var(--foreground)]"
                }`}>
                  {m.role === "assistant" ? <RichText text={m.content} onNavigate={() => setOpen(false)} /> : m.content}
                </div>
              </div>
            ))}

            {sending && messages[messages.length - 1]?.role !== "assistant" && (
              <div className="flex justify-start">
                <div className="rounded-2xl rounded-bl-sm border border-[var(--border)] bg-[var(--surface-raised)] px-3.5 py-2.5 text-sm text-[var(--muted)]">
                  {status || "Thinking…"}
                </div>
              </div>
            )}
            {error && <p role="alert" className="text-sm text-red-400">{error}</p>}
          </div>

          {messages.length === 0 && (
            <div className="flex flex-wrap gap-2 px-4 pb-2">
              {suggestions.map(s => (
                <button key={s} onClick={() => send(s)} disabled={sending}
                        className="rounded-full border border-[var(--border)] bg-[var(--surface-raised)] px-3 py-1.5 text-xs text-[var(--foreground)] transition hover:border-[var(--blue)] disabled:opacity-50">
                  {s}
                </button>
              ))}
            </div>
          )}

          <form
            onSubmit={e => { e.preventDefault(); send(input); }}
            className="flex items-end gap-2 border-t border-[var(--border)] px-3 py-3"
          >
            <label htmlFor="chat-input" className="sr-only">Message</label>
            <textarea
              id="chat-input"
              ref={inputRef}
              rows={1}
              value={input}
              maxLength={MAX_LENGTH}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(input); }
              }}
              placeholder="Ask anything about shows or bookings…"
              className="input max-h-28 min-h-[44px] resize-none text-sm"
            />
            <button type="submit" disabled={sending || !input.trim()} className="btn-primary px-4 disabled:opacity-50">
              Send
            </button>
          </form>
          {input.length > MAX_LENGTH - 50 && (
            <p className="px-4 pb-2 text-right text-xs text-[var(--muted)]">{input.length}/{MAX_LENGTH}</p>
          )}
        </section>
      )}
    </>
  );
}
