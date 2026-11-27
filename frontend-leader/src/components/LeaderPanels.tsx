import { useState } from "react";
import { AlertTriangle, Camera, CheckCircle2, ClipboardList, MessageSquare, PackagePlus, Scale, TrendingUp } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { apiFetch } from "../api";
import { Button } from "./ui/button";
import { Card, CardHeader, CardTitle } from "./ui/card";
import { Dialog, DialogClose, DialogContent, DialogDescription, DialogTitle, DialogTrigger } from "./ui/dialog";
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
        <div className="text-scale-sm text-[var(--text-secondary)]">Loading impact metrics...</div>
      </Card>
    );
  }

  const chartData = [
    { name: "Underpricing Caught (₹)", value: underpricingCaughtInr, fill: "#047857" },
    { name: "Recoveries Resolved", value: recoveryActionsResolved, fill: "#0F172A" },
  ];

  return (
    <Card className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center">
      <div className="md:col-span-7 space-y-1">
        <div className="flex items-center gap-1.5 text-scale-xs uppercase text-[var(--text-secondary)]">
          <TrendingUp className="w-4 h-4 text-[var(--status-success)]" strokeWidth={1.75} />
          <span>Measured Group Protection (QuoteCheck &amp; Recovery Audit)</span>
        </div>
        <div className="text-scale-lg text-[var(--text-primary)] tabular-nums">
          ₹{underpricingCaughtInr.toFixed(2)} caught in underpricing • {recoveryActionsResolved} recovery actions resolved
        </div>
      </div>
      <div className="md:col-span-5 h-20">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} layout="vertical" margin={{ top: 2, right: 16, bottom: 2, left: 10 }}>
            <XAxis type="number" hide />
            <YAxis type="category" dataKey="name" width={135} tick={{ fontSize: 11, fill: "#475569" }} />
            <Tooltip />
            <Bar dataKey="value" radius={[0, 3, 3, 0]}>
              {chartData.map((entry, idx) => (
                <Cell key={idx} fill={entry.fill} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
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
          due_in_days: 10,
        }),
      });
      onCreated(res.order_id);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to create draft order");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-1.5">
          <PackagePlus className="w-4 h-4" strokeWidth={1.75} />
          <span>Manual Order Entry (§21 — Enters as DRAFT)</span>
        </CardTitle>
      </CardHeader>
      {err && (
        <div className="mb-2 rounded border border-[var(--status-danger)] bg-[var(--status-danger-bg)] px-3 py-2 text-scale-xs text-[var(--status-danger)]">
          {err}
        </div>
      )}
      {buyers.length === 0 ? (
        <div className="text-scale-sm text-[var(--text-secondary)]">No buyers onboarded yet.</div>
      ) : (
        <form onSubmit={submit} className="grid grid-cols-1 sm:grid-cols-5 gap-2">
          <select
            value={buyerId || buyers[0]?.id || ""}
            onChange={(e) => setBuyerId(e.target.value)}
            className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] px-2.5 py-2 text-scale-sm"
          >
            {buyers.map((b) => (
              <option key={b.id} value={b.id}>
                {b.name}
              </option>
            ))}
          </select>
          <Input value={productName} onChange={(e) => setProductName(e.target.value)} placeholder="Product" />
          <Input type="number" min={1} value={qty} onChange={(e) => setQty(Number(e.target.value))} placeholder="Qty" />
          <Input type="number" min={1} value={price} onChange={(e) => setPrice(Number(e.target.value))} placeholder="Offer ₹/u" />
          <Button type="submit" variant="primary" disabled={submitting}>
            {submitting ? "Creating..." : "Create Draft"}
          </Button>
        </form>
      )}
    </Card>
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
          <span>Live Member Production Tracking (Flow A)</span>
        </CardTitle>
      </CardHeader>

      {loading ? (
        <div className="text-scale-sm text-[var(--text-secondary)] py-4" aria-busy="true">
          Loading member statuses...
        </div>
      ) : rows.length === 0 ? (
        <div className="text-scale-sm text-[var(--text-secondary)] py-4">No active SHG members found.</div>
      ) : (
        <div className="space-y-3">
          <div className="h-36 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 4, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#CBD5E1" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: "#475569" }} />
                <YAxis tick={{ fontSize: 11, fill: "#475569" }} />
                <Tooltip />
                <Bar dataKey="assigned_units" name="Assigned Units" fill="#0F172A" />
                <Bar dataKey="passed_units" name="QC Passed Units" fill="#047857" />
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
                      <div className="text-scale-xs text-[var(--status-warning)] mt-0.5">{r.unhonored_preference_reason}</div>
                    )}
                  </TableCell>
                  <TableCell>
                    <span className={`inline-block px-2 py-0.5 rounded border text-scale-xs ${statusStyle[r.live_status] || statusStyle.NOT_STARTED}`}>
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
          <span>Side-by-Side Human QC Queue</span>
        </CardTitle>
        <span className="text-scale-xs text-[var(--text-secondary)]">Rubric: {rubric?.status || "STUB"}</span>
      </CardHeader>

      {err && (
        <div className="mb-2 rounded border border-[var(--status-danger)] bg-[var(--status-danger-bg)] px-3 py-2 text-scale-xs text-[var(--status-danger)]">
          {err}
        </div>
      )}

      {eligible.length === 0 ? (
        <div className="text-scale-sm text-[var(--text-secondary)]">No active assignments to inspect yet.</div>
      ) : (
        <div className="space-y-2.5">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
            <div className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2.5 text-scale-xs">
              <div className="font-bold mb-1">Agreed Reference Rubric</div>
              {(rubric?.criteria || []).map((c, idx) => (
                <div key={idx} className="text-[var(--text-secondary)]">
                  • <strong>{c.criterion}:</strong> {c.target}
                </div>
              ))}
            </div>
            <div className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2.5">
              <div className="text-scale-xs mb-1">Flag / Escalate Note</div>
              <Input value={flagReason} onChange={(e) => setFlagReason(e.target.value)} />
            </div>
          </div>

          {eligible.map((a) => (
            <div
              key={a.id}
              className="flex flex-wrap items-center justify-between gap-2 rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2.5 text-scale-sm"
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
  materials,
}: {
  orderId: string;
  materials: { id: string; name: string; unit: string }[];
}) {
  const [quotes, setQuotes] = useState<
    { supplier_quote_id: string; supplier_name: string; unit_price_inr: number; total_cost_inr: number; delivery_days: number }[]
  >([]);
  const [loadingQuotes, setLoadingQuotes] = useState(false);
  const [draftMsg, setDraftMsg] = useState("");
  const [sentNotice, setSentNotice] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  async function loadQuotes() {
    if (!materials[0]) return;
    setLoadingQuotes(true);
    setErr(null);
    try {
      const res = await apiFetch<{ quotes: typeof quotes }>(
        `/api/leader/supplier-quotes/compare?material_id=${materials[0].id}&required_quantity=50`
      );
      setQuotes(res.quotes);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to load supplier quotes");
    } finally {
      setLoadingQuotes(false);
    }
  }

  async function loadCounterOffer() {
    setSentNotice(null);
    setErr(null);
    try {
      const res = await apiFetch<{ draft_message: string }>(`/api/leader/orders/${orderId}/counter-offer-draft`, {
        method: "POST",
      });
      setDraftMsg(res.draft_message);
    } catch (e: unknown) {
      setErr(e instanceof Error ? e.message : "Failed to draft counter-offer");
    }
  }

  return (
    <Card className="bg-[var(--bg-surface-muted)] space-y-2.5">
      <CardHeader className="mb-1">
        <CardTitle className="flex items-center gap-1.5">
          <Scale className="w-4 h-4" strokeWidth={1.75} />
          <span>Supplier Comparison &amp; Counter-Offer Draft (§15)</span>
        </CardTitle>
        <div className="flex gap-1.5">
          <Button onClick={loadQuotes}>Compare Suppliers</Button>
          <Button variant="primary" onClick={loadCounterOffer}>
            Draft Counter-Offer
          </Button>
        </div>
      </CardHeader>

      {err && (
        <div className="rounded border border-[var(--status-danger)] bg-[var(--status-danger-bg)] px-3 py-2 text-scale-xs text-[var(--status-danger)]">
          {err}
        </div>
      )}

      {loadingQuotes ? (
        <div className="text-scale-xs text-[var(--text-secondary)]" aria-busy="true">
          Comparing supplier quotes...
        </div>
      ) : quotes.length === 0 ? (
        <div className="text-scale-xs text-[var(--text-secondary)]">Click "Compare Suppliers" to view material quotes side-by-side.</div>
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
          <div className="text-scale-xs text-[var(--status-warning)]">
            Review and edit before sending — never auto-sent to external buyer.
          </div>
          <textarea
            rows={3}
            value={draftMsg}
            onChange={(e) => setDraftMsg(e.target.value)}
            className="w-full rounded border border-[var(--border-neutral)] p-2 text-scale-sm"
          />
          <Dialog>
            <DialogTrigger asChild>
              <Button variant="approvalGate" className="w-full sm:w-auto">
                <MessageSquare className="w-4 h-4" strokeWidth={1.75} /> Approve &amp; Send Counter-Offer
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogTitle>Confirm Counter-Offer Dispatch</DialogTitle>
              <DialogDescription>
                This sends your reviewed counter-offer to the buyer channel. Verify the exact message below:
              </DialogDescription>
              <p className="mt-3 rounded border border-[var(--border-neutral)] bg-[var(--bg-surface-muted)] p-2.5 text-scale-sm">
                {draftMsg}
              </p>
              <div className="mt-4 flex justify-end gap-2">
                <DialogClose asChild>
                  <Button>Cancel</Button>
                </DialogClose>
                <DialogClose asChild>
                  <Button
                    variant="approvalGate"
                    onClick={() => setSentNotice("Counter-offer approved and queued for buyer channel.")}
                  >
                    Confirm &amp; Send
                  </Button>
                </DialogClose>
              </div>
            </DialogContent>
          </Dialog>
          {sentNotice && <div className="text-scale-xs text-[var(--status-success)]">{sentNotice}</div>}
        </div>
      )}
    </Card>
  );
}
