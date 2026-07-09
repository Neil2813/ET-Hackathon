import { Leaf, Flame } from "lucide-react";

interface CO2BadgeProps {
  co2Data: {
    co2_emissions_metric_tons: number;
    carbon_cost_usd: number;
    esg_score: number;
    co2_delta_tons?: number;
    carbon_cost_delta_usd?: number;
  };
}

export function CO2Badge({ co2Data }: CO2BadgeProps) {
  const { co2_emissions_metric_tons, esg_score, co2_delta_tons = 0 } = co2Data;

  const isLow = co2_delta_tons <= 0;
  const isHigh = co2_delta_tons > 1500;

  let bgClass = "bg-emerald-50 text-emerald-700 border-emerald-200";
  let icon = <Leaf className="size-3" />;
  let label = "Low Footprint";

  if (isHigh) {
    bgClass = "bg-red-50 text-red-700 border-red-200";
    icon = <Flame className="size-3" />;
    label = "High Impact";
  } else if (!isLow) {
    bgClass = "bg-amber-50 text-amber-700 border-amber-200";
    icon = <Leaf className="size-3" />;
    label = "Moderate Impact";
  }

  return (
    <div className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] font-mono font-bold uppercase border ${bgClass}`}>
      {icon}
      <span>{label}</span>
      <span className="opacity-40">•</span>
      <span>{co2_emissions_metric_tons.toLocaleString()} t CO₂</span>
      {co2_delta_tons !== 0 && (
        <>
          <span className="opacity-40">•</span>
          <span className={co2_delta_tons > 0 ? "text-red-600" : "text-emerald-600"}>
            {co2_delta_tons > 0 ? `+${co2_delta_tons.toLocaleString()}` : co2_delta_tons.toLocaleString()} t
          </span>
        </>
      )}
      <span className="opacity-40">•</span>
      <span>ESG: {esg_score}</span>
    </div>
  );
}
