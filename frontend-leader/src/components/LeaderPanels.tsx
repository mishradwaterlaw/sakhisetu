import { useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, ClipboardList, Copy, Scale, TrendingUp } from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiFetch } from "../api";
import { Button } from "./ui/button";
import { Card, CardHeader, CardTitle } from "./ui/card";
import { Table, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { Input } from "./ui/tabs-toast";

export function ImpactMetricWidget({
  underpricingCaughtInr,
  recoveryActionsResolved,
  loading,
}: {
  underpricingCaughtInr: number;
  recoveryActionsResolved: number;
  loading?: boolean;
}) {
  if (loading) {
    return (
      <Card aria-busy="true">
        <div className="type-scale-sm text-[var(--text-secondary)]">Loading impact metrics...</div>
      </Card>
    );
  }

  return (
    <Card>
      <div className="panel-heading"><h2><TrendingUp />Group protection</h2></div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="rounded-lg bg-[var(--status-success-bg)] p-4">
          <p className="type-scale-sm">Underpricing caught</p>
          <strong className="large-value">₹{underpricingCaughtInr.toLocaleString("en-IN", { maximumFractionDigits: 2 })}</strong>
        </div>
        <div className="rounded-lg bg-[var(--bg-surface-muted)] p-4">
          <p className="type-scale-sm">Recovery actions resolved</p>
          <strong className="large-value">{recoveryActionsResolved}</strong>
        </div>
      </div>
    </Card>
  );
}

export function ManualOrderForm({
  shgId,
  leaderId,
  buyers,
  products,
  onCreated,
}: {
  shgId: string;
  leaderId: string;
  buyers: { id: string; name: string }[];
  products: { id: string; name: string }[];
  onCreated: (orderId: string) => void;
}) {
  const [buyerId, setBuyerId] = useState(buyers[0]?.id || "");
  const [productName, setProductName] = useState(products[0]?.name || "Cotton Tote Bag");
  const [qty, setQty] = useState(25);
  const [days, setDays] = useState(10);
  const [price, setPrice] = useState(175);
  const [submitting, setSubmitting] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setSubmitting(true);
    try {
      const res = await apiFetch<{ order_id: string }>("/api/leader/orders/manual", {
        method: "POST",
        body: JSON.stringify({
          shg_id: shgId,
          leader_id: leaderId,
          buyer_party_id: buyerId || buyers[0]?.id,
          product_name: productName,
          quantity: Number(qty),
          offered_price_per_unit_inr: Number(price),
          due_in_days: days,
        }),
      });
      if (!res.order_id) throw new Error("The request was received without a draft. Review it in Communications.");
      onCreated(res.order_id);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to create draft order");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="form-stack">
      {err && <div className="error-box" role="alert">{err}</div>}
      {!buyers.length ? <p className="quiet">Onboard a buyer in Communications to create an order.</p> : (
        <form onSubmit={submit} className="form-stack">
          <label className="field">Buyer<select value={buyerId || buyers[0]?.id || ""} onChange={e => setBuyerId(e.target.value)}>
            {buyers.map(buyer => <option key={buyer.id} value={buyer.id}>{buyer.name}</option>)}
          </select></label>
          <label className="field">Product<Input required value={productName} onChange={e => setProductName(e.target.value)}/></label>
          <div className="field-pair"><label className="field">Quantity (units)<Input required type="number" min={1} value={qty || ""} onChange={e => setQty(Number(e.target.value))}/></label>
          <label className="field">Offer per unit (₹)<Input required type="number" min={0.01} step="0.01" value={price || ""} onChange={e => setPrice(Number(e.target.value))}/></label></div>
          <label className="field">Due in (days)<Input required type="number" min={1} value={days || ""} onChange={e => setDays(Number(e.target.value))}/></label>
          <Button type="submit" variant="primary" disabled={submitting || !productName.trim()}>{submitting ? "Creating…" : "Create draft order"}</Button>
        </form>
      )}
    </div>
  );
}

export function LiveMemberTrackingTable({
  rows,
  loading,
}: {
  rows: {
    member_id: string;
    name: string;
    workload_preference: string;
    live_status: string;
    assigned_units: number;
    passed_units: number;
    unhonored_preference_reason?: string | null;
  }[];
  loading?: boolean;
}) {
  const statusStyle: Record<string, string> = {
    NOT_STARTED: "bg-[var(--bg-surface-muted)] text-[var(--text-secondary)] border-[var(--border-neutral)]",
    IN_PROGRESS: "bg-[#E0F2FE] text-[#075985] border-[#7DD3FC]",
    BLOCKED: "bg-[var(--status-danger-bg)] text-[var(--status-danger)] border-[var(--status-danger)]",
    SUBMITTED: "bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success)]",
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">
          <ClipboardList className="w-4 h-4" strokeWidth={1.75} />
          <span>Member production</span>
        </CardTitle>
      </CardHeader>

      {loading ? (
        <div className="type-scale-sm text-[var(--text-secondary)] py-4" aria-busy="true">
          Loading member statuses...
        </div>
      ) : rows.length === 0 ? (
        <div className="type-scale-sm text-[var(--text-secondary)] py-4">No active SHG members found.</div>
      ) : (
        <div className="space-y-3">
          <div className="h-36 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#475569" }} />
                <YAxis tick={{ fontSize: 11, fill: "#475569" }} />
                <Tooltip />
                <Bar dataKey="assigned_units" name="Assigned Units" fill="#973659" />
                <Bar dataKey="passed_units" name="QC Passed Units" fill="#538069" />
              </BarChart>
            </ResponsiveContainer>
          </div>

          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Member</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Passed / Assigned</TableHead>
                <TableHead>Workload Pref</TableHead>
              </TableRow>
            </TableHeader>
            <tbody>
              {rows.map((r) => (
                <TableRow key={r.member_id}>
                  <TableCell>
                    <div className="font-bold">{r.name}</div>
                    {r.unhonored_preference_reason && (
                      <div className="type-scale-xs text-[var(--status-warning)] mt-0.5">{r.unhonored_preference_reason}</div>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className={`inline-block px-2 py-0.5 rounded border type-scale-xs ${statusStyle[r.live_status] || statusStyle.NOT_STARTED}`}>
                      {r.live_status.replace("_", " ")}
                    </span>
                  </TableCell>
                  <TableCell>
                    {r.passed_units} / {r.assigned_units}
                  </TableCell>
                  <TableCell className="uppercase">{r.workload_preference}</TableCell>
                </TableRow>
              ))}
            </tbody>
          </Table>
        </div>
      )}
    </Card>
  );
}

export function SideBySideQCQueue({
  orderId,
  leaderId,
  assignments,
  rubric,
  onRecorded,
}: {
  orderId: string;
  leaderId: string;
  assignments: { id: string; member_name: string; assigned_units: number; passed_units: number }[];
  rubric: { status: string; criteria: { criterion: string; target: string }[] } | null;
  onRecorded: () => void;
}) {
  const [flagReason, setFlagReason] = useState("Uneven seam allowance");
  const [err, setErr] = useState<string | null>(null);
  const eligible = assignments.filter((a) => a.assigned_units > 0);

  async function recordDecision(assignmentId: string, outcome: "PASS" | "FLAG" | "ESCALATE", units: number) {
    setErr(null);
    try {
      await apiFetch(`/api/leader/orders/${orderId}/qc`, {
        method: "POST",
        body: JSON.stringify({
          assignment_id: assignmentId,
          reviewer_member_id: leaderId,
          units_checked: Math.max(1, units),
          outcome,
          flag_reason: outcome === "PASS" ? null : flagReason,
        }),
      });
      onRecorded();
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to record QC");
    }
  }

  return (
    <Card className="bg-[var(--bg-surface-muted)]">
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">
          <Camera className="w-4 h-4" strokeWidth={1.75} />
          <span>Quality checks</span>
        </CardTitle>
        <span className="type-scale-xs text-[var(--text-secondary)]">Rubric: {rubric?.status || "STUB"}</span>
      </CardHeader>

      {err && (
        <div className="mb-2 rounded border border-[var(--status-danger)] bg-[var(--status-danger-bg)] px-3 py-2 type-scale-xs text-[var(--status-danger)]">
          {err}
        </div>
      )}

      {eligible.length === 0 ? (
        <div className="type-scale-sm text-[var(--text-secondary)]">No active assignments to inspect yet.</div>
      ) : (
        <div className="space-y-2.5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2.5 type-scale-xs">
              <div className="font-bold mb-1">Agreed Reference Rubric</div>
              {(rubric?.criteria || []).map((c, idx) => (
                <div key={idx} className="text-[var(--text-secondary)]">
                  • <strong>{c.criterion}:</strong> {c.target}
                </div>
              ))}
            </div>
            <div className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2.5">
              <div className="type-scale-xs mb-1">Flag / Escalate Note</div>
              <Input value={flagReason} onChange={(e) => setFlagReason(e.target.value)} />
            </div>
          </div>

          {eligible.map((a) => (
            <div
              key={a.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2.5 type-scale-sm"
            >
              <div>
                <strong>{a.member_name}</strong> — {a.passed_units}/{a.assigned_units} passed
              </div>
              <div className="flex gap-1.5">
                <Button variant="success" onClick={() => recordDecision(a.id, "PASS", a.assigned_units - a.passed_units)}>
                  <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.75} /> Pass
                </Button>
                <Button variant="danger" onClick={() => recordDecision(a.id, "FLAG", 1)}>
                  <AlertTriangle className="w-3.5 h-3.5" strokeWidth={1.75} /> Flag
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </Card>
  );
}

export function SupplierAndCounterOfferPanel({
  orderId,
  leaderId,
  orderStatus,
  materials,
  recommendation,
  buyerOffer,
  mvpPrice,
  onCounterOfferSent,
}: {
  orderId: string;
  leaderId?: string;
  orderStatus?: string;
  materials: { id: string; name: string; unit: string }[];
  recommendation?: string;
  buyerOffer?: number | null;
  mvpPrice?: number | null;
  onCounterOfferSent?: () => void;
}) {
  const [quotes, setQuotes] = useState<
    { supplier_quote_id: string; supplier_name: string; unit_price_inr: number; total_cost_inr: number; delivery_days: number }[]
  >([]);
  const [hasCompared, setHasCompared] = useState(false);
  const [loadingQuotes, setLoadingQuotes] = useState(false);
  const [draftMsg, setDraftMsg] = useState("");
  const [rationale, setRationale] = useState<string | null>(null);
  const [sendingOffer, setSendingOffer] = useState(false);
  const [sentNotice, setSentNotice] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const isOfferGood = recommendation === "ACCEPT";
  const isInsufficient = recommendation === "INSUFFICIENT_DATA";

  async function loadQuotes() {
    if (!materials[0]) return;
    setLoadingQuotes(true);
    setErr(null);
    try {
      const res = await apiFetch<{ quotes: typeof quotes }>(
        `/api/leader/supplier-quotes/compare?material_id=${materials[0].id}&required_quantity=50`
      );
      setQuotes(res.quotes);
      setHasCompared(true);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load supplier quotes");
    } finally {
      setLoadingQuotes(false);
    }
  }

  async function loadCounterOffer(forceDraft = false) {
    setSentNotice(null);
    setErr(null);
    try {
      const res = await apiFetch<{
        draft_message: string | null;
        rationale?: string;
        needs_counter_offer?: boolean;
      }>(`/api/leader/orders/${orderId}/counter-offer-draft${forceDraft ? "?force_draft=true" : ""}`, {
        method: "POST",
      });
      setRationale(res.rationale || null);
      setDraftMsg(res.draft_message || "");
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to draft counter-offer");
    }
  }

  return (
    <Card className="bg-[var(--bg-surface-muted)] space-y-2.5">
      <CardHeader className="mb-1">
        <CardTitle className="flex items-center gap-1.5">
          <Scale className="w-4 h-4" strokeWidth={1.75} />
          <span>Supplier quotes and counter-offer</span>
        </CardTitle>
        <div className="flex gap-1.5">
          <Button disabled={loadingQuotes || !materials.length} onClick={loadQuotes}>Compare Suppliers</Button>
          {!isOfferGood && !isInsufficient && (
            <Button variant="primary" onClick={() => loadCounterOffer(false)}>
              Draft Counter-Offer
            </Button>
          )}
        </div>
      </CardHeader>

      {isOfferGood && !draftMsg && (
        <div className="rounded border border-[var(--status-success)] bg-[var(--status-success-bg)] px-3 py-2 type-scale-xs flex flex-wrap items-center justify-between gap-2">
          <span className="font-bold text-[var(--status-success)]">
            Buyer offer ({buyerOffer != null ? `₹${buyerOffer.toFixed(2)}` : "offered"}/unit) meets or exceeds minimum viable price ({mvpPrice != null ? `₹${mvpPrice.toFixed(2)}` : "MVP"}/unit). Ready to approve price.
          </span>
          <button
            type="button"
            onClick={() => loadCounterOffer(true)}
            className="text-[var(--text-secondary)] underline"
          >
            Draft custom quote anyway
          </button>
        </div>
      )}

      {isInsufficient && (
        <div className="rounded border border-[var(--status-warning)] bg-[var(--status-warning-bg)] px-3 py-2 type-scale-xs text-[var(--status-warning)]">
          Can't compute a reliable cost basis for this product yet; add catalogue pricing before drafting a counter-offer.
        </div>
      )}

      {rationale && !draftMsg && !isOfferGood && (
        <div className="type-scale-xs text-[var(--text-secondary)]">{rationale}</div>
      )}

      {err && (
        <div className="rounded border border-[var(--status-danger)] bg-[var(--status-danger-bg)] px-3 py-2 type-scale-xs text-[var(--status-danger)]">
          {err}
        </div>
      )}

      {loadingQuotes ? (
        <div className="type-scale-xs text-[var(--text-secondary)]" aria-busy="true">
          Comparing supplier quotes...
        </div>
      ) : quotes.length === 0 ? (
        <div className="type-scale-xs text-[var(--text-secondary)]">{hasCompared ? "No supplier quotes are available for this material." : "Compare material costs and delivery times."}</div>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Supplier</TableHead>
              <TableHead>Unit Price</TableHead>
              <TableHead>Total Cost</TableHead>
              <TableHead>Delivery</TableHead>
            </TableRow>
          </TableHeader>
          <tbody>
            {quotes.map((q) => (
              <TableRow key={q.supplier_quote_id}>
                <TableCell className="font-bold">{q.supplier_name}</TableCell>
                <TableCell>₹{q.unit_price_inr}</TableCell>
                <TableCell className="font-bold">₹{q.total_cost_inr}</TableCell>
                <TableCell>{q.delivery_days} days</TableCell>
              </TableRow>
            ))}
          </tbody>
        </Table>
      )}

      {draftMsg && (
        <div className="space-y-2 rounded border-2 border-[#0F172A] bg-[var(--bg-surface)] p-3">
          <div className="type-scale-xs text-[var(--status-warning)]">
            Review the wording, then copy the counter-offer for the buyer.
          </div>
          <textarea
            rows={3}
            aria-label="Counter-offer draft" value={draftMsg}
            onChange={(e) => { setDraftMsg(e.target.value); setSentNotice(null); }}
            className="w-full rounded border border-[var(--border-neutral)] p-2 type-scale-sm"
          />
          <div className="flex flex-wrap gap-2">
            <Button variant="primary" disabled={!draftMsg.trim()} onClick={async () => {
              try { await navigator.clipboard.writeText(draftMsg); setSentNotice("Counter-offer copied."); }
              catch { setErr("Select the draft text and use your device’s copy command."); }
            }}><Copy size={15}/>Copy counter-offer</Button>
            {leaderId && orderStatus === "CONFIRMED" && (
              <Button
                variant="approvalGate"
                disabled={sendingOffer || !draftMsg.trim()}
                onClick={async () => {
                  setSendingOffer(true);
                  setErr(null);
                  try {
                    await apiFetch(`/api/leader/orders/${orderId}/send-counter-offer`, {
                      method: "POST",
                      body: JSON.stringify({ leader_id: leaderId, message: draftMsg }),
                    });
                    setSentNotice("Counter-offer sent. Waiting for buyer revised offer.");
                    onCounterOfferSent?.();
                  } catch (e: unknown) {
                    setErr(e instanceof Error ? e.message : "Failed to send counter-offer");
                  } finally {
                    setSendingOffer(false);
                  }
                }}
              >
                {sendingOffer ? "Sending..." : "Send counter-offer to buyer"}
              </Button>
            )}
          </div>
          {sentNotice && <div className="type-scale-xs text-[var(--status-success)]">{sentNotice}</div>}
        </div>
      )}
    </Card>
  );
}
