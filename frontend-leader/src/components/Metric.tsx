import type { LucideIcon } from "lucide-react";
import { Card } from "./ui/card";

export function Metric({
  icon: Icon,
  tone,
  label,
  value,
  detail,
}: {
  icon: LucideIcon;
  tone: string;
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <Card className="metric">
      <div className="metric-head">
        <span className={"tile " + tone}>
          <Icon />
        </span>
        <span>{label}</span>
      </div>
      <strong>{value}</strong>
      <p>{detail}</p>
    </Card>
  );
}
