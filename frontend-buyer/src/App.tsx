import { useEffect, useState } from "react";
import {
  AlertCircle,
  CheckCheck,
  ChevronRight,
  ClipboardList,
  Flag,
  Package,
  Search,
  ShoppingBag,
  Truck,
} from "lucide-react";

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
async function read<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(path, options);
  const data = await response.json().catch(() => null);
  if (!response.ok || !data)
    throw new Error(data?.detail || `Unable to load orders (HTTP ${response.status}).`);
  return data;
}
export default function App() {
  const [orders, setOrders] = useState<BuyerOrderSummary[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [revision, setRevision] = useState(0);
  const [term, setTerm] = useState("");
  useEffect(() => {
    let active = true;
    setLoading(true);
    setError("");
    read<{ buyer_party_id: string }>("/api/bootstrap", { method: "POST" })
      .then((boot) =>
        read<{ orders: BuyerOrderSummary[] }>("/api/buyer/orders", {
          headers: { "X-Buyer-Party-Id": boot.buyer_party_id },
        }),
      )
      .then((data) => {
        if (active) setOrders(data.orders);
      })
      .catch((err) => {
        if (active) setError(err.message);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [revision]);
  const visible = orders.filter((o) =>
    (o.order_code + " " + o.shg_name).toLowerCase().includes(term.trim().toLowerCase()),
  );
  return (
    <div>
      <header className="buyer-header">
        <div className="buyer-frame">
          <a href="./" className="brand">
            <img src="/lotus.svg" alt="" />
            <span>
              <strong>SakhiSetu</strong>
              <small>Women · Work · Enterprise</small>
            </span>
          </a>
          <span className="portal-label">
            <ShoppingBag size={16} />
            Buyer portal
          </span>
        </div>
      </header>
      <main className="buyer-frame">
        <div className="buyer-crumb">
          Buyer workspace <ChevronRight size={13} /> <b>Orders</b>
        </div>
        <div className="buyer-title">
          <div>
            <h1>Order progress</h1>
            <p>Track your orders, delivery dates, and group quality checks.</p>
          </div>
          <label className="buyer-search">
            <Search size={16} />
            <input
              aria-label="Search orders"
              value={term}
              onChange={(e) => setTerm(e.target.value)}
              placeholder="Find an order or group…"
            />
          </label>
        </div>
        {loading ? (
          <div className="buyer-state" aria-busy="true">
            Loading your orders…
          </div>
        ) : error ? (
          <div className="buyer-state" role="alert">
            <AlertCircle />
            {error}
            <button onClick={() => setRevision((v) => v + 1)}>Retry</button>
          </div>
        ) : (
          <>
            <div className="summary-grid">
              {[
                { label: "Total orders", value: orders.length, icon: Package, tone: "rose" },
                {
                  label: "Units ordered",
                  value: orders.reduce((sum, o) => sum + o.quantity, 0),
                  icon: Truck,
                  tone: "amber",
                },
                {
                  label: "Units passed QC",
                  value: orders.reduce((sum, o) => sum + o.group_qc_passed_units, 0),
                  icon: CheckCheck,
                  tone: "sage",
                },
              ].map(({ label, value, icon: Icon, tone }) => (
                <div className="summary-card" key={label}>
                  <span className={"tile " + tone}>
                    <Icon size={19} />
                  </span>
                  <div>
                    <small>{label}</small>
                    <strong>{value.toLocaleString("en-IN")}</strong>
                  </div>
                </div>
              ))}
            </div>
            <h2 className="list-title">
              <ClipboardList size={20} />
              Your orders <span>{visible.length}</span>
            </h2>
            {visible.length === 0 ? (
              <div className="buyer-state">
                <Package />
                <strong>{orders.length ? "No matching orders" : "No orders yet"}</strong>
                <p>
                  {orders.length
                    ? "Try another order code or group name."
                    : "Orders placed with a group will appear here."}
                </p>
              </div>
            ) : (
              visible.map((o) => {
                const pct = o.total_tasks
                  ? Math.min(100, Math.round((o.completed_tasks / o.total_tasks) * 100))
                  : 0;
                return (
                  <article className="buyer-order" key={o.order_id}>
                    <div className="order-heading">
                      <span className="tile rose">
                        <Package size={20} />
                      </span>
                      <div>
                        <h3>{o.order_code}</h3>
                        <p>{o.shg_name}</p>
                      </div>
                      <span className="buyer-status">
                        {o.status.charAt(0) + o.status.slice(1).toLowerCase().replaceAll("_", " ")}
                      </span>
                    </div>
                    <dl className="facts">
                      <div>
                        <dt>Quantity</dt>
                        <dd>{o.quantity} units</dd>
                      </div>
                      <div>
                        <dt>Agreed unit price</dt>
                        <dd>
                          {o.agreed_price_per_unit_inr == null
                            ? "Pending"
                            : "₹" + o.agreed_price_per_unit_inr.toLocaleString("en-IN")}
                        </dd>
                      </div>
                      <div>
                        <dt>Due date</dt>
                        <dd>
                          {o.due_date
                            ? new Date(o.due_date).toLocaleDateString("en-IN", {
                                day: "numeric",
                                month: "short",
                                year: "numeric",
                              })
                            : "Unscheduled"}
                        </dd>
                      </div>
                    </dl>
                    <div className="progress-header">
                      <span>Milestone progress</span>
                      <strong>
                        {o.completed_tasks} of {o.total_tasks} stages
                      </strong>
                    </div>
                    <progress value={pct} max="100" aria-label="Milestone completion">
                      {pct}%
                    </progress>
                    <div className="quality-row">
                      <span>
                        <CheckCheck />
                        {o.group_qc_passed_units} units passed
                      </span>
                      <span>
                        <Flag />
                        {o.group_qc_flagged_units} units flagged
                      </span>
                      {Boolean(o.rubric_disagreement_risk) && (
                        <span>
                          <AlertCircle />
                          Quality criteria under review
                        </span>
                      )}
                    </div>
                  </article>
                );
              })
            )}
          </>
        )}
      </main>
    </div>
  );
}
