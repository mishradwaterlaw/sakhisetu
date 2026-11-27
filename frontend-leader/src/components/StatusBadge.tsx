import { humanize } from "../workspace";
import { Badge } from "./ui/badge";

const labels: Record<string, [string, string]> = {
  DRAFT: ["Draft review", "amber"],
  CONFIRMED: ["Confirmed", "sage"],
  PRICING_APPROVED: ["Price approved", "sage"],
  ALLOCATION_PROPOSED: ["Plan proposed", "lavender"],
  ALLOCATION_APPROVED: ["Plan approved", "sage"],
  IN_PRODUCTION: ["In production", "rose"],
  QC_PENDING: ["Quality review", "lavender"],
  QC_CLEARED: ["QC cleared", "sage"],
  PAYOUT_PENDING: ["Group review", "amber"],
  PAYOUT_APPROVED: ["Contest window", "lavender"],
  DISPUTED: ["Disputed", "rose"],
  DISBURSED: ["Disbursed", "sage"],
};
export function StatusBadge({ status }: { status: string }) {
  const [label, tone] = labels[status] ?? [humanize(status), "neutral"];
  return (
    <Badge variant="secondary" className={`status-pill ${tone}`}>
      <i aria-hidden="true" />
      {label}
    </Badge>
  );
}
