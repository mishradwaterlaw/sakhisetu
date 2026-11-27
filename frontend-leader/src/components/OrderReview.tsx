import { useEffect, useState } from "react";
import { Check, IndianRupee, Package } from "lucide-react";
import { apiFetch } from "../api";
import {
  dateLabel,
  humanize,
  money,
  stage,
  type DashboardData,
  type OrderDetail,
  type Order,
} from "../workspace";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import {
  Dialog,
  DialogContent,
  DialogClose,
  DialogTrigger,
  DialogTitle,
  DialogDescription,
} from "./ui/dialog";
import { SideBySideQCQueue, SupplierAndCounterOfferPanel } from "./LeaderPanels";
import { StatusBadge } from "./StatusBadge";

export function OrderReview({
  order,
  leaderId,
  materials,
  onChange,
}: {
  order: Order;
  leaderId: string;
  materials: DashboardData["materials"];
  onChange: (message?: string) => void;
}) {
  const [orderDetail, setDetail] = useState<OrderDetail | null>(null);
  const [pricingInfo, setPricingInfo] = useState<Record<string, unknown> | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [version, setVersion] = useState(0);
  const [agreedPrice, setAgreedPrice] = useState(
    order.agreed_price_per_unit_inr ?? order.offered_price_per_unit_inr ?? 0,
  );
  useEffect(() => {
    let active = true;
    apiFetch<OrderDetail>(`/api/leader/orders/${order.id}`)
      .then((result) => {
        if (active) setDetail(result);
      })
      .catch((err) => {
        if (active) setError(err.message);
      });
    return () => {
      active = false;
    };
  }, [order.id, version]);
  function refresh(message?: string) {
    setError("");
    setDetail(null);
    setVersion((v) => v + 1);
    onChange(message);
  }
  async function runAction(action: () => Promise<void>, message?: string) {
    setBusy(true);
    setError("");
    try {
      await action();
      refresh(message);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not update order.");
    } finally {
      setBusy(false);
    }
  }
  function displayField(field: OrderDetail["extracted_fields"][number]) {
    if (!field.extracted_value) return "Missing";
    if (field.field_name === "product")
      return order.product_name || field.source_span || field.extracted_value;
    if (field.field_name === "offered_price" && Number.isFinite(Number(field.extracted_value)))
      return money(Number(field.extracted_value));
    if (field.field_name === "due_date" && Number.isFinite(Date.parse(field.extracted_value)))
      return dateLabel(field.extracted_value);
    return field.extracted_value;
  }
  const stages = ["Draft", "Planning", "Production", "Quality"];
  const currentStage = stages.indexOf(stage(orderDetail?.order.status || order.status));
  return (
    <Card className="order-review" id="order-review" tabIndex={-1}>
      <div className="review-heading">
        <span className="tile rose">
          <Package />
        </span>
        <div>
          <h2>{order.order_code}</h2>
          <p>{order.product_name || "Order details"}</p>
        </div>
        <StatusBadge status={order.status} />
      </div>
      <dl className="detail-stats">
        <div>
          <dt>Quantity</dt>
          <dd>{order.quantity} units</dd>
        </div>
        <div>
          <dt>Due date</dt>
          <dd>{dateLabel(order.due_date)}</dd>
        </div>
        <div>
          <dt>Offer per unit</dt>
          <dd>
            {order.offered_price_per_unit_inr == null ? "Pending" : money(order.offered_price_per_unit_inr)}
          </dd>
        </div>
      </dl>
      {currentStage >= 0 && (
        <ol className="stage-track" aria-label="Order progress">
          {stages.map((label, i) => (
            <li
              key={label}
              data-done={i < currentStage}
              aria-current={i === currentStage ? "step" : undefined}
            >
              <span>{i < currentStage ? <Check size={12} /> : <i />}</span>
              {label}
            </li>
          ))}
        </ol>
      )}
      {error && (
        <div className="error-box" role="alert">
          {error}
          <Button onClick={() => refresh()}>Retry</Button>
        </div>
      )}
      {!orderDetail && !error && (
        <p className="quiet" aria-busy="true">
          Loading order details…
        </p>
      )}
      {orderDetail && (
        <fieldset disabled={busy} className="space-y-4 min-w-0">
          {orderDetail.raw_input && (
            <div className="source-note">
              <strong>Source message</strong>
              <p>{orderDetail.raw_input}</p>
            </div>
          )}
          {orderDetail.order.status === "CONFIRMED" && (
            <label className="field">
              Agreed unit price (₹)
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={agreedPrice || ""}
                onChange={(event) => setAgreedPrice(Number(event.target.value))}
              />
            </label>
          )}
          {/* Approval-Gate Dominant Action Container (DESIGN.md §7) */}
          {["DRAFT", "CONFIRMED", "PRICING_APPROVED", "ALLOCATION_PROPOSED", "ALLOCATION_APPROVED"].includes(
            orderDetail.order.status,
          ) && (
            <div className="rounded-lg bg-[var(--brand-dark)] text-white p-4 flex flex-wrap items-center justify-between gap-3">
              <div>
                <div className="type-scale-xs uppercase text-rose-100">Next step</div>
                <div className="type-scale-sm mt-0.5">
                  {orderDetail.order.status === "DRAFT" && "Confirm extracted order details to proceed."}
                  {orderDetail.order.status === "CONFIRMED" &&
                    "Review the cost breakdown and approve a unit price."}
                  {orderDetail.order.status === "PRICING_APPROVED" &&
                    "Generate a work allocation for this order."}
                  {orderDetail.order.status === "ALLOCATION_PROPOSED" && "Approve CP-SAT task allocation."}
                  {orderDetail.order.status === "ALLOCATION_APPROVED" &&
                    "Allocation active. Record QC below."}
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
                            { method: "POST" },
                          );
                          setPricingInfo(p);
                        })
                      }
                    >
                      Check minimum price
                    </Button>
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button
                          variant="approvalGate"
                          disabled={!Number.isFinite(agreedPrice) || agreedPrice <= 0}
                        >
                          Approve price
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogTitle>Approve unit price?</DialogTitle>
                        <DialogDescription>
                          Record {money(agreedPrice)} per unit for {order.order_code}, totalling{" "}
                          {money(agreedPrice * order.quantity)} for {order.quantity} units.
                        </DialogDescription>
                        <div className="dialog-actions">
                          <DialogClose asChild>
                            <Button>Cancel</Button>
                          </DialogClose>
                          <DialogClose asChild>
                            <Button
                              variant="approvalGate"
                              onClick={() =>
                                runAction(async () => {
                                  await apiFetch(`/api/leader/orders/${order.id}/approve-pricing`, {
                                    method: "POST",
                                    body: JSON.stringify({
                                      leader_id: leaderId,
                                      agreed_price_per_unit_inr: agreedPrice,
                                    }),
                                  });
                                }, "Pricing approved.")
                              }
                            >
                              Confirm price
                            </Button>
                          </DialogClose>
                        </div>
                      </DialogContent>
                    </Dialog>
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
                    Generate work plan
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
            </div>
          )}

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
                  <span className="uppercase">{humanize(f.field_name)}</span>
                  <span>{Math.round(f.confidence * 100)}% confidence</span>
                </div>
                <div className="type-scale-sm font-bold mt-0.5">{displayField(f)}</div>
                <div className="type-scale-xs text-[var(--text-secondary)]">
                  Span: "{f.source_span || "none"}"
                </div>
              </div>
            ))}
          </div>

          {pricingInfo && (
            <div className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface-muted)] p-2.5 type-scale-xs space-y-1">
              <div className="font-bold flex items-center gap-1">
                <IndianRupee className="w-3.5 h-3.5" strokeWidth={1.75} />
                <span>
                  MVP: ₹{String(pricingInfo.minimum_viable_price_per_unit_inr)}/unit (
                  {String(pricingInfo.recommendation)})
                </span>
              </div>
              <div>
                Material ₹{String(pricingInfo.material_cost_per_unit_inr)} • Labour ₹
                {String(pricingInfo.labour_cost_per_unit_inr)} • Overhead ₹
                {String(pricingInfo.overhead_per_unit_inr)} • Margin ₹
                {String(pricingInfo.margin_per_unit_inr)}
              </div>
              <div className="text-[var(--status-warning)]">{String(pricingInfo.market_trend_note)}</div>
            </div>
          )}

          {orderDetail.assignments.length > 0 && (
            <div className="space-y-1.5">
              <div className="type-scale-xs uppercase text-[var(--text-secondary)]">Work allocation</div>
              {orderDetail.assignments.map((a) => (
                <div
                  key={a.id}
                  className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface-muted)] p-2.5 type-scale-xs"
                >
                  <div className="font-bold">
                    {a.member_name} — {a.assigned_units}u ({a.estimated_minutes}m)
                  </div>
                  <div className="text-[var(--text-secondary)] mt-0.5">{a.solver_explanation}</div>
                </div>
              ))}
            </div>
          )}

          <SupplierAndCounterOfferPanel orderId={orderDetail.order.id} materials={materials} />

          {orderDetail.assignments.length > 0 && (
            <SideBySideQCQueue
              orderId={orderDetail.order.id}
              leaderId={leaderId}
              assignments={orderDetail.assignments}
              rubric={orderDetail.rubric}
              onRecorded={() => refresh("Quality decision recorded.")}
            />
          )}
        </fieldset>
      )}
    </Card>
  );
}
