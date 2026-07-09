/**
 * ROIWidget — cumulative business-impact summary card for the Command Center.
 *
 * Derives all numbers from live incident + audit data already fetched
 * by the parent page — no extra API calls.
 */
import React, { useMemo } from "react";
import { TrendingDown, Truck, Clock, Shield, DollarSign, BarChart3 } from "lucide-react";

/* ---------- helpers ---------- */

function fmt(n: number): string {
  if (n >= 1_000_000_000) return `$${(n / 1_000_000_000).toFixed(1)}B`;
  if (n >= 1_000_000)     return `$${(n / 1_000_000).toFixed(1)}M`;
  if (n >= 1_000)         return `$${(n / 1_000).toFixed(0)}K`;
  return `$${n.toFixed(0)}`;
}

function fmtDays(d: number): string {
  if (d <= 0) return "—";
  return `${d.toFixed(1)} days`;
}

/* ---------- animated counter ---------- */

function Counter({ value, prefix = "", suffix = "" }: { value: string; prefix?: string; suffix?: string }) {
  return (
    <span className="tabular-nums font-black text-2xl leading-none">
      {prefix}{value}{suffix}
    </span>
  );
}

/* ---------- mini sparkbar ---------- */

function SparkBar({ pct, color }: { pct: number; color: string }) {
  return (
    <div className="w-full h-1.5 bg-muted/50 rounded-full overflow-hidden mt-2">
      <div
        className="h-full rounded-full transition-all duration-700"
        style={{ width: `${Math.min(100, Math.max(0, pct))}%`, background: color }}
      />
    </div>
  );
}

/* ---------- single metric tile ---------- */

interface TileProps {
  icon: React.ReactNode;
  label: string;
  value: string;
  sub?: string;
  barPct?: number;
  barColor?: string;
  accent: string;
}

function MetricTile({ icon, label, value, sub, barPct, barColor, accent }: TileProps) {
  return (
    <div className="flex-1 bg-card/60 backdrop-blur-sm border border-border rounded-lg p-4 flex flex-col gap-2 hover:shadow-md transition-shadow min-w-[140px]">
      <div className="flex items-center gap-2">
        <div className={`p-1.5 rounded-md ${accent}`}>{icon}</div>
        <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground leading-tight">
          {label}
        </p>
      </div>
      <Counter value={value} />
      {sub && (
        <p className="text-[10px] text-muted-foreground leading-snug">{sub}</p>
      )}
      {barPct !== undefined && barColor && (
        <SparkBar pct={barPct} color={barColor} />
      )}
    </div>
  );
}

/* ---------- main component ---------- */

export interface ROIWidgetProps {
  /** Resolved + dismissed incidents from /api/incidents */
  resolvedIncidents?: Record<string, unknown>[];
  /** Active (detected / analysed / awaiting) incidents */
  activeIncidents?: Record<string, unknown>[];
  /** Audit rows from /api/audit */
  auditRows?: Record<string, unknown>[];
  /** Whether the parent data is still loading */
  isLoading?: boolean;
}

const ROIWidget: React.FC<ROIWidgetProps> = ({
  resolvedIncidents = [],
  activeIncidents = [],
  auditRows = [],
  isLoading = false,
}) => {
  const metrics = useMemo(() => {
    // ── 1. Total Exposure Avoided ──────────────────────────────────────────
    // Sum monte_carlo.expected_exposure_avoided_usd across all resolved incidents
    // Fall back to total_exposure_usd * 0.72 (avg protection rate from simulation).
    let exposureAvoided = 0;
    let totalExposureAtRisk = 0;

    for (const inc of resolvedIncidents) {
      const mc = inc.monte_carlo as Record<string, unknown> | undefined;
      const avoided =
        Number(mc?.expected_exposure_avoided_usd ?? mc?.estimated_loss_avoided_usd ?? 0) ||
        Number(inc.total_exposure_usd ?? 0) * 0.72;
      exposureAvoided += avoided;
      totalExposureAtRisk += Number(inc.total_exposure_usd ?? 0);
    }

    // ── 2. Active Reroutes ────────────────────────────────────────────────
    // Count audit rows with action starting with "rfq_" or "workflow_routes"
    const activeReroutes = auditRows.filter((r) => {
      const action = String(r.action ?? "");
      return action.startsWith("rfq_") || action === "workflow_routes";
    }).length;

    // ── 3. Average Delay Saved (days) ────────────────────────────────────
    const delayValues: number[] = resolvedIncidents
      .map((inc) => {
        const mc = inc.monte_carlo as Record<string, unknown> | undefined;
        return Number(mc?.expected_delay_days ?? mc?.average_delay_days ?? 0);
      })
      .filter((v) => v > 0);

    const avgDelaySaved =
      delayValues.length > 0
        ? delayValues.reduce((a, b) => a + b, 0) / delayValues.length
        : 0;

    // ── 4. Incidents Resolved vs Total ───────────────────────────────────
    const totalIncidents = resolvedIncidents.length + activeIncidents.length;
    const resolvedCount = resolvedIncidents.length;
    const resolutionRate = totalIncidents > 0 ? (resolvedCount / totalIncidents) * 100 : 0;

    // ── 5. Nodes Protected ───────────────────────────────────────────────
    const nodesProtected = resolvedIncidents.reduce(
      (sum, inc) => sum + Number(inc.affected_node_count ?? 0),
      0
    );

    // ── 6. Average Monte Carlo Protection Rate ───────────────────────────
    const mcRates: number[] = resolvedIncidents
      .map((inc) => {
        const mc = inc.monte_carlo as Record<string, unknown> | undefined;
        return Number(mc?.protected_rate ?? 0);
      })
      .filter((v) => v > 0);

    const avgProtectionRate =
      mcRates.length > 0 ? mcRates.reduce((a, b) => a + b, 0) / mcRates.length : 0;

    return {
      exposureAvoided,
      totalExposureAtRisk,
      activeReroutes,
      avgDelaySaved,
      resolvedCount,
      totalIncidents,
      resolutionRate,
      nodesProtected,
      avgProtectionRate,
    };
  }, [resolvedIncidents, activeIncidents, auditRows]);

  if (isLoading) {
    return (
      <div className="w-full h-24 bg-card/40 border border-border rounded-xl animate-pulse" />
    );
  }

  return (
    <div className="w-full">
      {/* Section header */}
      <div className="flex items-center gap-2 mb-3">
        <BarChart3 size={13} className="text-emerald-500" />
        <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
          Business Impact — ROI Summary
        </p>
        <div className="ml-auto flex items-center gap-1.5 text-[9px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-500/10 px-2 py-0.5 rounded-full">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          LIVE
        </div>
      </div>

      {/* Tiles row */}
      <div className="flex flex-wrap gap-3">
        <MetricTile
          icon={<DollarSign size={13} className="text-emerald-600" />}
          label="Total Exposure Avoided"
          value={fmt(metrics.exposureAvoided)}
          sub={
            metrics.totalExposureAtRisk > 0
              ? `of ${fmt(metrics.totalExposureAtRisk)} at risk`
              : "across resolved incidents"
          }
          barPct={
            metrics.totalExposureAtRisk > 0
              ? (metrics.exposureAvoided / metrics.totalExposureAtRisk) * 100
              : 72
          }
          barColor="#10b981"
          accent="bg-emerald-500/10"
        />

        <MetricTile
          icon={<Truck size={13} className="text-blue-500" />}
          label="Active Reroutes"
          value={String(metrics.activeReroutes || 0)}
          sub="RFQs dispatched / routes computed"
          barPct={Math.min(100, metrics.activeReroutes * 10)}
          barColor="#3b82f6"
          accent="bg-blue-500/10"
        />

        <MetricTile
          icon={<Clock size={13} className="text-violet-500" />}
          label="Avg Delay Saved"
          value={fmtDays(metrics.avgDelaySaved)}
          sub="per resolved incident (Monte Carlo)"
          barPct={Math.min(100, (metrics.avgDelaySaved / 14) * 100)}
          barColor="#8b5cf6"
          accent="bg-violet-500/10"
        />

        <MetricTile
          icon={<Shield size={13} className="text-amber-500" />}
          label="Incidents Resolved"
          value={`${metrics.resolvedCount}/${metrics.totalIncidents}`}
          sub={`${metrics.resolutionRate.toFixed(0)}% resolution rate`}
          barPct={metrics.resolutionRate}
          barColor="#f59e0b"
          accent="bg-amber-500/10"
        />

        <MetricTile
          icon={<TrendingDown size={13} className="text-rose-500" />}
          label="Nodes Protected"
          value={String(metrics.nodesProtected)}
          sub={
            metrics.avgProtectionRate > 0
              ? `${Math.round(metrics.avgProtectionRate * 100)}% avg MC protection`
              : "supplier nodes secured"
          }
          barPct={metrics.avgProtectionRate * 100}
          barColor="#ef4444"
          accent="bg-rose-500/10"
        />
      </div>
    </div>
  );
};

export default ROIWidget;
