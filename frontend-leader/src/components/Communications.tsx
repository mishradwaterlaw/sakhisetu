import { useEffect, useState } from "react";
import {
  Inbox as InboxIcon,
  Megaphone,
  MessageCircle,
  Phone,
  Search,
  SlidersHorizontal,
} from "lucide-react";
import { type Order } from "../workspace";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "./ui/tabs-toast";
import { channels, day, time, useInbox, type Notice, type Inbox } from "./conversation-data";
import { Avatar, ConversationWorkspace, Draft, NoThread } from "./ConversationWorkspace";
import "./communications.css";

const whatsapp = "whatsapp_smartphone";
const filters = ["All", "Orders", "Tasks", "General"];
function useSmallScreen() {
  const [small, setSmall] = useState(() => window.matchMedia("(max-width: 700px)").matches);
  useEffect(() => {
    const media = window.matchMedia("(max-width: 700px)");
    const change = () => setSmall(media.matches);
    media.addEventListener("change", change);
    return () => media.removeEventListener("change", change);
  }, []);
  return small;
}
function Notices({ inbox }: { inbox: Inbox }) {
  const [records, setRecords] = useState<Notice[]>([]);
  const [state, setState] = useState("Loading notices…");
  useEffect(() => {
    const controller = new AbortController();
    inbox
      .request<{ announcements: Notice[] }>("/announcements", { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) {
          setRecords(data.announcements);
          setState("");
        }
      })
      .catch((err) => {
        if (!controller.signal.aborted) setState(err.message);
      });
    return () => controller.abort();
  }, [inbox.request, inbox.revision]);
  return (
    <Card className="comm-notices">
      <h2>
        <Megaphone size={20} />
        Group announcements
      </h2>
      {state ? (
        <p role="status">
          {state} {state !== "Loading notices…" && <Button onClick={inbox.refresh}>Retry</Button>}
        </p>
      ) : records.length ? (
        records.map((n) => (
          <article key={n.id}>
            <small>
              {day(n.created_at)} · {time(n.created_at)} · {channels[n.channel] || n.channel}
            </small>
            <h3>{n.title}</h3>
            <p>{n.text}</p>
          </article>
        ))
      ) : (
        <div className="comm-empty">
          <Megaphone />
          <h3>No group notices yet</h3>
          <p>Your group’s payout review and approval notices will appear here.</p>
        </div>
      )}
    </Card>
  );
}

export function Communications({
  shgId,
  leaderId,
  orders,
  openOrder,
  onChange,
}: {
  shgId: string;
  leaderId: string;
  orders: Order[];
  openOrder: (id: string) => void;
  onChange: (message: string) => void;
}) {
  const [channel, setChannel] = useState(whatsapp);
  const [other, setOther] = useState("all");
  const [filter, setFilter] = useState("All");
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState("");
  const small = useSmallScreen();
  const inbox = useInbox(shgId, leaderId, query);
  const source = channel === "other" ? other : channel;
  const visible = inbox.threads.filter(
    (t) =>
      (source === "all" || (source === "review" ? t.needs_review : t.channel === source)) &&
      (filter === "All" || t.topics.includes(filter.toLowerCase())),
  );
  const current = visible.find((t) => t.id === selected) || (!small ? visible[0] : undefined);
  const currentId = current?.id;
  useEffect(() => {
    if (!small && currentId) setSelected(currentId);
  }, [small, currentId]);
  const threadOpen = Boolean(small && current);
  function switchChannel(value: string) {
    setChannel(value);
    setFilter("All");
    setQuery("");
    setSelected("");
  }
  function back() {
    const id = selected;
    setSelected("");
    requestAnimationFrame(() => document.getElementById(`thread-${id}`)?.focus());
  }
  return (
    <div className="comm-page">
      <div className="page-heading">
        <div>
          <h1>Communications</h1>
          <p>Coordinate with your members across WhatsApp and voice calls.</p>
        </div>
      </div>
      <Tabs value={channel} onValueChange={switchChannel}>
        <div className="comm-toolbar">
          <TabsList className="comm-tabs" aria-label="Communication channel">
            <TabsTrigger value={whatsapp}>
              <MessageCircle />
              WhatsApp
            </TabsTrigger>
            <TabsTrigger value="basic_phone_voice">
              <Phone />
              Voice calls
            </TabsTrigger>
            <TabsTrigger value="announcements">
              <Megaphone />
              Announcements
            </TabsTrigger>
            <TabsTrigger value="other">
              <SlidersHorizontal />
              More
            </TabsTrigger>
          </TabsList>
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="primary" className="comm-announcement">
                <Megaphone size={18} />
                <span>Draft announcement</span>
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogTitle>Draft announcement</DialogTitle>
              <DialogDescription>
                Prepare a group update and copy it when you’re ready to share.
              </DialogDescription>
              <Draft storageKey={`sakhi.announcement.${shgId}.${leaderId}`} announcement />
            </DialogContent>
          </Dialog>
        </div>
        <TabsContent value={channel}>
          {channel === "announcements" ? (
            <Notices inbox={inbox} />
          ) : (
            <div className={`comm-grid ${threadOpen ? "show-thread" : ""}`}>
              <Card className="comm-list">
                <div className="comm-list-tools">
                  {channel === "other" && (
                    <label className="field">
                      Inbox
                      <select
                        value={other}
                        onChange={(e) => {
                          setOther(e.target.value);
                          setSelected("");
                        }}
                      >
                        <option value="all">All channels</option>
                        <option value="janai_cafe">JanAI Café</option>
                        <option value="leader_manual">Manual entries</option>
                        <option value="review">Needs review</option>
                      </select>
                    </label>
                  )}
                  <label className="comm-search">
                    <Search size={17} />
                    <input
                      type="search"
                      aria-label="Search conversations"
                      maxLength={500}
                      placeholder="Search conversations…"
                      value={query}
                      onChange={(e) => setQuery(e.target.value)}
                    />
                  </label>
                  <div className="comm-filters" aria-label="Conversation topics">
                    {filters.map((f) => (
                      <button key={f} aria-pressed={filter === f} onClick={() => setFilter(f)}>
                        {f}
                      </button>
                    ))}
                  </div>
                </div>
                <div className="comm-rows">
                  {inbox.error && (
                    <div className="error-box" role="alert">
                      {inbox.error} <button onClick={inbox.refresh}>Retry</button>
                    </div>
                  )}
                  {inbox.loading ? (
                    <p className="comm-muted" role="status">
                      Loading conversations…
                    </p>
                  ) : visible.length ? (
                    visible.map((t, i) => (
                      <button
                        id={`thread-${t.id}`}
                        className="comm-row"
                        aria-pressed={current?.id === t.id}
                        key={t.id}
                        onClick={() => setSelected(t.id)}
                      >
                        <Avatar title={t.title} tone={i} />
                        <span className="comm-row-content">
                          <strong>{t.title}</strong>
                          <small>{t.preview}</small>
                        </span>
                        <span className="comm-row-meta">
                          <time>
                            {day(t.updated_at) === "Today" ? time(t.updated_at) : day(t.updated_at)}
                          </time>
                          {t.unread > 0 && (
                            <span className="comm-unread" aria-label={`${t.unread} unread`}>
                              {t.unread}
                            </span>
                          )}
                        </span>
                      </button>
                    ))
                  ) : (
                    !inbox.error && (
                      <div className="comm-empty">
                        <InboxIcon />
                        <h3>No conversations</h3>
                        <p>
                          {query || filter !== "All"
                            ? "Try another search or topic."
                            : "Incoming messages for this channel will appear here."}
                        </p>
                      </div>
                    )
                  )}
                </div>
              </Card>
              {current ? (
                <ConversationWorkspace
                  key={current.id}
                  thread={current}
                  inbox={inbox}
                  leaderId={leaderId}
                  openOrder={openOrder}
                  orders={orders}
                  onChange={onChange}
                  back={back}
                />
              ) : (
                <NoThread />
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
