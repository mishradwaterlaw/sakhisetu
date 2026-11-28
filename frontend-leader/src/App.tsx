import { useCallback, useEffect, useRef, useState } from "react";
import {
  AlertCircle,
  Bell,
  ChartNoAxesColumnIncreasing,
  Check,
  ChevronRight,
  CircleDollarSign,
  Factory,
  House,
  LayoutGrid,
  Menu,
  MessageSquare,
  Package,
  Search,
  Store,
  Users,
  Wallet,
  type LucideIcon,
} from "lucide-react";
import { apiFetch } from "./api";
import { type DashboardData, type Order, type Page, initials, money } from "./workspace";
import { Overview } from "./components/Overview";
import { Orders } from "./components/Orders";
import { Communications } from "./components/Communications";
import { CafeView } from "./components/CafeView";
import { BankSummaryPanel, ImpactMetricWidget, LiveMemberTrackingTable, ManualOrderForm } from "./components/LeaderPanels";
import { MemberView } from "./components/MemberView";
import { StatusBadge } from "./components/StatusBadge";
import { Button } from "./components/ui/button";
import { Card } from "./components/ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle } from "./components/ui/dialog";
import { Toast, ToastProvider, ToastViewport } from "./components/ui/tabs-toast";

const sections: { id: Page; title: string; icon: LucideIcon }[] = [
  { id: "dashboard", title: "Dashboard", icon: LayoutGrid },
  { id: "orders", title: "Orders", icon: Package },
  { id: "production", title: "Production", icon: Factory },
  { id: "members", title: "Members", icon: Users },
  { id: "communications", title: "Communications", icon: MessageSquare },
  { id: "payouts", title: "Payouts", icon: Wallet },
  { id: "insights", title: "Insights", icon: ChartNoAxesColumnIncreasing },
  { id: "cafe", title: "JanAI Café", icon: Store },
];
function routeFromHash() {
  const [page, id] = window.location.hash.slice(1).split("/");
  return { page: sections.find((item) => item.id === page)?.id || ("dashboard" as Page), id: id || null };
}

export default function App() {
  const [route, setRoute] = useState(routeFromHash);
  const [dash, setDash] = useState<DashboardData | null>(null);
  const [leaderId, setLeaderId] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [toast, setToast] = useState("");
  const [searchOpen, setSearchOpen] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const [createOpen, setCreateOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmBatch, setConfirmBatch] = useState<string | null>(null);
  const [orderSearchVersion, setOrderSearchVersion] = useState(0);
  const generation = useRef(0);
  const page = route.page;
  const currentSection = sections.find((item) => item.id === page)!;
  const shgId = dash?.shg.id;
  const load = useCallback(async (knownId?: string) => {
    const request = ++generation.current;
    setLoading(true);
    setError("");
    try {
      let id = knownId;
      if (!id) {
        const boot = await apiFetch<{ shg_id: string; leader_id: string }>("/api/bootstrap", {
          method: "POST",
        });
        if (request !== generation.current) return;
        id = boot.shg_id;
        setLeaderId(boot.leader_id);
      }
      const result = await apiFetch<DashboardData>(`/api/leader/shgs/${id}/dashboard`);
      if (request === generation.current) setDash(result);
    } catch (err) {
      if (request === generation.current)
        setError(err instanceof Error ? err.message : "Could not load the workspace.");
    } finally {
      if (request === generation.current) setLoading(false);
    }
  }, []);
  useEffect(() => {
    void load();
    return () => {
      generation.current++;
    };
  }, [load]);
  useEffect(() => {
    function hashChanged() {
      setRoute(routeFromHash());
    }
    function shortcut(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setQuery("");
        setSearchOpen((open) => !open);
      }
    }
    window.addEventListener("hashchange", hashChanged);
    window.addEventListener("keydown", shortcut);
    return () => {
      window.removeEventListener("hashchange", hashChanged);
      window.removeEventListener("keydown", shortcut);
    };
  }, []);
  useEffect(() => {
    document.title = currentSection.title + " · SakhiSetu";
    window.scrollTo(0, 0);
  }, [page, currentSection.title]);
  function navigate(target: Page, id?: string) {
    window.location.hash = target + (id ? "/" + id : "");
    setMenuOpen(false);
    setSearchOpen(false);
  }
  function afterChange(message?: string) {
    if (message) setToast(message);
    void load(shgId);
  }
  async function mutate(action: () => Promise<unknown>, message: string) {
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      await action();
      afterChange(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }
  const selectOrder = (order: Order) => navigate("orders", order.id);
  const leader = dash?.members.find((member) => member.id === leaderId);
  const attention = new Set(
    [...(dash?.unrouted_messages || []), ...(dash?.quarantined_messages || [])].map((m) => m.id),
  ).size;
  const term = query.trim().toLowerCase();
  const navMatches = sections.filter((section) => section.title.toLowerCase().includes(term));
  const orderMatches =
    dash?.orders
      .filter((o) =>
        [o.order_code, o.product_name, o.buyer_name].some((x) => x?.toLowerCase().includes(term)),
      )
      .slice(0, 8) || [];
  const memberMatches = dash?.members.filter((m) => m.name.toLowerCase().includes(term)).slice(0, 8) || [];
  const nav = (
    <>
      <a className="brand" href="#dashboard" onClick={() => setMenuOpen(false)}>
        <img src="/lotus.svg" alt="" width="43" height="39" />
        <span>
          <strong>SakhiSetu</strong>
          <small>Women · Work · Enterprise</small>
        </span>
      </a>
      <nav aria-label="Main navigation">
        {sections.map(({ id, title, icon: Icon }, index) => (
          <div key={id}>
            {index === 0 && <span className="nav-label">Workspace</span>}
            {id === "cafe" && <span className="nav-label secondary">Assisted services</span>}
            <a
              href={"#" + id}
              aria-current={id === page ? "page" : undefined}
              onClick={() => setMenuOpen(false)}
            >
              <Icon />
              {title}
              {id === "communications" && attention > 0 && <span className="nav-count">{attention}</span>}
            </a>
          </div>
        ))}
      </nav>
      <div className="group-card">
        <span className="group-icon">
          <House />
        </span>
        <div>
          <strong>{dash?.shg.name || "Group workspace"}</strong>
          <small>{dash?.shg.village || "Leader desk"}</small>
        </div>
      </div>
    </>
  );
  return (
    <ToastProvider>
      <div className="workspace-shell">
        <a
          className="skip-link"
          href="#main-content"
          onClick={(e) => {
            e.preventDefault();
            document.getElementById("main-content")?.focus();
          }}
        >
          Skip to content
        </a>
        <aside className="sidebar">{nav}</aside>
        <Dialog open={menuOpen} onOpenChange={setMenuOpen}>
          <DialogContent className="mobile-sheet">
            <DialogTitle className="sr-only">Workspace navigation</DialogTitle>
            <DialogDescription className="sr-only">Choose a workspace section.</DialogDescription>
            {nav}
          </DialogContent>
        </Dialog>
        <div className="workspace-main">
          <header className="topbar">
            <button
              className="icon-button mobile-menu"
              aria-label="Open navigation"
              onClick={() => setMenuOpen(true)}
            >
              <Menu />
            </button>
            <div className="breadcrumb">
              <span>Workspace</span>
              <ChevronRight />
              {currentSection.title}
            </div>
            <button
              aria-label="Search workspace"
              className="global-search"
              onClick={() => {
                setQuery("");
                setSearchOpen(true);
              }}
            >
              <Search />
              <span>Search workspace…</span>
              <kbd>⌘ K</kbd>
            </button>
            <button
              className="icon-button bell"
              aria-label={`Open communications, ${attention} messages need review`}
              onClick={() => navigate("communications")}
            >
              <Bell />
              {attention > 0 && <i />}
            </button>
            <div className="profile">
              <span className="avatar profile-avatar">{initials(leader?.name || "Group Leader")}</span>
              <div>
                <strong>{leader?.name || "Group leader"}</strong>
                <small>Group leader</small>
              </div>
            </div>
          </header>
          <main id="main-content" tabIndex={-1} className="content">
            {error && (
              <div className="error-box" role="alert">
                <AlertCircle size={18} />
                <span>{error}</span>
                <Button disabled={loading} onClick={() => load(shgId)}>
                  Retry connection
                </Button>
              </div>
            )}
            {!dash ? (
              <div className="page-stack">
                <section className="welcome">
                  <div className="welcome-copy">
                    <div className="welcome-date">Leader workspace</div>
                    <h1>{currentSection.title}</h1>
                    <p>
                      {loading
                        ? "Loading your group’s workspace…"
                        : "Connect to the group ledger to view your workspace."}
                    </p>
                  </div>
                  <img className="workshop-art" src="/textile-workshop.webp" alt="" />
                </section>
                {loading && (
                  <div className="metrics-grid" aria-busy="true">
                    {[1, 2, 3, 4].map((i) => (
                      <Card key={i} className="skeleton-card" />
                    ))}
                  </div>
                )}
              </div>
            ) : (
              <>
                {page === "dashboard" && (
                  <Overview
                    dash={dash}
                    leaderName={leader?.name || ""}
                    navigate={navigate}
                    create={() => setCreateOpen(true)}
                    selectOrder={selectOrder}
                  />
                )}
                {page === "orders" && (
                  <Orders
                    key={orderSearchVersion}
                    dash={dash}
                    leaderId={leaderId}
                    selectedId={route.id}
                    selectOrder={selectOrder}
                    create={() => setCreateOpen(true)}
                    busy={busy}
                    onChange={afterChange}
                    simulate={() =>
                      mutate(
                        () =>
                          apiFetch("/api/webhooks/whatsapp", {
                            method: "POST",
                            body: JSON.stringify({
                              shg_id: shgId,
                              sender_phone: "+919900000099",
                              text: "New order: 40 Cotton Tote Bag pieces at Rs 185 per piece, due in 12 days",
                            }),
                          }),
                        "Simulated buyer order received.",
                      )
                    }
                  />
                )}
                {page === "communications" && (
                  <Communications
                    orders={dash.orders}
                    shgId={dash.shg.id}
                    leaderId={leaderId}
                    openOrder={(id) => navigate("orders", id)}
                    onChange={afterChange}
                  />
                )}
                {page === "production" && (
                  <div className="page-stack">
                    <div className="page-heading">
                      <div>
                        <h1>Production</h1>
                        <p>Follow assigned work, quality checks, and open blockers.</p>
                      </div>
                    </div>
                    <LiveMemberTrackingTable rows={dash.member_live_status} />
                    <Card>
                      <div className="panel-heading">
                        <h2>
                          <AlertCircle />
                          Open blockers
                        </h2>
                      </div>
                      {dash.open_blockers.length ? (
                        dash.open_blockers.map((b) => (
                          <button
                            key={b.id}
                            onClick={() => navigate("orders", b.order_id)}
                            className="data-row"
                          >
                            <span>{b.reason}</span>
                            <small>{b.remaining_units} units remaining</small>
                            <ChevronRight />
                          </button>
                        ))
                      ) : (
                        <p className="quiet">No open production blockers.</p>
                      )}
                    </Card>
                  </div>
                )}
                {page === "members" && (
                  <div className="page-stack">
                    <div className="page-heading">
                      <div>
                        <h1>Members</h1>
                        <p>Review individual work records, earnings, and notices.</p>
                      </div>
                    </div>
                    <MemberView key={route.id} initialId={route.id} members={dash.members} />
                  </div>
                )}
                {page === "cafe" && (
                  <div className="page-stack">
                    <div className="page-heading">
                      <div>
                        <h1>JanAI Café</h1>
                        <p>Record a member’s spoken update with their consent.</p>
                      </div>
                    </div>
                    <CafeView shgId={dash.shg.id} onSubmitted={() => afterChange()} />
                  </div>
                )}
                {page === "payouts" && (
                  <div className="page-stack">
                    <div className="page-heading">
                      <div>
                        <h1>Payouts</h1>
                        <p>Review group payout batches and their contest windows.</p>
                      </div>
                    </div>
                    <Card>
                      <div className="panel-heading">
                        <h2>
                          <Wallet />
                          Payout batches
                        </h2>
                      </div>
                      {dash.payout_batches.length === 0 ? (
                        <div className="empty">
                          <Wallet />
                          <h3>No payout batches yet</h3>
                          <p>Group payouts will appear here when a batch is initiated.</p>
                        </div>
                      ) : (
                        dash.payout_batches.map((b) => (
                          <div key={b.id} className="payout-row">
                            <div>
                              <b>{money(b.total_amount_inr)}</b> <StatusBadge status={b.status} />
                              <p>
                                {b.breakdown_snapshot
                                  .map((x) => x.member_name + " · " + money(x.amount_inr))
                                  .join(" / ")}
                              </p>
                            </div>
                            {b.status === "PAYOUT_APPROVED" && (
                              <Button variant="approvalGate" onClick={() => setConfirmBatch(b.id)}>
                                Evaluate contest window
                              </Button>
                            )}
                          </div>
                        ))
                      )}
                    </Card>
                  </div>
                )}
                {page === "insights" && (
                  <div className="page-stack">
                    <div className="page-heading">
                      <div>
                        <h1>Insights</h1>
                        <p>Track the financial impact and running costs of your group’s operations.</p>
                      </div>
                    </div>
                    <ImpactMetricWidget
                      underpricingCaughtInr={dash.impact_metrics.underpricing_caught_inr}
                      recoveryActionsResolved={dash.impact_metrics.recovery_actions_resolved}
                    />
                    <Card>
                      <div className="panel-heading">
                        <h2>
                          <CircleDollarSign />
                          Operating cost
                        </h2>
                      </div>
                      <p className="quiet">{dash.usage_summary.period_ym}</p>
                      <strong className="large-value">{money(dash.usage_summary.total_cost_inr)}</strong>
                    </Card>
                    <BankSummaryPanel shgId={dash.shg.id} leaderId={leaderId} />
                  </div>
                )}
              </>
            )}
          </main>
        </div>
        <Dialog open={searchOpen} onOpenChange={setSearchOpen}>
          <DialogContent className="search-dialog">
            <DialogTitle>Search workspace</DialogTitle>
            <DialogDescription className="sr-only">Find a page, order, product, or member.</DialogDescription>
            <div className="search-field">
              <Search />
              <input
                autoFocus
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search pages, orders, products, or members…"
                aria-label="Search workspace"
              />
            </div>
            <div className="search-results">
              {navMatches.map(({ id, title, icon: Icon }) => (
                <button key={id} onClick={() => navigate(id)}>
                  <Icon />
                  <span>{title}</span>
                  <ChevronRight />
                </button>
              ))}
              {orderMatches.map((o) => (
                <button
                  key={o.id}
                  onClick={() => {
                    setOrderSearchVersion((v) => v + 1);
                    selectOrder(o);
                  }}
                >
                  <Package />
                  <span>
                    {o.order_code}
                    <small>{o.product_name}</small>
                  </span>
                  <ChevronRight />
                </button>
              ))}
              {memberMatches.map((m) => (
                <button key={m.id} onClick={() => navigate("members", m.id)}>
                  <Users />
                  <span>
                    {m.name}
                    <small>Member record</small>
                  </span>
                  <ChevronRight />
                </button>
              ))}
              {!navMatches.length && !orderMatches.length && !memberMatches.length && (
                <p className="quiet">No results for “{query}”.</p>
              )}
            </div>
          </DialogContent>
        </Dialog>
        <Dialog open={createOpen} onOpenChange={setCreateOpen}>
          <DialogContent>
            <DialogTitle>Create order</DialogTitle>
            <DialogDescription>Enter the buyer’s request to create a draft for review.</DialogDescription>
            {dash && (
              <ManualOrderForm
                shgId={dash.shg.id}
                leaderId={leaderId}
                buyers={dash.buyers}
                products={dash.products}
                onCreated={(id) => {
                  setCreateOpen(false);
                  setOrderSearchVersion((v) => v + 1);
                  navigate("orders", id);
                  afterChange("Draft order created.");
                }}
              />
            )}
          </DialogContent>
        </Dialog>
        <Dialog open={!!confirmBatch} onOpenChange={(open) => !open && setConfirmBatch(null)}>
          <DialogContent>
            <DialogTitle>Evaluate contest window?</DialogTitle>
            <DialogDescription>
              The ledger can disburse this approved batch if its window has elapsed and there are no open
              contests.
            </DialogDescription>
            <div className="dialog-actions">
              <DialogClose asChild>
                <Button>Cancel</Button>
              </DialogClose>
              <Button
                variant="approvalGate"
                onClick={() => {
                  const id = confirmBatch;
                  setConfirmBatch(null);
                  mutate(
                    () => apiFetch(`/api/leader/payouts/${id}/evaluate-window`, { method: "POST" }),
                    "Contest window evaluated.",
                  );
                }}
              >
                Evaluate window
              </Button>
            </div>
          </DialogContent>
        </Dialog>
        <Toast open={!!toast} onOpenChange={(open) => !open && setToast("")}>
          <span className="toast-inner">
            <Check size={16} />
            {toast}
          </span>
        </Toast>
        <ToastViewport />
      </div>
    </ToastProvider>
  );
}
