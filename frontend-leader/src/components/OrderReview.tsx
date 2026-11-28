import { useEffect, useState } from "react";
import { Check, ChevronDown, ChevronUp, IndianRupee, Minus, Package, Plus } from "lucide-react";
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
  members = [],
  onChange,
}: {
  order: Order;
  leaderId: string;
  materials: DashboardData["materials"];
  members?: DashboardData["members"];
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
  const [revisedBuyerOffer, setRevisedBuyerOffer] = useState(
    order.offered_price_per_unit_inr ?? 0,
  );
  const [overrides, setOverrides] = useState<
    Record<string, { new_member_id: string; assigned_units: number; reason: string }>
  >({});
  const [addedRows, setAddedRows] = useState<
    { key: string; task_id: string; member_id: string; assigned_units: number; reason: string }[]
  >([]);
  const [expandedReason, setExpandedReason] = useState<Record<string, boolean>>({});
  useEffect(() => {
    let active = true;
    apiFetch<OrderDetail>(`/api/leader/orders/${order.id}`)
      .then((result) => {
        if (active) {
          setDetail(result);
          if (result.latest_quote_check) {
            setPricingInfo(result.latest_quote_check);
          }
        }
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
                {(orderDetail.order.status === "COUNTER_OFFER_SENT" ||
                  orderDetail.order.status === "NEGOTIATING") && (
                  <div className="flex flex-wrap items-end gap-2">
                    <label className="field">
                      Buyer revised offer (₹/unit)
                      <input
                        type="number"
                        min={1}
                        step="1"
                        value={revisedBuyerOffer || ""}
                        onChange={(e) => setRevisedBuyerOffer(Number(e.target.value))}
                      />
                    </label>
                    <Button
                      variant="primary"
                      disabled={!Number.isFinite(revisedBuyerOffer) || revisedBuyerOffer <= 0}
                      onClick={() =>
                        runAction(async () => {
                          await apiFetch(`/api/leader/orders/${order.id}/buyer-revised-offer`, {
                            method: "POST",
                            body: JSON.stringify({
                              offered_price_per_unit_inr: revisedBuyerOffer,
                            }),
                          });
                          setAgreedPrice(revisedBuyerOffer);
                        }, "Buyer revised offer recorded. Ready to review price again.")
                      }
                    >
                      Record buyer revised offer
                    </Button>
                  </div>
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
                        const overridesPayload = Object.entries(overrides)
                          .map(([assignment_id, ov]) => {
                            const orig = orderDetail.assignments.find((x) => x.id === assignment_id);
                            const origMemberId =
                              orig?.member_id ||
                              members.find((m) => m.name === orig?.member_name)?.id ||
                              "";
                            if (
                              !orig ||
                              (ov.new_member_id === origMemberId && ov.assigned_units === orig.assigned_units)
                            ) {
                              return null;
                            }
                            return {
                              assignment_id,
                              new_member_id: ov.new_member_id || origMemberId,
                              assigned_units: ov.assigned_units,
                              reason: ov.reason.trim() || "Leader adjustment",
                            };
                          })
                          .filter(Boolean);
                        const newAssignmentsPayload = addedRows
                          .filter((r) => r.assigned_units > 0 && r.member_id)
                          .map((r) => ({
                            task_id: r.task_id,
                            member_id: r.member_id,
                            assigned_units: r.assigned_units,
                            reason: r.reason.trim() || "Leader manual split",
                          }));
                        await apiFetch(`/api/leader/orders/${orderDetail.order.id}/approve-allocation`, {
                          method: "POST",
                          body: JSON.stringify({
                            leader_id: leaderId,
                            overrides: overridesPayload,
                            new_assignments: newAssignmentsPayload,
                          }),
                        });
                        setOverrides({});
                        setAddedRows([]);
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
              {pricingInfo.recommendation === "INSUFFICIENT_DATA" ? (
                <div className="font-bold text-[var(--status-warning)]">
                  Can't compute a reliable cost basis for this product yet ({String(pricingInfo.market_trend_note || "missing catalogue data")}).
                </div>
              ) : (
                <>
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
                </>
              )}
            </div>
          )}

          {orderDetail.assignments.length > 0 && (() => {
            const canEdit = orderDetail.order.status === "ALLOCATION_PROPOSED";
            const visibleAssignments = orderDetail.assignments.filter((a) => a.status !== "OVERRIDDEN");
            const taskGroups =
              orderDetail.tasks && orderDetail.tasks.length > 0
                ? orderDetail.tasks.map((t) => ({
                    task: t,
                    rows: visibleAssignments.filter((a) => a.task_id === t.id),
                  }))
                : [
                    {
                      task: {
                        id: "all",
                        step_name: "Order tasks",
                        required_skill: "",
                        required_tools: [] as string[],
                        total_units: orderDetail.order.quantity,
                        minutes_per_unit: 0,
                        piece_rate_inr: 0,
                      },
                      rows: visibleAssignments,
                    },
                  ];

            function memberResourceLabel(
              m: DashboardData["members"][number],
              reqSkill: string,
              reqTools: string[],
            ) {
              const hasSkill = !reqSkill || (m.skills || []).includes(reqSkill);
              const missingTools = (reqTools || []).filter((t) => !(m.tools || []).includes(t));
              if (hasSkill && missingTools.length === 0) {
                const mins = m.available_minutes_per_day ? `${m.available_minutes_per_day}m/d` : "";
                return `${m.name} (Suggested${mins ? ` · ${mins}` : ""})`;
              }
              const missing: string[] = [];
              if (!hasSkill) missing.push(`no ${reqSkill}`);
              if (missingTools.length) missing.push(`no ${missingTools.join(", ")}`);
              return `${m.name} (${missing.join(", ")})`;
            }

            return (
              <div className="space-y-2.5">
                <div className="flex items-center justify-between">
                  <div className="type-scale-xs uppercase text-[var(--text-secondary)]">
                    Work allocation {canEdit ? "· leader controls" : ""}
                  </div>
                </div>
                {taskGroups.map(({ task, rows }) => {
                  const taskAdditions = addedRows.filter((r) => r.task_id === task.id);
                  const allocatedUnits =
                    rows.reduce((sum, a) => {
                      const ov = overrides[a.id];
                      return sum + (ov ? ov.assigned_units : a.assigned_units);
                    }, 0) + taskAdditions.reduce((sum, r) => sum + r.assigned_units, 0);
                  const remainingUnits = task.total_units - allocatedUnits;
                  const isExact = allocatedUnits === task.total_units;

                  return (
                    <div
                      key={task.id}
                      className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface-muted)] p-2.5 space-y-2"
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="type-scale-xs">
                          <span className="font-bold uppercase">{humanize(task.step_name)}</span>
                          {(task.required_skill || (task.required_tools && task.required_tools.length > 0)) && (
                            <span className="text-[var(--text-secondary)] ml-1.5">
                              ({[task.required_skill, ...(task.required_tools || [])].filter(Boolean).join(" · ")})
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 type-scale-xs">
                          <span
                            className={`font-bold px-2 py-0.5 rounded border ${
                              isExact
                                ? "bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success)]"
                                : "bg-[var(--status-warning-bg)] text-[var(--status-warning)] border-[var(--status-warning)]"
                            }`}
                          >
                            {allocatedUnits} / {task.total_units} units
                            {!isExact &&
                              (remainingUnits > 0 ? ` (${remainingUnits} left)` : ` (${Math.abs(remainingUnits)} over)`)}
                          </span>
                          {canEdit && members.length > 0 && task.id !== "all" && (
                            <Button
                              onClick={() => {
                                const fallbackMember =
                                  members.find(
                                    (m) =>
                                      (!task.required_skill || (m.skills || []).includes(task.required_skill)) &&
                                      (task.required_tools || []).every((tl) => (m.tools || []).includes(tl)),
                                  ) || members[0];
                                setAddedRows((prev) => [
                                  ...prev,
                                  {
                                    key: `add-${Date.now()}-${prev.length}`,
                                    task_id: task.id,
                                    member_id: fallbackMember.id,
                                    assigned_units: Math.max(1, remainingUnits > 0 ? remainingUnits : 1),
                                    reason: "",
                                  },
                                ]);
                              }}
                            >
                              + Add member
                            </Button>
                          )}
                        </div>
                      </div>

                      {rows.map((a) => {
                        const origMemberId =
                          a.member_id || members.find((m) => m.name === a.member_name)?.id || "";
                        const currentOv = overrides[a.id] ?? {
                          new_member_id: origMemberId,
                          assigned_units: a.assigned_units,
                          reason: "",
                        };
                        const isChanged =
                          canEdit &&
                          (currentOv.new_member_id !== origMemberId ||
                            currentOv.assigned_units !== a.assigned_units);
                        const isExpanded = Boolean(expandedReason[a.id]);

                        return (
                          <div
                            key={a.id}
                            className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2 type-scale-xs space-y-1.5"
                          >
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              {canEdit && members.length > 0 ? (
                                <select
                                  aria-label={`Assign member for ${task.step_name} (${a.member_name})`}
                                  value={currentOv.new_member_id}
                                  onChange={(e) =>
                                    setOverrides((prev) => ({
                                      ...prev,
                                      [a.id]: {
                                        ...currentOv,
                                        new_member_id: e.target.value,
                                      },
                                    }))
                                  }
                                  className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] px-2 py-1 font-bold"
                                >
                                  {members.map((m) => (
                                    <option key={m.id} value={m.id}>
                                      {memberResourceLabel(m, task.required_skill, task.required_tools || [])}
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <span className="font-bold">{a.member_name}</span>
                              )}

                              <div className="flex items-center gap-1.5">
                                {canEdit ? (
                                  <div className="flex items-center gap-1">
                                    <button
                                      type="button"
                                      aria-label={`Decrease units for ${a.member_name}`}
                                      disabled={currentOv.assigned_units <= 0}
                                      onClick={() =>
                                        setOverrides((prev) => ({
                                          ...prev,
                                          [a.id]: {
                                            ...currentOv,
                                            assigned_units: Math.max(0, currentOv.assigned_units - 1),
                                          },
                                        }))
                                      }
                                      className="rounded border border-[var(--border-neutral)] p-1 disabled:opacity-40"
                                    >
                                      <Minus className="w-3 h-3" />
                                    </button>
                                    <input
                                      type="number"
                                      min={0}
                                      aria-label={`Units for ${a.member_name}`}
                                      value={currentOv.assigned_units}
                                      onChange={(e) => {
                                        const val = Math.max(0, Math.floor(Number(e.target.value) || 0));
                                        setOverrides((prev) => ({
                                          ...prev,
                                          [a.id]: {
                                            ...currentOv,
                                            assigned_units: val,
                                          },
                                        }));
                                      }}
                                      className="w-14 text-center rounded border border-[var(--border-neutral)] px-1 py-0.5 font-bold"
                                    />
                                    <button
                                      type="button"
                                      aria-label={`Increase units for ${a.member_name}`}
                                      onClick={() =>
                                        setOverrides((prev) => ({
                                          ...prev,
                                          [a.id]: {
                                            ...currentOv,
                                            assigned_units: currentOv.assigned_units + 1,
                                          },
                                        }))
                                      }
                                      className="rounded border border-[var(--border-neutral)] p-1"
                                    >
                                      <Plus className="w-3 h-3" />
                                    </button>
                                    <span className="text-[var(--text-secondary)]">
                                      / {task.total_units}
                                    </span>
                                  </div>
                                ) : (
                                  <span className="font-bold">
                                    {a.assigned_units} / {task.total_units}u ({a.estimated_minutes}m)
                                  </span>
                                )}

                                <button
                                  type="button"
                                  onClick={() =>
                                    setExpandedReason((prev) => ({ ...prev, [a.id]: !isExpanded }))
                                  }
                                  className="inline-flex items-center gap-0.5 text-[var(--text-secondary)] underline ml-1"
                                >
                                  <span>{isExpanded ? "Hide reason" : "Why suggested"}</span>
                                  {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                                </button>
                              </div>
                            </div>

                            {isExpanded && (
                              <div className="rounded bg-[var(--bg-surface-muted)] p-2 text-[var(--text-secondary)]">
                                {a.solver_explanation}
                              </div>
                            )}

                            {isChanged && (
                              <input
                                type="text"
                                placeholder="Optional note for this adjustment"
                                aria-label={`Adjustment reason for ${a.member_name}`}
                                value={currentOv.reason}
                                onChange={(e) =>
                                  setOverrides((prev) => ({
                                    ...prev,
                                    [a.id]: {
                                      ...currentOv,
                                      reason: e.target.value,
                                    },
                                  }))
                                }
                                className="w-full rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] px-2 py-1"
                              />
                            )}
                          </div>
                        );
                      })}

                      {taskAdditions.map((added) => (
                        <div
                          key={added.key}
                          className="rounded border border-dashed border-[var(--border-neutral)] bg-[var(--bg-surface)] p-2 type-scale-xs flex flex-wrap items-center justify-between gap-2"
                        >
                          <select
                            aria-label={`New member for ${task.step_name}`}
                            value={added.member_id}
                            onChange={(e) =>
                              setAddedRows((prev) =>
                                prev.map((r) => (r.key === added.key ? { ...r, member_id: e.target.value } : r)),
                              )
                            }
                            className="rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] px-2 py-1 font-bold"
                          >
                            {members.map((m) => (
                              <option key={m.id} value={m.id}>
                                {memberResourceLabel(m, task.required_skill, task.required_tools || [])}
                              </option>
                            ))}
                          </select>
                          <div className="flex items-center gap-1">
                            <button
                              type="button"
                              disabled={added.assigned_units <= 0}
                              onClick={() =>
                                setAddedRows((prev) =>
                                  prev.map((r) =>
                                    r.key === added.key
                                      ? { ...r, assigned_units: Math.max(0, r.assigned_units - 1) }
                                      : r,
                                  ),
                                )
                              }
                              className="rounded border border-[var(--border-neutral)] p-1 disabled:opacity-40"
                            >
                              <Minus className="w-3 h-3" />
                            </button>
                            <input
                              type="number"
                              min={0}
                              value={added.assigned_units}
                              onChange={(e) => {
                                const val = Math.max(0, Math.floor(Number(e.target.value) || 0));
                                setAddedRows((prev) =>
                                  prev.map((r) => (r.key === added.key ? { ...r, assigned_units: val } : r)),
                                );
                              }}
                              className="w-14 text-center rounded border border-[var(--border-neutral)] px-1 py-0.5 font-bold"
                            />
                            <button
                              type="button"
                              onClick={() =>
                                setAddedRows((prev) =>
                                  prev.map((r) =>
                                    r.key === added.key ? { ...r, assigned_units: r.assigned_units + 1 } : r,
                                  ),
                                )
                              }
                              className="rounded border border-[var(--border-neutral)] p-1"
                            >
                              <Plus className="w-3 h-3" />
                            </button>
                            <span className="text-[var(--text-secondary)]">/ {task.total_units}</span>
                            <button
                              type="button"
                              onClick={() => setAddedRows((prev) => prev.filter((r) => r.key !== added.key))}
                              className="ml-2 text-[var(--status-danger)] underline"
                            >
                              Remove
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  );
                })}
              </div>
            );
          })()}

          <SupplierAndCounterOfferPanel
            orderId={orderDetail.order.id}
            leaderId={leaderId}
            orderStatus={orderDetail.order.status}
            materials={materials}
            recommendation={String(pricingInfo?.recommendation || "")}
            buyerOffer={orderDetail.order.offered_price_per_unit_inr}
            mvpPrice={
              pricingInfo?.minimum_viable_price_per_unit_inr != null
                ? Number(pricingInfo.minimum_viable_price_per_unit_inr)
                : null
            }
            onCounterOfferSent={() => refresh("Counter-offer sent to buyer.")}
          />

          {(orderDetail.blockers || []).filter((b) => b.status === "OPEN").length > 0 && (
            <div className="space-y-2">
              <div className="type-scale-xs uppercase text-[var(--status-danger)] font-bold">
                Open Blockers — Recovery Options
              </div>
              {(orderDetail.blockers || [])
                .filter((b) => b.status === "OPEN")
                .map((b) => (
                  <div
                    key={b.id}
                    className="rounded border border-[var(--status-danger)] bg-[var(--status-danger-bg)] p-2.5 type-scale-xs space-y-2"
                  >
                    <div className="font-bold">
                      {b.reason} ({b.remaining_units} units remaining)
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {b.options.map((opt, idx) => (
                        <Button
                          key={opt.id}
                          variant="approvalGate"
                          onClick={() =>
                            runAction(async () => {
                              await apiFetch(`/api/leader/blockers/${b.id}/approve-recovery`, {
                                method: "POST",
                                body: JSON.stringify({
                                  leader_id: leaderId,
                                  recovery_option_id: opt.id,
                                }),
                              });
                            }, `Recovery Option ${idx === 0 ? "A" : "B"} approved.`)
                          }
                        >
                          Approve Option {idx === 0 ? "A" : "B"}: {opt.summary}
                        </Button>
                      ))}
                    </div>
                  </div>
                ))}
            </div>
          )}

          {orderDetail.assignments.length > 0 && (
            <SideBySideQCQueue
              orderId={orderDetail.order.id}
              leaderId={leaderId}
              members={members}
              qualityRotation={orderDetail.quality_rotation}
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
