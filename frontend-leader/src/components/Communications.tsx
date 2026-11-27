import { useEffect, useState, type FormEvent } from "react";
import {
  ArrowRight,
  CalendarDays,
  Check,
  Headphones,
  Inbox,
  MessageCircle,
  MessagesSquare,
  Phone,
  Search,
  Store,
  UserPlus,
} from "lucide-react";
import { apiFetch } from "../api";
import { dateLabel, humanize, initials } from "../workspace";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs-toast";

type Message = {
  id: string;
  channel: string;
  sender: string | null;
  text: string | null;
  intent: string;
  quarantined: boolean;
  created_at: string;
  order_id: string | null;
  order_code: string | null;
};
const channels: Record<string, string> = {
  whatsapp_smartphone: "WhatsApp",
  basic_phone_voice: "Voice",
  janai_cafe: "JanAI Café",
  leader_manual: "Manual entry",
};
function needsReview(msg: Message) {
  return msg.quarantined || msg.intent === "UNROUTED";
}

function OnboardBuyer({
  message,
  leaderId,
  onComplete,
}: {
  message: Message;
  leaderId: string;
  onComplete: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      await apiFetch(`/api/leader/quarantine/${message.id}/onboard-buyer`, {
        method: "POST",
        body: JSON.stringify({ leader_id: leaderId, name: name.trim(), phone: phone.trim() }),
      });
      setOpen(false);
      onComplete();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not onboard buyer.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="primary">
          <UserPlus size={16} />
          Onboard buyer
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogTitle>Onboard buyer</DialogTitle>
        <DialogDescription>
          Confirm the sender’s details to release this message from quarantine.
        </DialogDescription>
        <form className="form-stack" onSubmit={submit}>
          <label className="field">
            Buyer name
            <input required value={name} onChange={(e) => setName(e.target.value)} />
          </label>
          <label className="field">
            Phone number
            <input type="tel" required value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          {error && (
            <p className="error-box" role="alert">
              {error}
            </p>
          )}
          <Button variant="primary" type="submit" disabled={busy || !name.trim() || !phone.trim()}>
            Confirm buyer
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export function Communications({
  shgId,
  leaderId,
  openOrder,
  onChange,
}: {
  shgId: string;
  leaderId: string;
  openOrder: (id: string) => void;
  onChange: (message: string) => void;
}) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [selected, setSelected] = useState("");
  const [channel, setChannel] = useState("all");
  const [query, setQuery] = useState("");
  const [reviewOnly, setReviewOnly] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    apiFetch<{ messages: Message[] }>(`/api/leader/shgs/${shgId}/communications`, {
      headers: { "X-Leader-Id": leaderId },
    })
      .then((res) => {
        if (active) setMessages(res.messages);
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [shgId, leaderId, revision]);
  const filtered = messages.filter(
    (msg) =>
      (channel === "all" || msg.channel === channel) &&
      (!reviewOnly || needsReview(msg)) &&
      [msg.sender || "Unknown sender", msg.text, msg.order_code].some((value) =>
        value?.toLowerCase().includes(query.trim().toLowerCase()),
      ),
  );
  const current = filtered.find((msg) => msg.id === selected) || filtered[0];
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1>Communications</h1>
          <p>Review incoming messages and the orders they belong to.</p>
        </div>
      </div>
      <Tabs value={channel} onValueChange={setChannel}>
        <TabsList aria-label="Message channel" className="channel-tabs">
          {(
            [
              ["all", "All channels", Inbox],
              ["whatsapp_smartphone", "WhatsApp", MessageCircle],
              ["basic_phone_voice", "Voice", Phone],
              ["janai_cafe", "JanAI Café", Store],
            ] as const
          ).map(([value, label, Icon]) => (
            <TabsTrigger key={value} value={value}>
              <Icon size={16} />
              {label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value={channel} className="mt-4">
          {error ? (
            <div className="error-box" role="alert">
              {error}
              <Button onClick={() => setRevision((v) => v + 1)}>Retry</Button>
            </div>
          ) : (
            <div className="inbox-layout">
              <Card className="inbox-list">
                <div className="panel-heading">
                  <h2>
                    <MessagesSquare />
                    Inbox
                  </h2>
                  <span className="number-count">{filtered.length}</span>
                </div>
                <div className="inbox-tools">
                  <div className="search-field">
                    <Search />
                    <input
                      aria-label="Search messages"
                      placeholder="Search messages…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </div>
                  <div className="filter-row">
                    <button aria-pressed={!reviewOnly} onClick={() => setReviewOnly(false)}>
                      All messages
                    </button>
                    <button aria-pressed={reviewOnly} onClick={() => setReviewOnly(true)}>
                      Needs review
                    </button>
                  </div>
                </div>
                {loading ? (
                  <p className="quiet inside" aria-busy="true">
                    Loading messages…
                  </p>
                ) : filtered.length === 0 ? (
                  <div className="empty">
                    <Inbox />
                    <h3>No messages here</h3>
                    <p>Incoming messages matching this view will appear here.</p>
                  </div>
                ) : (
                  filtered.map((msg) => (
                    <button
                      className="message-row"
                      key={msg.id}
                      aria-pressed={msg.id === current?.id}
                      onClick={() => setSelected(msg.id)}
                    >
                      <span className="avatar">{initials(msg.sender || "Unknown")}</span>
                      <span className="message-preview">
                        <strong>{msg.sender || "Unknown sender"}</strong>
                        <small>{msg.text || "Voice or media message"}</small>
                      </span>
                      <time>{dateLabel(msg.created_at)}</time>
                    </button>
                  ))
                )}
              </Card>
              <Card className="message-detail">
                {current && !loading ? (
                  <>
                    <div className="review-heading">
                      <span className="avatar large">{initials(current.sender || "Unknown")}</span>
                      <div>
                        <h2>{current.sender || "Unknown sender"}</h2>
                        <p>{channels[current.channel] || humanize(current.channel)}</p>
                      </div>
                    </div>
                    <div className="message-body">
                      <div className="message-date">
                        <CalendarDays size={14} />
                        {new Date(current.created_at).toLocaleString("en-IN", {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </div>
                      <blockquote>{current.text || "Voice or media message"}</blockquote>
                      <span className={`status-pill ${needsReview(current) ? "amber" : "sage"}`}>
                        {needsReview(current) ? <Headphones size={13} /> : <Check size={13} />}{" "}
                        {current.quarantined ? "Quarantined" : humanize(current.intent)}
                      </span>
                    </div>
                    {current.order_id && (
                      <div className="detail-action">
                        <span>Related order</span>
                        <button className="text-button" onClick={() => openOrder(current.order_id!)}>
                          {current.order_code} <ArrowRight />
                        </button>
                      </div>
                    )}
                    {current.quarantined && (
                      <div className="detail-action">
                        <OnboardBuyer
                          key={current.id}
                          message={current}
                          leaderId={leaderId}
                          onComplete={() => {
                            setRevision((v) => v + 1);
                            onChange("Buyer onboarded.");
                          }}
                        />
                      </div>
                    )}
                  </>
                ) : (
                  <div className="empty">
                    <MessageCircle />
                    <h3>Message details</h3>
                    <p>Select an incoming message to read it here.</p>
                  </div>
                )}
              </Card>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
