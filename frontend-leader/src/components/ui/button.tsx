import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "../../lib/utils";

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-1.5 rounded border font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#0F172A] disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        // Exclusively for approval-gate and money-moving actions (DESIGN.md §2, §7)
        approvalGate:
          "min-h-[44px] px-4 py-2.5 bg-[var(--accent-gate)] text-[var(--accent-gate-text)] border-[#0F172A] border-2 type-scale-md font-extrabold hover:brightness-95",
        primary:
          "px-3 py-2 bg-[#0F172A] text-[#F8FAFC] border-[#0F172A] type-scale-sm font-semibold hover:bg-[#1E293B]",
        outline:
          "px-3 py-2 bg-[var(--bg-surface)] text-[var(--text-primary)] border-[var(--border-neutral)] type-scale-sm hover:bg-[var(--bg-surface-muted)]",
        danger:
          "px-3 py-2 bg-[var(--status-danger-bg)] text-[var(--status-danger)] border-[var(--status-danger)] type-scale-sm font-bold",
        success:
          "px-3 py-2 bg-[var(--status-success-bg)] text-[var(--status-success)] border-[var(--status-success)] type-scale-sm font-bold",
      },
    },
    defaultVariants: {
      variant: "outline",
    },
  }
);

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean;
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    return <Comp className={cn(buttonVariants({ variant, className }))} ref={ref} {...props} />;
  }
);
Button.displayName = "Button";
