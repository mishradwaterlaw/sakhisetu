import { useCallback, useEffect, useState } from "react";
import { motion } from "framer-motion";
import { AlertCircle, CheckCircle2, Coins, IndianRupee, RefreshCw, ShieldAlert, Sparkles, Users } from "lucide-react";
import { apiFetch } from "./api";
import { CafeView } from "./components/CafeView";
import {
  ImpactMetricWidget,
  LiveMemberTrackingTable,
  ManualOrderForm,
  SideBySideQCQueue,
  SupplierAndCounterOfferPanel,
} from "./components/LeaderPanels";
import { MemberView } from "./components/MemberView";
import { StatusBadge } from "./components/StatusBadge";
import { Button } from "./components/ui/button";
import { Card, CardHeader, CardTitle } from "./components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger, Toast, ToastProvider, ToastViewport } from "./components/ui/tabs-toast";

interface DashboardData {
  shg: { id: string; name: string; village: string; language: string };
  orders: {
    id: string;
    order_code: string;
    status: string;
    quantity: number;
    offered_price_per_unit_inr: number | null;
    agreed_price_per_unit_inr: number | null;
    has_uncertain_fields: boolean;
    rubric_disagreement_risk: boolean;
  }[];
  quarantined_messages: { id: string; channel: string; raw_text: string }[];
  unrouted_messages: { id: string; channel: string; raw_text: string }[];
  open_blockers: { id: string; order_id: string; reason: string; remaining_units: number }[];
  payout_batches: {
    id: string;
    order_id: string;
    total_amount_inr: number;
    status: string;
    rotation_id: string | null;
    breakdown_snapshot: { member_id: string; member_name: string; units: number; amount_inr: number }[];
  }[];
  members: { id: string; name: string; role: string; preferred_language: string; default_channel: string }[];
  buyers: { id: string; name: string }[];
  materials: { id: string; name: string; unit: string }[];
  products: { id: string; name: string; sku: string }[];
  member_live_status: {
    member_id: string;
    name: string;
    workload_preference: string;
    live_status: string;
    assigned_units: number;
    passed_units: number;
    unhonored_preference_reason?: string | null;
  }[];
  impact_metrics: { underpricing_caught_inr: number; recovery_actions_resolved: number };
  usage_summary: { period_ym: string; total_cost_inr: number };
}

interface OrderDetail {
  order: {
    id: string;
    order_code: string;
    status: string;
    quantity: number;
    offered_price_per_unit_inr: number | null;
    agreed_price_per_unit_inr: number | null;
    has_uncertain_fields: boolean;
    rubric_disagreement_risk: boolean;
  };
  raw_input: string | null;
  extracted_fields: {
    id: string;
    field_name: string;
    extracted_value: string | null;
    confidence: number;
    source_span: string | null;
    is_uncertain: boolean;
  }[];
  assignments: {
    id: string;
    member_name: string;
    assigned_units: number;
    passed_units: number;
    estimated_minutes: number;
    solver_explanation: string;
    status: string;
  }[];
  rubric: { status: string; criteria: { criterion: string; target: string }[] } | null;
}

export default function App() {
  const [shgId, setShgId] = useState("");
  const [leaderId, setLeaderId] = useState("");
  const [dash, setDash] = useState<DashboardData | null>(null);
  const [loadingDash, setLoadingDash] = useState(true);
  const [selectedOrderId, setSelectedOrderId] = useState<string | null>(null);
  const [orderDetail, setOrderDetail] = useState<OrderDetail | null>(null);
  const [loadingOrder, setLoadingOrder] = useState(false);
  const [pricingInfo, setPricingInfo] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toastMsg, setToastMsg] = useState<string | null>(null);

  const loadDashboard = useCallback(async (id: string) => {
    if (!id) return;
    setLoadingDash(true);
    try {
      const data = await apiFetch<DashboardData>(`/api/leader/shgs/${id}/dashboard`);
      setDash(data);
    } finally {
      setLoadingDash(false);
    }
  }, []);

  useEffect(() => {
    apiFetch<{ shg_id: string; leader_id: string }>("/api/bootstrap", { method: "POST" })
      .then((res) => {
        setShgId(res.shg_id);
        setLeaderId(res.leader_id);
        return loadDashboard(res.shg_id);
      })
      .catch((e) => {
        setError(e.message);
        setLoadingDash(false);
      });
  }, [loadDashboard]);

  useEffect(() => {
    if (!selectedOrderId) {
      setOrderDetail(null);
      setPricingInfo(null);
      return;
    }
    setLoadingOrder(true);
    apiFetch<OrderDetail>(`/api/leader/orders/${selectedOrderId}`)
      .then(setOrderDetail)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingOrder(false));
  }, [selectedOrderId]);

  async function runAction(fn: () => Promise<void>, successLabel?: string) {
    setError(null);
    try {
      await fn();
      if (shgId) await loadDashboard(shgId);
      if (selectedOrderId) {
        const d = await apiFetch<OrderDetail>(`/api/leader/orders/${selectedOrderId}`);
        setOrderDetail(d);
      }
      if (successLabel) setToastMsg(successLabel);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Action failed");
    }
  }

  return (
    <ToastProvider swipeDirection="right">
      <Tabs defaultValue="leader" className="min-h-screen bg-[var(--bg-base)] text-[var(--text-primary)]">
        <header className="bg-[#0F172A] text-[#F8FAFC] border-b-2 border-[#334155]">
          <div className="max-w-6xl mx-auto px-4 py-3 flex flex-wrap items-center justify-between gap-3">
            <div>
              <h1 className="type-scale-lg">SakhiSetu Ledger &amp; Operations</h1>
              <p className="type-scale-xs text-[#94A3B8]">
                {dash ? `${dash.shg.name} • ${dash.shg.village}` : "Connecting to SHG ledger..."}
              </p>
            </div>
            <TabsList>
              <TabsTrigger value="leader">Leader Desk</TabsTrigger>
              <TabsTrigger value="cafe">JanAI Café</TabsTrigger>
              <TabsTrigger value="member">Member Record</TabsTrigger>
            </TabsList>
          </div>
        </header>

        <main className="max-w-6xl mx-auto p-4 space-y-3">
          {error && (
            <div className="rounded border-2 border-[var(--status-danger)] bg-[var(--status-danger-bg)] p-3 type-scale-sm text-[var(--status-danger)] flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 font-bold">
                <AlertCircle className="w-4 h-4 shrink-0" strokeWidth={1.75} />
                <span>{error}</span>
              </div>
              <Button onClick={() => shgId && loadDashboard(shgId)}>Retry</Button>
            </div>
          )}

          <TabsContent value="cafe">
            {shgId && <CafeView shgId={shgId} onSubmitted={() => loadDashboard(shgId)} />}
          </TabsContent>

          <TabsContent value="member">{dash && <MemberView members={dash.members} />}</TabsContent>

          <TabsContent value="leader" className="space-y-3">
            {loadingDash && !dash ? (
              <Card aria-busy="true">
                <div className="type-scale-sm text-[var(--text-secondary)] py-6">Loading SHG operations dashboard...</div>
              </Card>
            ) : (
              dash && (
                <motion.div initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.15 }} className="space-y-3">
                  {/* Dense Operational KPI Bar */}
                  <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 tabular-nums">
                    <Card>
                      <div className="type-scale-xs uppercase text-[var(--text-secondary)]">Active Orders</div>
                      <div className="type-scale-xl mt-1">{dash.orders.length}</div>
                    </Card>
                    <Card>
                      <div className="type-scale-xs uppercase text-[var(--status-warning)]">Quarantined / Unrouted</div>
                      <div className="type-scale-xl mt-1">{dash.quarantined_messages.length + dash.unrouted_messages.length}</div>
                    </Card>
                    <Card>
                      <div className="type-scale-xs uppercase text-[var(--text-secondary)]">Pending Payouts</div>
                      <div className="type-scale-xl mt-1">{dash.payout_batches.filter((p) => p.status !== "DISBURSED").length}</div>
                    </Card>
                    <Card>
                      <div className="type-scale-xs uppercase text-[var(--status-success)]">Infra Cost ({dash.usage_summary.period_ym})</div>
                      <div className="type-scale-xl mt-1">₹{dash.usage_summary.total_cost_inr.toFixed(2)}</div>
                    </Card>
                  </div>

                  {/* Priority 2: Recharts Live Impact Metric */}
                  <ImpactMetricWidget
                    underpricingCaughtInr={dash.impact_metrics.underpricing_caught_inr}
                    recoveryActionsResolved={dash.impact_metrics.recovery_actions_resolved}
                  />

                  {/* Priority 1: Manual Order Entry (§21) */}
                  <ManualOrderForm
                    shgId={shgId}
                    leaderId={leaderId}
                    buyers={dash.buyers}
                    products={dash.products}
                    onCreated={(newOrderId) => {
                      setSelectedOrderId(newOrderId);
                      loadDashboard(shgId);
                      setToastMsg("Draft order created — review before confirming.");
                    }}
                  />

                  {/* Quarantine Inbox (§4.2) */}
                  {dash.quarantined_messages.length > 0 && (
                    <Card className="border-2 border-[var(--status-warning)] bg-[var(--status-warning-bg)] space-y-2">
                      <div className="flex items-center gap-2 type-scale-md text-[var(--status-warning)]">
                        <ShieldAlert className="w-4 h-4" strokeWidth={1.75} />
                        <span>Quarantined Unknown Senders</span>
                      </div>
                      {dash.quarantined_messages.map((qm) => (
                        <div key={qm.id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2.5">
                          <div>
                            <div className="type-scale-xs uppercase text-[var(--text-secondary)]">{qm.channel}</div>
                            <div className="type-scale-sm">{qm.raw_text || "(Voice/Media)"}</div>
                          </div>
                          <Button
                            variant="primary"
                            onClick={() =>
                              runAction(
                                async () => {
                                  await apiFetch(`/api/leader/quarantine/${qm.id}/onboard-buyer`, {
                                    method: "POST",
                                    body: JSON.stringify({
                                      leader_id: leaderId,
                                      name: "New Walk-in Buyer",
                                      phone: `+9199${Date.now().toString().slice(-8)}`,
                                    }),
                                  });
                                },
                                "Buyer onboarded from quarantine."
                              )
                            }
                          >
                            Onboard as New Buyer
                          </Button>
                        </div>
                      ))}
                    </Card>
                  )}

                  {/* Orders List + Decision Desk */}
                  <div className="grid grid-cols-1 lg:grid-cols-12 gap-3">
                    <Card className="lg:col-span-5 space-y-2">
                      <CardHeader>
                        <CardTitle>Orders</CardTitle>
                        <Button
                          variant="primary"
                          onClick={() =>
                            runAction(async () => {
                              await apiFetch("/api/webhooks/whatsapp", {
                                method: "POST",
                                body: JSON.stringify({
                                  shg_id: shgId,
                                  sender_phone: "+919900000099",
                                  text: "New order: 40 Cotton Tote Bag pieces at Rs 185 per piece, due in 12 days",
                                }),
                              });
                            }, "Simulated WhatsApp order received as DRAFT.")
                          }
                        >
                          <Sparkles className="w-3.5 h-3.5" strokeWidth={1.75} /> Simulate Buyer Order
                        </Button>
                      </CardHeader>

                      {dash.orders.length === 0 ? (
                        <div className="type-scale-sm text-[var(--text-secondary)] py-6">
                          No orders yet. Create a manual draft above or simulate an inbound buyer order.
                        </div>
                      ) : (
                        <div className="space-y-2">
                          {dash.orders.map((o) => (
                            <button
                              key={o.id}
                              onClick={() => setSelectedOrderId(o.id)}
                              className={`w-full text-left rounded border p-2.5 transition-colors ${
                                selectedOrderId === o.id
                                  ? "border-2 border-[#0F172A] bg-[var(--bg-surface-muted)]"
                                  : "border-[var(--border-neutral)] bg-[var(--bg-surface)]"
                              }`}
                            >
                              <div className="flex items-center justify-between gap-2">
                                <span className="type-scale-sm font-bold">{o.order_code}</span>
                                <StatusBadge status={o.status} />
                              </div>
                              <div className="type-scale-xs text-[var(--text-secondary)] mt-1 flex gap-3 tabular-nums">
                                <span>Qty: {o.quantity}</span>
                                <span>Offer: ₹{o.offered_price_per_unit_inr ?? "—"}</span>
                              </div>
                            </button>
                          ))}
                        </div>
                      )}
                    </Card>

                    <Card className="lg:col-span-7 space-y-3">
                      {loadingOrder ? (
                        <div className="type-scale-sm text-[var(--text-secondary)] py-8" aria-busy="true">
                          Loading order details...
                        </div>
                      ) : !orderDetail ? (
                        <div className="type-scale-sm text-[var(--text-secondary)] py-8">
                          Select an order to review extracted fields, pricing, CP-SAT plan, and approval gates.
                        </div>
                      ) : (
                        <>
                          <CardHeader>
                            <div>
                              <CardTitle>{orderDetail.order.order_code}</CardTitle>
                              <p className="type-scale-xs text-[var(--text-secondary)]">Raw input: "{orderDetail.raw_input || "N/A"}"</p>
                            </div>
                            <StatusBadge status={orderDetail.order.status} />
                          </CardHeader>

                          {/* Approval-Gate Dominant Action Container (DESIGN.md §7) */}
                          <motion.div
                            initial={{ scale: 0.99 }}
                            animate={{ scale: 1 }}
                            transition={{ duration: 0.15 }}
                            className="rounded border-2 border-[#0F172A] bg-[#0F172A] text-[#F8FAFC] p-3 flex flex-wrap items-center justify-between gap-3"
                          >
                            <div>
                              <div className="type-scale-xs uppercase text-[#94A3B8]">Required Leader Decision</div>
                              <div className="type-scale-sm mt-0.5">
                                {orderDetail.order.status === "DRAFT" && "Confirm extracted order details to proceed."}
                                {orderDetail.order.status === "CONFIRMED" && "Review MVP cost breakdown & approve price."}
                                {orderDetail.order.status === "PRICING_APPROVED" && "Run OR-Tools CP-SAT fair allocation solver."}
                                {orderDetail.order.status === "ALLOCATION_PROPOSED" && "Approve CP-SAT task allocation."}
                                {orderDetail.order.status === "ALLOCATION_APPROVED" && "Allocation active. Record QC below."}
                              </div>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              {orderDetail.order.status === "DRAFT" && (
                                <Button
                                  variant="approvalGate"
                                  onClick={() =>
                                    runAction(async () => {
                                      await apiFetch(`/api/leader/orders/${orderDetail.order.id}/confirm`, {
                                        method: "POST",
                                        body: JSON.stringify({ leader_id: leaderId }),
                                      });
                                    }, "Order confirmed.")
                                  }
                                >
                                  Confirm Order
                                </Button>
                              )}
                              {orderDetail.order.status === "CONFIRMED" && (
                                <>
                                  <Button
                                    onClick={() =>
                                      runAction(async () => {
                                        const p = await apiFetch<Record<string, unknown>>(
                                          `/api/leader/orders/${orderDetail.order.id}/pricing`,
                                          { method: "POST" }
                                        );
                                        setPricingInfo(p);
                                      })
                                    }
                                  >
                                    Check MVP Pricing
                                  </Button>
                                  <Button
                                    variant="approvalGate"
                                    onClick={() =>
                                      runAction(async () => {
                                        await apiFetch(`/api/leader/orders/${orderDetail.order.id}/approve-pricing`, {
                                          method: "POST",
                                          body: JSON.stringify({
                                            leader_id: leaderId,
                                            agreed_price_per_unit_inr: orderDetail.order.offered_price_per_unit_inr || 185,
                                          }),
                                        });
                                      }, "Pricing approved.")
                                    }
                                  >
                                    Approve Price
                                  </Button>
                                </>
                              )}
                              {orderDetail.order.status === "PRICING_APPROVED" && (
                                <Button
                                  variant="approvalGate"
                                  onClick={() =>
                                    runAction(async () => {
                                      await apiFetch(`/api/leader/orders/${orderDetail.order.id}/plan`, { method: "POST" });
                                    }, "CP-SAT plan generated.")
                                  }
                                >
                                  Run CP-SAT Planner
                                </Button>
                              )}
                              {orderDetail.order.status === "ALLOCATION_PROPOSED" && (
                                <Button
                                  variant="approvalGate"
                                  onClick={() =>
                                    runAction(async () => {
                                      await apiFetch(`/api/leader/orders/${orderDetail.order.id}/approve-allocation`, {
                                        method: "POST",
                                        body: JSON.stringify({ leader_id: leaderId, overrides: [] }),
                                      });
                                    }, "Allocation approved.")
                                  }
                                >
                                  Approve Allocation
                                </Button>
                              )}
                            </div>
                          </motion.div>

                          {/* Inline Extraction Confidence & Source Spans */}
                          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                            {orderDetail.extracted_fields.map((f) => (
                              <div
                                key={f.id}
                                className={`rounded border p-2 ${
                                  f.is_uncertain
                                    ? "border-[var(--status-warning)] bg-[var(--status-warning-bg)]"
                                    : "border-[var(--border-neutral)] bg-[var(--bg-surface-muted)]"
                                }`}
                              >
                                <div className="flex justify-between type-scale-xs">
                                  <span className="uppercase">{f.field_name}</span>
                                  <span>{Math.round(f.confidence * 100)}% conf</span>
                                </div>
                                <div className="type-scale-sm font-bold mt-0.5">{f.extracted_value || "MISSING"}</div>
                                <div className="type-scale-xs text-[var(--text-secondary)]">Span: "{f.source_span || "none"}"</div>
                              </div>
                            ))}
                          </div>

                          {pricingInfo && (
                            <div className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface-muted)] p-2.5 type-scale-xs space-y-1">
                              <div className="font-bold flex items-center gap-1">
                                <IndianRupee className="w-3.5 h-3.5" strokeWidth={1.75} />
                                <span>MVP: ₹{String(pricingInfo.minimum_viable_price_per_unit_inr)}/unit ({String(pricingInfo.recommendation)})</span>
                              </div>
                              <div>
                                Material ₹{String(pricingInfo.material_cost_per_unit_inr)} • Labour ₹{String(pricingInfo.labour_cost_per_unit_inr)} • Overhead ₹{String(pricingInfo.overhead_per_unit_inr)} • Margin ₹{String(pricingInfo.margin_per_unit_inr)}
                              </div>
                              <div className="text-[var(--status-warning)]">{String(pricingInfo.market_trend_note)}</div>
                            </div>
                          )}

                          {orderDetail.assignments.length > 0 && (
                            <div className="space-y-1.5">
                              <div className="type-scale-xs uppercase text-[var(--text-secondary)]">CP-SAT Solver Explanations</div>
                              {orderDetail.assignments.map((a) => (
                                <div key={a.id} className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface-muted)] p-2.5 type-scale-xs">
                                  <div className="font-bold">
                                    {a.member_name} — {a.assigned_units}u ({a.estimated_minutes}m)
                                  </div>
                                  <div className="text-[var(--text-secondary)] mt-0.5">{a.solver_explanation}</div>
                                </div>
                              ))}
                            </div>
                          )}

                          <SupplierAndCounterOfferPanel orderId={orderDetail.order.id} materials={dash.materials} />

                          {orderDetail.assignments.length > 0 && (
                            <SideBySideQCQueue
                              orderId={orderDetail.order.id}
                              leaderId={leaderId}
                              assignments={orderDetail.assignments}
                              rubric={orderDetail.rubric}
                              onRecorded={() => {
                                loadDashboard(shgId);
                                apiFetch<OrderDetail>(`/api/leader/orders/${orderDetail.order.id}`).then(setOrderDetail);
                                setToastMsg("Human QC decision recorded.");
                              }}
                            />
                          )}
                        </>
                      )}
                    </Card>
                  </div>

                  {/* Priority 1: Live Member Tracking Table + Recharts Visualization */}
                  <LiveMemberTrackingTable rows={dash.member_live_status} loading={loadingDash} />

                  {/* Group-Governed Payout Batches */}
                  {dash.payout_batches.length > 0 && (
                    <Card className="space-y-2">
                      <CardHeader>
                        <CardTitle className="flex items-center gap-1.5">
                          <Coins className="w-4 h-4" strokeWidth={1.75} />
                          <span>Group-Governed Payout Batches</span>
                        </CardTitle>
                      </CardHeader>
                      {dash.payout_batches.map((b) => (
                        <div key={b.id} className="flex flex-wrap items-center justify-between gap-2 rounded border border-[var(--border-neutral)] p-2.5">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="type-scale-md tabular-nums">₹{b.total_amount_inr.toFixed(2)}</span>
                              <StatusBadge status={b.status} />
                            </div>
                            <div className="type-scale-xs text-[var(--text-secondary)] mt-1 flex items-center gap-1">
                              <Users className="w-3.5 h-3.5" strokeWidth={1.75} />
                              <span>{b.breakdown_snapshot.map((x) => `${x.member_name}: ₹${x.amount_inr}`).join(" • ")}</span>
                            </div>
                          </div>
                          {b.status === "PAYOUT_APPROVED" && (
                            <Button
                              variant="approvalGate"
                              onClick={() =>
                                runAction(async () => {
                                  await apiFetch(`/api/leader/payouts/${b.id}/evaluate-window`, { method: "POST" });
                                }, "Contest window evaluated.")
                              }
                            >
                              <RefreshCw className="w-4 h-4" strokeWidth={1.75} /> Evaluate Contest Window
                            </Button>
                          )}
                          {b.status === "DISBURSED" && (
                            <span className="inline-flex items-center gap-1 type-scale-xs text-[var(--status-success)]">
                              <CheckCircle2 className="w-4 h-4" strokeWidth={1.75} /> Disbursed
                            </span>
                          )}
                        </div>
                      ))}
                    </Card>
                  )}
                </motion.div>
              )
            )}
          </TabsContent>
        </main>

        <Toast open={!!toastMsg} onOpenChange={(o) => !o && setToastMsg(null)}>
          {toastMsg}
        </Toast>
        <ToastViewport />
      </Tabs>
    </ToastProvider>
  );
}
