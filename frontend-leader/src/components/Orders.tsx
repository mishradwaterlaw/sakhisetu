import { useEffect, useState } from "react";
import {
  Archive,
  ChevronDown,
  ChevronRight,
  ClipboardCheck,
  Factory,
  ListFilter,
  Package,
  Plus,
  Search,
  Sparkles,
} from "lucide-react";
import { dateLabel, filters, stage, type DashboardData, type Order, type OrderFilter } from "../workspace";
import { StatusBadge } from "./StatusBadge";
import { Button } from "./ui/button";
import { Card } from "./ui/card";
import { Table, TableCell, TableHead, TableHeader, TableRow } from "./ui/table";
import { OrderReview } from "./OrderReview";
import { Metric } from "./Metric";

export function OrdersTable({
  orders,
  selectOrder,
  selected,
}: {
  orders: Order[];
  selectOrder: (order: Order) => void;
  selected?: string;
}) {
  return (
    <Table className="orders-table">
      <TableHeader>
        <TableRow>
          <TableHead>Order</TableHead>
          <TableHead>Quantity</TableHead>
          <TableHead>Due date</TableHead>
          <TableHead>Status</TableHead>
          <TableHead>
            <span className="sr-only">Details</span>
          </TableHead>
        </TableRow>
      </TableHeader>
      <tbody>
        {orders.map((order) => (
          <TableRow key={order.id} data-selected={order.id === selected} onClick={() => selectOrder(order)}>
            <TableCell>
              <button
                className="order-link"
                onClick={(e) => {
                  e.stopPropagation();
                  selectOrder(order);
                }}
              >
                <span className="order-icon">
                  <Package />
                </span>
                <span>
                  <b>{order.order_code}</b>
                  <small>{order.product_name || order.buyer_name || "Production order"}</small>
                </span>
              </button>
            </TableCell>
            <TableCell>{order.quantity} units</TableCell>
            <TableCell>{dateLabel(order.due_date)}</TableCell>
            <TableCell>
              <StatusBadge status={order.status} />
            </TableCell>
            <TableCell>
              <ChevronRight size={14} />
            </TableCell>
          </TableRow>
        ))}
      </tbody>
    </Table>
  );
}
export function Orders({
  dash,
  leaderId,
  selectedId,
  selectOrder,
  create,
  simulate,
  busy,
  onChange,
}: {
  dash: DashboardData;
  leaderId: string;
  selectedId: string | null;
  selectOrder: (order: Order) => void;
  create: () => void;
  simulate: () => void;
  busy: boolean;
  onChange: (message?: string) => void;
}) {
  const [filter, setFilter] = useState<OrderFilter>("All orders");
  const [query, setQuery] = useState("");
  const [sort, setSort] = useState("recent");
  const visible = dash.orders.filter(
    (order) =>
      (filter === "All orders" || stage(order.status) === filter) &&
      [order.order_code, order.product_name, order.buyer_name].some((value) =>
        value?.toLowerCase().includes(query.trim().toLowerCase()),
      ),
  );
  if (sort === "due") visible.sort((a, b) => (a.due_date || "9999").localeCompare(b.due_date || "9999"));
  const selected = visible.find((order) => order.id === selectedId) || visible[0];
  useEffect(() => {
    if (selectedId && selected?.id === selectedId && window.matchMedia("(max-width: 1319px)").matches) {
      document.getElementById("order-review")?.focus();
    }
  }, [selectedId, selected?.id]);
  return (
    <div className="page-stack">
      <div className="page-heading">
        <div>
          <h1>Orders</h1>
          <p>Track customer orders from intake through quality review.</p>
        </div>
        <Button variant="primary" onClick={create}>
          <Plus size={16} />
          Create order
        </Button>
      </div>
      <div className="metrics-grid">
        <Metric
          icon={Package}
          label="Total orders"
          tone="rose"
          value={dash.orders.length}
          detail="Across your group"
        />
        <Metric
          icon={Archive}
          label="Draft review"
          tone="amber"
          value={dash.orders.filter((o) => stage(o.status) === "Draft").length}
          detail="Awaiting confirmation"
        />
        <Metric
          icon={Factory}
          label="In production"
          tone="sage"
          value={dash.orders.filter((o) => stage(o.status) === "Production").length}
          detail="Work allocated"
        />
        <Metric
          icon={ClipboardCheck}
          label="Quality review"
          tone="lavender"
          value={dash.orders.filter((o) => o.status === "QC_PENDING").length}
          detail="Awaiting QC clearance"
        />
      </div>
      <div className="orders-split">
        <Card className="table-card">
          <div className="panel-heading">
            <h2>
              <Package />
              Order register
            </h2>
            <button className="text-button" onClick={simulate} disabled={busy}>
              <Sparkles />
              Simulate buyer order
            </button>
          </div>
          <div className="table-tools">
            <div className="search-field">
              <Search />
              <input
                placeholder="Search orders…"
                aria-label="Search orders"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </div>
            <label className="select-box">
              <ListFilter />
              <select aria-label="Sort orders" value={sort} onChange={(e) => setSort(e.target.value)}>
                <option value="recent">Most recent</option>
                <option value="due">Due date</option>
              </select>
              <ChevronDown />
            </label>
          </div>
          <div className="filter-row" aria-label="Filter orders">
            {filters.map((item) => (
              <button key={item} aria-pressed={item === filter} onClick={() => setFilter(item)}>
                {item}
              </button>
            ))}
          </div>
          {visible.length ? (
            <OrdersTable orders={visible} selectOrder={selectOrder} selected={selected?.id} />
          ) : (
            <div className="empty">
              <Package />
              <h3>No matching orders</h3>
              <p>Try a different filter or create an order.</p>
            </div>
          )}
        </Card>
        {selected && (
          <OrderReview
            key={selected.id}
            order={selected}
            leaderId={leaderId}
            materials={dash.materials}
            members={dash.members}
            onChange={onChange}
          />
        )}
      </div>
    </div>
  );
}
