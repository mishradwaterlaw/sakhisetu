import { Fragment, useEffect, useLayoutEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Box,
  Check,
  ChevronRight,
  Copy,
  Info,
  Link2,
  ListChecks,
  LockKeyhole,
  MessageCircle,
  PencilLine,
  UsersRound,
  Zap,
} from "lucide-react";
import { initials, type Order } from "../workspace";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./ui/dialog";
import { day, subtitle, time, type Conversation, type Inbox, type Timeline } from "./conversation-data";
import { OnboardBuyer } from "./OnboardBuyer";

export function Avatar({
  title,
  tone = 0,
  small = false,
}: {
  title: string;
  tone?: number;
  small?: boolean;
}) {
  return (
    <span aria-hidden="true" className={`comm-avatar tone-${tone % 5}${small ? " small" : ""}`}>
      {initials(title)}
    </span>
  );
}

function Identity({ thread, data }: { thread: Conversation; data: Timeline | null }) {
  return (
    <div className="comm-identity">
      <Avatar title={thread.title} />
      <div>
        <h2>{thread.title}</h2>
        <p>{subtitle(thread, data)}</p>
      </div>
    </div>
  );
}

export function Draft({
  storageKey,
  announcement = false,
}: {
  storageKey: string;
  announcement?: boolean;
}) {
  const [value, setValue] = useState(() => {
    try {
      return sessionStorage.getItem(storageKey) || "";
    } catch {
      return "";
    }
  });
  const [status, setStatus] = useState("");
  const hint = announcement ? "Announcement draft" : "Reply draft";
  function edit(text: string) {
    setValue(text);
    try {
      if (text) sessionStorage.setItem(storageKey, text);
      else sessionStorage.removeItem(storageKey);
      setStatus("");
    } catch {
      setStatus("Draft is available until you leave this view.");
    }
  }
  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setStatus("Draft copied.");
    } catch {
      setStatus("Select the draft text to copy it.");
    }
  }
  return (
    <div className={`comm-draft ${announcement ? "announcement-draft" : ""}`}>
      <div className="comm-compose">
        <span aria-hidden="true">
          <PencilLine size={18} />
        </span>
        <textarea
          rows={announcement ? 5 : 1}
          aria-label={hint}
          placeholder={announcement ? "Write an announcement draft…" : "Draft a reply…"}
          value={value}
          onChange={(e) => edit(e.target.value)}
        />
        <button
          type="button"
          className="comm-copy"
          onClick={copy}
          disabled={!value.trim()}
          aria-label="Copy draft"
          title="Copy draft"
        >
          {status === "Draft copied." ? <Check size={17} /> : <Copy size={17} />}
        </button>
      </div>
      <small role="status">
        <LockKeyhole size={11} />
        {status || "Private draft in this tab · No messages sent"}
      </small>
    </div>
  );
}

type WorkspaceProps = {
  thread: Conversation;
  inbox: Inbox;
  leaderId: string;
  orders: Order[];
  openOrder: (id: string) => void;
  onChange: (message: string) => void;
  back: () => void;
};

function Details({
  thread,
  data,
  orders,
  openOrder,
  link,
  linking,
  linkError,
}: {
  thread: Conversation;
  data: Timeline | null;
  orders: Order[];
  openOrder: WorkspaceProps["openOrder"];
  link: (id: string) => Promise<boolean>;
  linking: boolean;
  linkError: string;
}) {
  const [dialog, setDialog] = useState<"link" | "people" | "plan" | null>(null);
  const available = orders.filter((o) => !data?.orders.some((linked) => linked.id === o.id));
  const [chosen, setChosen] = useState("");
  const selectId = available.some((o) => o.id === chosen) ? chosen : available[0]?.id;
  const people = data?.participants || [];
  const linked = data?.orders || [];
  return (
    <>
      <div className="comm-context-heading">
        <Identity thread={thread} data={data} />
        <button
          className="comm-icon"
          aria-label="Participant details"
          title="Participant details"
          disabled={!people.length}
          onClick={() => setDialog("people")}
        >
          <Info size={18} />
        </button>
      </div>
      <section className="comm-context-section">
        <h3>
          <Box />
          Related orders
        </h3>
        {linked.length ? (
          linked.map((o) => (
            <button key={o.id} onClick={() => openOrder(o.id)} className="comm-order">
              <span className="comm-order-icon">
                <Box size={20} />
              </span>
              <span>
                <strong>{o.code}</strong>
                <small>
                  {o.product} · {o.quantity} pcs
                </small>
              </span>
              <ChevronRight size={17} />
            </button>
          ))
        ) : (
          <p>{data ? "No orders linked yet." : "Loading orders…"}</p>
        )}
      </section>
      <section className="comm-context-section">
        <h3>
          <Zap />
          Quick actions
        </h3>
        <button
          className="comm-action"
          disabled={!linked.length}
          onClick={() => (linked.length === 1 ? openOrder(linked[0].id) : setDialog("plan"))}
        >
          <ListChecks />
          Review work plan
        </button>
        <button
          className="comm-action"
          disabled={!available.length || !data}
          onClick={() => setDialog("link")}
        >
          <Link2 />
          Link an order
        </button>
        <button className="comm-action" disabled={!people.length} onClick={() => setDialog("people")}>
          <UsersRound />
          View participants
        </button>
      </section>
      <Dialog
        open={dialog !== null}
        onOpenChange={(open) => {
          if (!open) setDialog(null);
        }}
      >
        <DialogContent>
          <DialogTitle>
            {dialog === "people" ? "Participants" : dialog === "link" ? "Link an order" : "Choose an order"}
          </DialogTitle>
          <DialogDescription>{thread.title}</DialogDescription>
          {dialog === "people" ? (
            <ul className="comm-people">
              {people.map((name, i) => (
                <li key={i}>
                  <Avatar title={name} tone={i} small />
                  {name}
                </li>
              ))}
            </ul>
          ) : dialog === "link" ? (
            <form
              className="form-stack"
              onSubmit={async (e) => {
                e.preventDefault();
                if (selectId && (await link(selectId))) setDialog(null);
              }}
            >
              <label className="field">
                Group order
                <select value={selectId || ""} onChange={(e) => setChosen(e.target.value)}>
                  {available.map((o) => (
                    <option key={o.id} value={o.id}>
                      {o.order_code} · {o.product_name || "Order"}
                    </option>
                  ))}
                </select>
              </label>
              {linkError && (
                <p role="alert" className="error-box">
                  {linkError}
                </p>
              )}
              <Button variant="primary" disabled={linking || !selectId}>
                {linking ? "Linking…" : "Link order"}
              </Button>
            </form>
          ) : (
            <div className="comm-people">
              {linked.map((o) => (
                <Button key={o.id} onClick={() => openOrder(o.id)}>
                  {o.code}
                  <ChevronRight size={16} />
                </Button>
              ))}
            </div>
          )}
        </DialogContent>
      </Dialog>
    </>
  );
}

export function ConversationWorkspace({
  thread,
  inbox,
  leaderId,
  orders,
  openOrder,
  onChange,
  back,
}: WorkspaceProps) {
  const { request, read, refresh } = inbox;
  const [data, setData] = useState<Timeline | null>(null);
  const [error, setError] = useState("");
  const [revision, setRevision] = useState(0);
  const [older, setOlder] = useState(false);
  const [linking, setLinking] = useState(false);
  const [linkError, setLinkError] = useState("");
  const scroll = useRef<HTMLDivElement>(null);
  const pageRequest = useRef<AbortController | null>(null);
  const adjust = useRef<number | "bottom" | null>("bottom");
  const url = `/conversations/${thread.id}`;
  useEffect(() => {
    const controller = new AbortController();
    const options = { signal: controller.signal };
    async function load() {
      try {
        const res = await request<Timeline>(url, options);
        if (controller.signal.aborted) return;
        adjust.current = "bottom";
        setData(res);
        setError("");
        const latest = res.messages.at(-1);
        if (latest && document.visibilityState === "visible")
          await read(res.id, latest.position, controller.signal);
      } catch (e) {
        if (!controller.signal.aborted) setError((e as Error).message);
      }
    }
    void load();
    function visible() {
      if (document.visibilityState === "visible") void load();
    }
    document.addEventListener("visibilitychange", visible);
    return () => {
      controller.abort();
      pageRequest.current?.abort();
      document.removeEventListener("visibilitychange", visible);
    };
  }, [request, read, url, thread.latest, revision]);
  useLayoutEffect(() => {
    if (!scroll.current || adjust.current === null) return;
    scroll.current.scrollTop =
      adjust.current === "bottom"
        ? scroll.current.scrollHeight
        : scroll.current.scrollHeight - adjust.current;
    adjust.current = null;
  }, [data]);
  async function earlier() {
    if (!data?.before || older) return;
    const controller = new AbortController();
    pageRequest.current = controller;
    setOlder(true);
    try {
      const page = await request<Timeline>(`${url}?before=${data.before}`, { signal: controller.signal });
      if (controller.signal.aborted) return;
      const el = scroll.current;
      adjust.current = el ? el.scrollHeight - el.scrollTop : null;
      setData(
        (current) =>
          current && { ...current, before: page.before, messages: [...page.messages, ...current.messages] },
      );
    } catch (e) {
      if (!controller.signal.aborted) setError((e as Error).message);
    } finally {
      setOlder(false);
    }
  }
  async function link(id: string) {
    setLinking(true);
    setLinkError("");
    try {
      await request(`${url}/orders/${id}`, { method: "PUT" });
      setRevision((n) => n + 1);
      refresh();
      return true;
    } catch (e) {
      setLinkError((e as Error).message);
      return false;
    } finally {
      setLinking(false);
    }
  }
  const details = { thread, data, orders, openOrder, link, linking, linkError };
  return (
    <>
      <Card className="comm-thread">
        <header className="comm-thread-heading">
          <button className="comm-back comm-icon" onClick={back} aria-label="Back to conversations">
            <ArrowLeft size={19} />
          </button>
          <Identity thread={thread} data={data} />
          <Dialog>
            <DialogTrigger asChild>
              <button
                className="comm-icon comm-info"
                title="Conversation details"
                aria-label="Conversation details"
              >
                <Info size={19} />
              </button>
            </DialogTrigger>
            <DialogContent className="comm-details-dialog">
              <DialogTitle className="sr-only">Conversation details</DialogTitle>
              <DialogDescription className="sr-only">Participants and related orders</DialogDescription>
              <Details {...details} />
            </DialogContent>
          </Dialog>
        </header>
        <div className="comm-timeline" ref={scroll} aria-label="Conversation history">
          {error && (
            <div className="error-box" role="alert">
              {error} <button onClick={() => setRevision((n) => n + 1)}>Retry</button>
            </div>
          )}
          {!data && !error && (
            <p className="comm-muted" role="status">
              Loading conversation…
            </p>
          )}
          {data?.before && (
            <button className="comm-earlier" onClick={earlier} disabled={older}>
              {older ? "Loading…" : "Earlier messages"}
            </button>
          )}
          {data?.messages.map((m, i, all) => {
            const outgoing = m.direction === "outgoing";
            return (
              <Fragment key={m.position}>
                {(!i || day(m.created_at) !== day(all[i - 1].created_at)) && (
                  <div className="comm-day">
                    <span>{day(m.created_at)}</span>
                  </div>
                )}
                <div className={`comm-message ${outgoing ? "outgoing" : "incoming"}`}>
                  {!outgoing && <Avatar small title={m.sender} />}
                  <div className="comm-bubble">
                    {!outgoing && <b>{m.sender}</b>}
                    <p>{m.text}</p>
                    {m.sample_photo && (
                      <Dialog>
                        <DialogTrigger asChild>
                          <button className="comm-photo" aria-label="Enlarge tote seam photo">
                            <img
                              src="/tote-seam-sample.webp"
                              alt="Double stitching on the cotton tote sample"
                              width="680"
                              height="453"
                            />
                          </button>
                        </DialogTrigger>
                        <DialogContent>
                          <DialogTitle>Tote seam sample</DialogTitle>
                          <DialogDescription>Photo from the demo workshop conversation.</DialogDescription>
                          <img
                            className="comm-full-photo"
                            src="/tote-seam-sample.webp"
                            alt="Close-up of the double-stitched cotton seam"
                          />
                        </DialogContent>
                      </Dialog>
                    )}
                    {m.quarantined && m.inbound_id && (
                      <OnboardBuyer
                        messageId={m.inbound_id}
                        leaderId={leaderId}
                        onComplete={() => {
                          refresh();
                          setRevision((n) => n + 1);
                          onChange("Buyer onboarded.");
                        }}
                      />
                    )}
                    {m.needs_review && <small className="comm-review">Needs review</small>}
                    <time dateTime={m.created_at} title={new Date(m.created_at).toLocaleString()}>
                      {time(m.created_at)}
                    </time>
                  </div>
                </div>
              </Fragment>
            );
          })}
        </div>
        <Draft key={thread.id} storageKey={`sakhi.reply.${leaderId}.${thread.id}`} />
      </Card>
      <Card className="comm-context">
        <Details {...details} />
      </Card>
    </>
  );
}

export function NoThread() {
  return (
    <Card className="comm-no-thread">
      <MessageCircle />
      <h2>Conversation history</h2>
      <p>Select a conversation to see messages and related orders.</p>
    </Card>
  );
}
