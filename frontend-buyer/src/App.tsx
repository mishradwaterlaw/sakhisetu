import { useEffect, useState } from "react";
import { AlertTriangle, CheckCircle2, Clock, PackageCheck } from "lucide-react";

/**
 * Genuinely separate Buyer bundle (§6, §12):
 * Zero member-level data, identities, assignments, or compensation exist in this codebase or its API responses.
 */
interface BuyerOrderSummary {
  order_id: string;
  order_code: string;
  shg_name: string;
  status: string;
  quantity: number;
  due_date: string | null;
  agreed_price_per_unit_inr: number | null;
  rubric_disagreement_risk: boolean;
  total_tasks: number;
  completed_tasks: number;
  group_qc_passed_units: number;
  group_qc_flagged_units: number;
}

export default function App() {
  const [orders, setOrders] = useState<BuyerOrderSummary[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/bootstrap", { method: "POST" })
      .then((r) => r.json())
      .then((boot) =>
        fetch("/api/buyer/orders", {
          headers: { "X-Buyer-Party-Id": boot.buyer_party_id || "" },
        })
      )
      .then((r) => r.json())
      .then((data) => setOrders(data.orders || []))
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="bg-slate-900 text-white px-6 py-4">
        <div className="max-w-4xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-lg font-extrabold">SakhiSetu — Buyer Progress Portal</h1>
            <p className="text-xs text-slate-300">Group-level order progress &amp; aggregate quality summary</p>
          </div>
          <PackageCheck className="w-6 h-6 text-emerald-400" />
        </div>
      </header>

      <main className="max-w-4xl mx-auto p-6 space-y-4">
        {error && <div className="p-3 bg-rose-50 border border-rose-300 text-rose-900 rounded-lg text-sm">{error}</div>}

        {orders.length === 0 ? (
          <div className="bg-white border border-slate-200 rounded-xl p-8 text-center text-sm text-slate-500">
            No active orders for your buyer account yet.
          </div>
        ) : (
          orders.map((o) => {
            const pct = o.total_tasks > 0 ? Math.round((o.completed_tasks / o.total_tasks) * 100) : 0;
            return (
              <div key={o.order_id} className="bg-white border-2 border-slate-200 rounded-xl p-5 space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <div>
                    <h2 className="text-base font-extrabold">{o.order_code} — {o.shg_name}</h2>
                    <p className="text-xs text-slate-600">Quantity: {o.quantity} units • Agreed Price: ₹{o.agreed_price_per_unit_inr ?? "Pending"}</p>
                  </div>
                  <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full bg-slate-100 border border-slate-300 text-xs font-bold">
                    <Clock className="w-3.5 h-3.5" />
                    <span>{o.status}</span>
                  </span>
                </div>

                <div className="w-full bg-slate-200 h-2.5 rounded-full overflow-hidden">
                  <div className="bg-emerald-600 h-2.5" style={{ width: `${pct}%` }} />
                </div>

                <div className="grid grid-cols-3 gap-3 text-xs pt-1">
                  <div className="p-2.5 bg-slate-50 rounded border border-slate-200">
                    <div className="text-slate-500 font-semibold">Milestone Progress</div>
                    <div className="text-sm font-extrabold mt-0.5">{o.completed_tasks} / {o.total_tasks} stages</div>
                  </div>
                  <div className="p-2.5 bg-emerald-50 rounded border border-emerald-200">
                    <div className="text-emerald-800 font-semibold flex items-center gap-1"><CheckCircle2 className="w-3.5 h-3.5" /> Group QC Passed</div>
                    <div className="text-sm font-extrabold text-emerald-950 mt-0.5">{o.group_qc_passed_units} units</div>
                  </div>
                  <div className="p-2.5 bg-amber-50 rounded border border-amber-200">
                    <div className="text-amber-800 font-semibold flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" /> Group QC Flagged</div>
                    <div className="text-sm font-extrabold text-amber-950 mt-0.5">{o.group_qc_flagged_units} units</div>
                  </div>
                </div>
              </div>
            );
          })
        )}
      </main>
    </div>
  );
}
