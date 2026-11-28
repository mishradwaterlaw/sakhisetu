export interface DashboardData {
  shg: { id: string; name: string; village: string; language: string; federation_id?: string | null };
  orders: {
    id: string;
    order_code: string;
    due_date: string | null;
    product_name?: string | null;
    buyer_name?: string | null;
    status: string;
    quantity: number;
    offered_price_per_unit_inr: number | null;
    agreed_price_per_unit_inr: number | null;
    has_uncertain_fields: boolean;
    rubric_disagreement_risk: boolean;
  }[];
  quarantined_messages: { id: string; channel: string; raw_text: string | null }[];
  unrouted_messages: { id: string; channel: string; raw_text: string | null }[];
  open_blockers: { id: string; order_id: string; reason: string; remaining_units: number }[];
  payout_batches: {
    id: string;
    order_id: string;
    total_amount_inr: number;
    status: string;
    rotation_id: string | null;
    breakdown_snapshot: { member_id: string; member_name: string; units: number; amount_inr: number }[];
  }[];
  members: {
    id: string;
    name: string;
    role: string;
    preferred_language: string;
    default_channel: string;
    skills?: string[];
    tools?: string[];
    available_minutes_per_day?: number;
    workload_preference?: string;
  }[];
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

export interface OrderDetail {
  order: Order;
  raw_input: string | null;
  extracted_fields: {
    id: string;
    field_name: string;
    extracted_value: string | null;
    confidence: number;
    source_span: string | null;
    is_uncertain: boolean;
  }[];
  tasks?: {
    id: string;
    step_name: string;
    required_skill: string;
    required_tools?: string[];
    total_units: number;
    minutes_per_unit: number;
    piece_rate_inr: number;
  }[];
  assignments: {
    id: string;
    task_id?: string;
    member_id?: string;
    member_name: string;
    assigned_units: number;
    passed_units: number;
    estimated_minutes: number;
    solver_explanation: string;
    status: string;
  }[];
  rubric: { status: string; criteria: { criterion: string; target: string }[] } | null;
  latest_quote_check?: {
    material_cost_per_unit_inr: number;
    labour_cost_per_unit_inr: number;
    overhead_per_unit_inr: number;
    margin_per_unit_inr: number;
    minimum_viable_price_per_unit_inr: number;
    buyer_offer_per_unit_inr: number | null;
    gap_pct: number | null;
    recommendation: string;
    market_trend_note: string;
  } | null;
  quality_rotation?: {
    id: string;
    selected_member_ids: string[];
  } | null;
  blockers?: {
    id: string;
    reason: string;
    remaining_units: number;
    status: string;
    options: { id: string; option_type: string; summary: string; is_selected: boolean }[];
  }[];
}

export type Order = DashboardData["orders"][number];
export type Page =
  "dashboard" | "orders" | "production" | "communications" | "members" | "payouts" | "cafe" | "insights";
export type OrderFilter = "All orders" | "Draft" | "Planning" | "Production" | "Quality";
export const filters: OrderFilter[] = ["All orders", "Draft", "Planning", "Production", "Quality"];

export function stage(status: string): OrderFilter | "Other" {
  if (status === "DRAFT") return "Draft";
  if (["CONFIRMED", "COUNTER_OFFER_SENT", "NEGOTIATING", "PRICING_APPROVED", "ALLOCATION_PROPOSED"].includes(status)) return "Planning";
  if (["ALLOCATION_APPROVED", "IN_PRODUCTION"].includes(status)) return "Production";
  if (["QC_PENDING", "QC_CLEARED"].includes(status)) return "Quality";
  return "Other";
}
export function humanize(value: string) {
  const label = value.toLowerCase().replaceAll("_", " ");
  return label.charAt(0).toUpperCase() + label.slice(1);
}
export function dateLabel(value: string | null) {
  return value
    ? new Date(value).toLocaleDateString("en-IN", { day: "numeric", month: "short" })
    : "Unscheduled";
}
export function money(value: number) {
  return new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR", maximumFractionDigits: 2 })
    .format(value)
    .replace(/\.00$/, "");
}
export function initials(name: string) {
  return name
    .trim()
    .split(/\s+/)
    .slice(0, 2)
    .map((word) => word[0])
    .join("")
    .toUpperCase();
}
