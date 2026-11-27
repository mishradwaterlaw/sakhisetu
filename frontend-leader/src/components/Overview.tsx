import { useState } from "react";
import {
  Activity,
  ArrowRight,
  CalendarDays,
  CheckCheck,
  ChevronDown,
  ClipboardList,
  ListChecks,
  MessageCircle,
  Package,
  Plus,
  Users,
  Wallet,
  Zap,
} from "lucide-react";
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { type DashboardData, type Order, type Page, dateLabel, money } from "../workspace";
import { Metric } from "./Metric";
import { OrdersTable } from "./Orders";
import { Card } from "./ui/card";

function DeliveryChart({ orders }: { orders: Order[] }) {
  const [weeks, setWeeks] = useState(4);
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const dueOrders = orders.filter((order) => order.due_date && new Date(order.due_date) >= start);
  const data = Array.from({ length: weeks + 1 }, (_, index) => {
    const date = new Date(start);
    date.setDate(date.getDate() + index * 7);
    const label = dateLabel(date.toISOString());
    const cutoff = new Date(date);
    cutoff.setDate(cutoff.getDate() + 1);
    const units = dueOrders.reduce(
      (sum, order) => (new Date(order.due_date!) < cutoff ? sum + order.quantity : sum),
      0,
    );
    return { label, units };
  });
  const total = data[data.length - 1].units;
  return (
    <Card className="chart-card">
      <div className="panel-heading">
        <h2>
          <Activity />
          Delivery outlook
        </h2>
        <label className="select-box">
          <select
            aria-label="Delivery outlook period"
            value={weeks}
            onChange={(e) => setWeeks(Number(e.target.value))}
          >
            <option value={4}>Next 4 weeks</option>
            <option value={8}>Next 8 weeks</option>
          </select>
          <ChevronDown />
        </label>
      </div>
      <div className="chart-caption">
        <strong>{total.toLocaleString("en-IN")}</strong>
        <span>units due in this period</span>
      </div>
      <div
        className="chart-wrap"
        role="img"
        aria-label={`Cumulative units due: ${data.map((point) => point.label + ", " + point.units).join("; ")}`}
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={data} margin={{ top: 8, right: 18, bottom: 0, left: -23 }}>
            <defs>
              <linearGradient id="delivery-fill" x1="0" x2="0" y1="0" y2="1">
                <stop offset="0%" stopColor="#c5758b" stopOpacity={0.28} />
                <stop offset="100%" stopColor="#c5758b" stopOpacity={0.025} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#eee7e6" strokeDasharray="3 4" vertical={false} />
            <XAxis
              dataKey="label"
              tick={{ fontSize: 11, fill: "#756e71" }}
              axisLine={false}
              tickLine={false}
              tickMargin={9}
              minTickGap={16}
            />
            <YAxis
              allowDecimals={false}
              domain={[0, total || 4]}
              tickCount={4}
              tick={{ fontSize: 11, fill: "#756e71" }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              formatter={(value: number) => [value, "Units due by this date"]}
              contentStyle={{ borderRadius: 8, borderColor: "#e4d9dc", fontSize: 12 }}
            />
            <Area
              type="linear"
              dataKey="units"
              stroke="#9c3155"
              strokeWidth={2.5}
              fill="url(#delivery-fill)"
              dot={{ r: 3.5, strokeWidth: 2, fill: "#fff" }}
              activeDot={{ r: 5 }}
              isAnimationActive={false}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

export function Overview({
  dash,
  leaderName,
  navigate,
  create,
  selectOrder,
}: {
  dash: DashboardData;
  leaderName: string;
  navigate: (page: Page) => void;
  create: () => void;
  selectOrder: (order: Order) => void;
}) {
  const drafts = dash.orders.filter((order) => order.status === "DRAFT").length;
  const pending = dash.payout_batches.filter((batch) => batch.status !== "DISBURSED");
  const passed = dash.member_live_status.reduce((sum, member) => sum + member.passed_units, 0);
  const assigned = dash.member_live_status.reduce((sum, member) => sum + member.assigned_units, 0);
  const actions = [
    { label: "Create order", hint: "Enter a new draft", icon: Plus, tone: "rose", action: create },
    {
      label: "Track production",
      hint: "Review assigned work",
      icon: ClipboardList,
      tone: "amber",
      action: () => navigate("production"),
    },
    {
      label: "Open inbox",
      hint: "Review group messages",
      icon: MessageCircle,
      tone: "sage",
      action: () => navigate("communications"),
    },
    {
      label: "View members",
      hint: "Find a member record",
      icon: Users,
      tone: "lavender",
      action: () => navigate("members"),
    },
  ];
  return (
    <div className="page-stack">
      <section className="welcome">
        <div className="welcome-copy">
          <div className="welcome-date">
            <CalendarDays />
            {new Date().toLocaleDateString("en-IN", {
              weekday: "long",
              day: "numeric",
              month: "long",
              year: "numeric",
            })}
          </div>
          <h1>Namaste{leaderName ? ", " + leaderName.split(" ")[0] : ""}!</h1>
          <p>Here’s how your group’s work is coming along.</p>
        </div>
        <img src="/textile-workshop.webp" alt="" width="1000" height="357" className="workshop-art" />
      </section>
      <div className="metrics-grid">
        <Metric
          icon={Package}
          tone="rose"
          label="Total orders"
          value={dash.orders.length}
          detail={`${drafts} awaiting draft review`}
        />
        <Metric
          icon={Users}
          tone="sage"
          label="Group members"
          value={dash.members.length}
          detail={`${dash.member_live_status.filter((member) => member.live_status === "IN_PROGRESS").length} currently in production`}
        />
        <Metric
          icon={CheckCheck}
          tone="lavender"
          label="QC passed"
          value={passed}
          detail={`Of ${assigned} assigned units`}
        />
        <Metric
          icon={Wallet}
          tone="amber"
          label="Pending payouts"
          value={money(pending.reduce((sum, batch) => sum + batch.total_amount_inr, 0))}
          detail={`${pending.length} pending payout batches`}
        />
      </div>
      <div className="overview-split">
        <DeliveryChart orders={dash.orders} />
        <Card className="actions-card">
          <div className="panel-heading">
            <h2>
              <Zap />
              Quick actions
            </h2>
          </div>
          <div className="quick-grid">
            {actions.map(({ icon: Icon, ...item }) => (
              <button key={item.label} className="quick-action" onClick={item.action}>
                <span className={"tile " + item.tone}>
                  <Icon />
                </span>
                <strong>{item.label}</strong>
                <small>{item.hint}</small>
                <ArrowRight className="quick-arrow" />
              </button>
            ))}
          </div>
        </Card>
      </div>
      <Card className="table-card">
        <div className="panel-heading">
          <h2>
            <ListChecks />
            Recent orders
          </h2>
          <button className="text-button" onClick={() => navigate("orders")}>
            View all orders <ArrowRight />
          </button>
        </div>
        {dash.orders.length ? (
          <OrdersTable orders={dash.orders.slice(0, 5)} selectOrder={selectOrder} />
        ) : (
          <div className="empty">
            <Package />
            <h3>No orders yet</h3>
            <button className="text-button" onClick={create}>
              Create your first order <ArrowRight />
            </button>
          </div>
        )}
      </Card>
    </div>
  );
}
