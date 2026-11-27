import * as React from "react";
import * as TabsPrimitive from "@radix-ui/react-tabs";
import * as ToastPrimitive from "@radix-ui/react-toast";
import { cn } from "../../lib/utils";

export const Tabs = TabsPrimitive.Root;

export function TabsList({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.List>) {
  return (
    <TabsPrimitive.List
      className={cn("inline-flex items-center gap-1 rounded border border-[#334155] bg-[#1E293B] p-1", className)}
      {...props}
    />
  );
}

export function TabsTrigger({ className, ...props }: React.ComponentPropsWithoutRef<typeof TabsPrimitive.Trigger>) {
  return (
    <TabsPrimitive.Trigger
      className={cn(
        "rounded px-3 py-1.5 type-scale-xs text-[#94A3B8] transition-colors data-[state=active]:bg-[#FFFFFF] data-[state=active]:text-[#0F172A]",
        className
      )}
      {...props}
    />
  );
}

export const TabsContent = TabsPrimitive.Content;

export const ToastProvider = ToastPrimitive.Provider;
export const ToastViewport = React.forwardRef<
  React.ElementRef<typeof ToastPrimitive.Viewport>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitive.Viewport>
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Viewport
    ref={ref}
    className={cn("fixed bottom-4 right-4 z-50 flex max-w-sm flex-col gap-2", className)}
    {...props}
  />
));
ToastViewport.displayName = "ToastViewport";

export const Toast = React.forwardRef<
  React.ElementRef<typeof ToastPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof ToastPrimitive.Root>
>(({ className, ...props }, ref) => (
  <ToastPrimitive.Root
    ref={ref}
    className={cn(
      "rounded border-2 border-[#0F172A] bg-[var(--bg-surface)] px-4 py-3 type-scale-sm text-[var(--text-primary)]",
      className
    )}
    {...props}
  />
));
Toast.displayName = "Toast";

export function Input({ className, ...props }: React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "w-full rounded border border-[var(--border-neutral)] bg-[var(--bg-surface)] px-2.5 py-2 type-scale-sm text-[var(--text-primary)] focus:border-[#0F172A] focus:outline-none",
        className
      )}
      {...props}
    />
  );
}
