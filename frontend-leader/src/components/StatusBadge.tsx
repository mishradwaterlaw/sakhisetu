import { AlertTriangle, CheckCircle2, Clock, ShieldCheck, Users } from "lucide-react";

/** Redundant signaling (§12, DESIGN.md): color + Lucide icon (1.75 stroke) + explicit word. */
export function StatusBadge({ status }: { status: string }) {
  const map: Record<string, { cls: string; icon: JSX.Element; label: string }> = {
    DRAFT: {
      cls: "bg-[var(--status-warning-bg)] text-[var(--status-warning)] border-[var(--status-warning)]",
      icon: <Clock className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "DRAFT — REVIEW",
    },
    CONFIRMED: {
      cls: "bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success)]",
      icon: <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "CONFIRMED",
    },
    PRICING_APPROVED: {
      cls: "bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success)]",
      icon: <ShieldCheck className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "PRICING APPROVED",
    },
    ALLOCATION_PROPOSED: {
      cls: "bg-[var(--bg-surface-muted)] text-[var(--text-primary)] border-[var(--border-neutral)]",
      icon: <Clock className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "PLAN PROPOSED",
    },
    ALLOCATION_APPROVED: {
      cls: "bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success)]",
      icon: <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "PLAN APPROVED",
    },
    PAYOUT_PENDING: {
      cls: "bg-[var(--status-warning-bg)] text-[var(--status-warning)] border-[var(--status-warning)]",
      icon: <Users className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "GROUP REVIEW PENDING",
    },
    PAYOUT_APPROVED: {
      cls: "bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success)]",
      icon: <Users className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "GROUP APPROVED (CONTEST WINDOW)",
    },
    DISPUTED: {
      cls: "bg-[var(--status-danger-bg)] text-[var(--status-danger)] border-[var(--status-danger)]",
      icon: <AlertTriangle className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "DISPUTED — HALTED",
    },
    DISBURSED: {
      cls: "bg-[#0F172A] text-[#F8FAFC] border-[#0F172A]",
      icon: <CheckCircle2 className="w-3.5 h-3.5" strokeWidth={1.75} />,
      label: "DISBURSED",
    },
  };
  const cfg = map[status] || {
    cls: "bg-[var(--bg-surface-muted)] text-[var(--text-primary)] border-[var(--border-neutral)]",
    icon: <Clock className="w-3.5 h-3.5" strokeWidth={1.75} />,
    label: status,
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded border text-scale-xs tracking-wide ${cfg.cls}`}>
      {cfg.icon}
      <span>{cfg.label}</span>
    </span>
  );
}
