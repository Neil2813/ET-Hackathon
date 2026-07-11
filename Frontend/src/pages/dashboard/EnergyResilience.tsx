import { useMemo, useState } from "react";
import type { ElementType } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  Anchor,
  BarChart3,
  Boxes,
  BrainCircuit,
  CheckCircle2,
  Database,
  FlaskConical,
  Gauge,
  GitMerge,
  Loader2,
  RefreshCw,
  Shield,
  Ship,
  Zap,
  Leaf,
  GitBranch,
  Navigation,
} from "lucide-react";
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  LabelList,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type EnergyResilienceDashboard } from "@/lib/api";
import { CO2Badge } from "@/components/ui/CO2Badge";
import { getAccessToken, getUserId } from "@/lib/api";

const BASE = (import.meta.env.VITE_API_URL ?? "/api").replace(/\/+$/, "");

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  return {
    "Content-Type": "application/json",
    "X-User-Id": getUserId(),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

type ModuleKey = "ais" | "spr" | "compatibility" | "rag" | "ledger" | "esg" | "blend" | "routes";

const MODULES: Array<{ key: ModuleKey; label: string; icon: ElementType }> = [
  { key: "ais", label: "AIS Agent", icon: Ship },
  { key: "spr", label: "SPR Policy", icon: Gauge },
  { key: "compatibility", label: "Crude Match", icon: FlaskConical },
  { key: "blend", label: "Blend LP", icon: GitBranch },
  { key: "routes", label: "Route Compare", icon: Navigation },
  { key: "rag", label: "Risk RAG", icon: BrainCircuit },
  { key: "ledger", label: "Exchange Ledger", icon: GitMerge },
  { key: "esg", label: "ESG Carbon", icon: Leaf },
];

function pct(value: unknown) {
  return `${Math.round(Number(value || 0) * 100)}%`;
}

function fixed(value: unknown, digits = 1) {
  return Number(value || 0).toFixed(digits);
}

function statusStyle(status: string) {
  const normalized = status.toLowerCase();
  if (normalized === "critical") return "bg-red-50 text-red-700 border-red-200";
  if (normalized === "watch") return "bg-amber-50 text-amber-700 border-amber-200";
  return "bg-emerald-50 text-emerald-700 border-emerald-200";
}

function MetricTile({
  label,
  value,
  icon: Icon,
  tone = "text-slate-900",
}: {
  label: string;
  value: string;
  icon: ElementType;
  tone?: string;
}) {
  return (
    <div className="border border-slate-200 bg-white p-4 rounded shadow-sm min-w-0">
      <div className="flex items-center gap-2 text-slate-400">
        <Icon size={14} />
        <span className="text-[10px] font-mono font-bold uppercase tracking-widest truncate">{label}</span>
      </div>
      <div className={`mt-3 text-2xl font-headline font-bold tracking-wide ${tone}`}>{value}</div>
    </div>
  );
}

const AisTooltip = ({ active, payload }: any) => {
  if (active && payload && payload.length) {
    const data = payload[0].payload;
    return (
      <div className="bg-white/95 backdrop-blur-sm border border-slate-100 rounded-xl p-3.5 shadow-xl transition-all duration-200">
        <p className="text-[10px] font-mono font-bold uppercase tracking-wider text-slate-400">{data.corridor || "Spatial Forecast"}</p>
        <p className="text-sm font-bold text-slate-900 mt-1">{data.name}</p>
        <div className="flex items-center gap-2 mt-2">
          <span className="w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse" />
          <span className="text-xs font-semibold text-slate-700">
            Anomaly Score: <span className="font-bold text-slate-900">{pct(data.anomaly_score)}</span>
          </span>
        </div>
      </div>
    );
  }
  return null;
};

function AisPanel({ data }: { data: EnergyResilienceDashboard }) {
  const vessels = data.ais.vessels;
  const [activeIndex, setActiveIndex] = useState<number | null>(null);

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-4">
      <div className="border border-slate-200 bg-white rounded shadow-sm p-5 min-h-[320px]">
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Spatial-Temporal AIS Forecast</p>
            <h2 className="font-headline text-xl font-bold text-slate-900 mt-1">Dark-Ship and Transit Deviation Watch</h2>
          </div>
          <span className="text-xs font-mono font-bold text-blue-600 bg-blue-50 border border-blue-100 px-2.5 py-1 rounded">
            {data.ais.lead_time_hours}h lead
          </span>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={vessels} barCategoryGap={0} margin={{ top: 40, right: 10, left: 10, bottom: 5 }}>
              <CartesianGrid strokeDasharray="0" stroke="#f1f5f9" vertical={true} horizontal={false} />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} height={54} />
              <YAxis domain={[0, 1.2]} tick={{ fontSize: 11 }} />
              <Tooltip cursor={{ fill: 'rgba(241, 245, 249, 0.45)' }} content={<AisTooltip />} />
              <Bar
                dataKey="anomaly_score"
                radius={0}
                onMouseEnter={(_, index) => setActiveIndex(index)}
                onMouseLeave={() => setActiveIndex(null)}
              >
                {vessels.map((entry, index) => {
                  const isHovered = activeIndex === index;
                  const hasActive = activeIndex !== null;
                  return (
                    <Cell
                      key={`cell-${index}`}
                      fill="#dc2626"
                      opacity={hasActive ? (isHovered ? 1.0 : 0.4) : 1.0}
                      style={{
                        transition: "all 200ms ease",
                        cursor: "pointer",
                      }}
                    />
                  );
                })}
                <LabelList
                  dataKey="name"
                  position="top"
                  offset={18}
                  style={{
                    fontSize: 9,
                    fill: '#64748b',
                    fontWeight: 500,
                    transition: "all 200ms ease",
                  }}
                />
                <LabelList
                  dataKey="anomaly_score"
                  position="top"
                  offset={4}
                  formatter={(val: any) => pct(val)}
                  style={{
                    fontSize: 11,
                    fill: '#0f172a',
                    fontWeight: 'bold',
                    transition: "all 200ms ease",
                  }}
                />
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="space-y-3">
        {vessels.map((vessel) => (
          <div key={String(vessel.mmsi)} className="border border-slate-200 bg-white rounded shadow-sm p-4">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-bold text-slate-900 truncate">{String(vessel.name)}</p>
                <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400 mt-1">{String(vessel.corridor)}</p>
              </div>
              <span className={`text-[10px] font-mono font-bold uppercase px-2 py-1 rounded border ${statusStyle(String(vessel.status))}`}>
                {String(vessel.status)}
              </span>
            </div>
            <div className="grid grid-cols-3 gap-2 mt-4 text-xs">
              <div>
                <p className="text-slate-400 font-mono uppercase font-bold">AIS gap</p>
                <p className="font-bold text-slate-800 mt-1">{String(vessel.ais_gap_minutes)}m</p>
              </div>
              <div>
                <p className="text-slate-400 font-mono uppercase font-bold">Speed</p>
                <p className="font-bold text-slate-800 mt-1">{fixed(vessel.speed_knots)} kn</p>
              </div>
              <div>
                <p className="text-slate-400 font-mono uppercase font-bold">Deviation</p>
                <p className="font-bold text-slate-800 mt-1">{fixed(vessel.route_deviation_nm)} nm</p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function SprPanel({ data }: { data: EnergyResilienceDashboard }) {
  const chartData = data.spr.schedule.slice(0, 30);
  const action = data.spr.recommended_action;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_360px] gap-4">
      <div className="border border-slate-200 bg-white rounded shadow-sm p-5 min-h-[320px]">
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Reinforcement Learning Policy Surface</p>
            <h2 className="font-headline text-xl font-bold text-slate-900 mt-1">SPR Drawdown Stress Curve</h2>
          </div>
          <span className="text-xs font-mono font-bold text-slate-600 bg-slate-50 border border-slate-200 px-2.5 py-1 rounded">
            {data.spr.agent}
          </span>
        </div>
        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={chartData}>
              <defs>
                <linearGradient id="colorSpr" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#2563eb" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#93c5fd" stopOpacity={0.1} />
                </linearGradient>
                <linearGradient id="colorStress" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="5%" stopColor="#dc2626" stopOpacity={0.8} />
                  <stop offset="95%" stopColor="#fca5a5" stopOpacity={0.1} />
                </linearGradient>
              </defs>
              <CartesianGrid strokeDasharray="3 3" stroke="#f1f5f9" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" domain={[0, 1]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Area yAxisId="left" type="monotone" dataKey="spr_cover_days_remaining" stroke="#2563eb" strokeWidth={2} fillOpacity={1} fill="url(#colorSpr)" dot={false} />
              <Area yAxisId="right" type="monotone" dataKey="stress_index" stroke="#dc2626" strokeWidth={2} fillOpacity={1} fill="url(#colorStress)" dot={false} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      </div>
      <div className="border border-slate-200 bg-white rounded shadow-sm p-5">
        <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Recommended Action</p>
        <div className="mt-4 space-y-4">
          <MetricTile label="Drawdown Rate" value={`${fixed(action.drawdown_rate_mbd, 2)} mbd`} icon={Zap} tone="text-red-600" />
          <MetricTile label="Average Stress" value={pct(data.spr.average_stress_index)} icon={Activity} tone="text-amber-600" />
          <MetricTile label="Initial Inventory" value={`${fixed(data.spr.initial_inventory_mmbbl, 1)} mmbbl`} icon={Database} tone="text-blue-600" />
        </div>
        <p className="text-sm text-slate-600 leading-relaxed mt-4 font-medium">
          {String(action.forward_procurement || data.spr.policy_summary)}
        </p>
      </div>
    </div>
  );
}

function CompatibilityPanel({ data }: { data: EnergyResilienceDashboard }) {
  return (
    <div className="space-y-4">
      <div className="border border-slate-200 bg-white rounded shadow-sm p-5">
        <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Blocked Feedstock</p>
        <div className="flex flex-wrap items-center gap-3 mt-3">
          <h2 className="font-headline text-xl font-bold text-slate-900">{String(data.compatibility.blocked_grade.name)}</h2>
          <span className="text-xs font-mono font-bold text-red-600 bg-red-50 border border-red-100 px-2.5 py-1 rounded">blocked</span>
          <span className="text-xs font-mono font-bold text-slate-500">
            API {fixed(data.compatibility.blocked_grade.api_gravity)} / sulfur {fixed(data.compatibility.blocked_grade.sulfur_pct)}%
          </span>
        </div>
      </div>
      <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
        {data.compatibility.matches.map((row, index) => {
          const refinery = row.refinery as Record<string, unknown>;
          const alternatives = (row.alternatives as Array<Record<string, unknown>>) || [];
          return (
            <div key={String(refinery.id || index)} className="border border-slate-200 bg-white rounded shadow-sm p-5">
              <div className="flex items-start justify-between gap-4">
                <div>
                  <p className="text-sm font-bold text-slate-900">{String(refinery.name)}</p>
                  <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400 mt-1">
                    {String(refinery.operator)} / {String(refinery.privacy_band)}
                  </p>
                </div>
                <span className="text-xs font-mono font-bold text-slate-600 bg-slate-50 border border-slate-200 px-2 py-1 rounded">
                  {alternatives.length} viable
                </span>
              </div>
              <div className="mt-4 space-y-3">
                {alternatives.map((alt) => {
                  const crude = alt.crude as Record<string, unknown>;
                  return (
                    <div key={String(crude.id)} className="bg-slate-50 border border-slate-200 rounded p-3">
                      <div className="flex items-center justify-between gap-3">
                        <span className="font-bold text-sm text-slate-900">{String(crude.name)}</span>
                        <span className="text-xs font-mono font-bold text-emerald-700">{pct(alt.compatibility_score)}</span>
                      </div>
                      <p className="text-xs text-slate-600 font-medium mt-2">{String(alt.blend_note)}</p>
                    </div>
                  );
                })}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ── Blend LP Optimizer Panel ──────────────────────────────────────────────── */
function BlendPanel({ data }: { data: EnergyResilienceDashboard }) {
  const blockedGrade = String(data.compatibility.blocked_grade.id || "iranian_light");
  const [blendData, setBlendData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchBlend = async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(
        `${BASE}/api/energy-resilience/blend-optimizer?blocked_grade=${encodeURIComponent(blockedGrade)}`,
        { headers: authHeaders() }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setBlendData(await res.json());
    } catch (e: any) {
      setError(e.message || "Failed to fetch blend recipes");
    } finally { setLoading(false); }
  };

  const BLEND_COLORS = ["#2563eb", "#16a34a", "#dc2626", "#f59e0b", "#7c3aed", "#0891b2"];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border border-violet-200 bg-violet-50 rounded shadow-sm p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-violet-500">Linear Programming · scipy HiGHS Solver</p>
            <h2 className="font-headline text-lg font-bold text-slate-900 mt-1">Optimal Crude Blend Recipes</h2>
            <p className="text-xs text-slate-500 mt-1">
              Blocked: <span className="font-bold text-red-600">{String(data.compatibility.blocked_grade.name)}</span>
              {" "}— finds minimum-cost multi-crude blend satisfying each refinery's API gravity, sulfur &amp; viscosity spec.
            </p>
          </div>
          <button
            onClick={fetchBlend}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-violet-600 text-white text-xs font-bold rounded hover:bg-violet-700 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 size={13} className="animate-spin" /> : <GitBranch size={13} />}
            {loading ? "Solving…" : "Run LP Solver"}
          </button>
        </div>
        {error && <p className="mt-3 text-xs text-red-600 font-mono">{error}</p>}\
      </div>

      {!blendData && !loading && (
        <div className="border border-dashed border-slate-300 rounded p-10 text-center">
          <GitBranch size={32} className="text-violet-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500 font-medium">Click "Run LP Solver" to compute optimal blend recipes</p>
          <p className="text-xs text-slate-400 mt-1">scipy HiGHS finds the minimum-cost crude mix satisfying all refinery assay constraints</p>
        </div>
      )}

      {blendData && (
        <>
          {/* Summary */}
          <div className="grid grid-cols-3 gap-3">
            <div className="border border-slate-200 bg-white rounded p-4 text-center">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">Refineries</p>
              <p className="text-2xl font-bold text-slate-900 mt-1">{blendData.refineries_analysed}</p>
            </div>
            <div className="border border-emerald-200 bg-emerald-50 rounded p-4 text-center">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-emerald-600">Feasible</p>
              <p className="text-2xl font-bold text-emerald-700 mt-1">{blendData.feasible_count}</p>
            </div>
            <div className="border border-red-200 bg-red-50 rounded p-4 text-center">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-red-500">Infeasible</p>
              <p className="text-2xl font-bold text-red-700 mt-1">{blendData.infeasible_count}</p>
            </div>
          </div>

          {/* Per-refinery blend cards */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {(blendData.blend_recipes as any[]).map((result: any, idx: number) => (
              <div key={idx} className={`border rounded shadow-sm p-5 ${
                result.status === "optimal"
                  ? "border-emerald-200 bg-white"
                  : "border-red-200 bg-red-50"
              }`}>
                <div className="flex items-start justify-between gap-3 mb-4">
                  <div>
                    <p className="text-sm font-bold text-slate-900">{String(result.refinery?.name)}</p>
                    <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400 mt-0.5">
                      {String(result.refinery?.operator)} · API {fixed(result.refinery?.api_min)}-{fixed(result.refinery?.api_max)} / S≤{fixed(result.refinery?.sulfur_max_pct)}%
                    </p>
                  </div>
                  <span className={`text-[10px] font-mono font-bold uppercase px-2 py-1 rounded border ${
                    result.status === "optimal"
                      ? "bg-emerald-50 text-emerald-700 border-emerald-200"
                      : "bg-red-50 text-red-700 border-red-200"
                  }`}>
                    {result.status}
                  </span>
                </div>

                {result.status === "optimal" && result.recipe && (
                  <>
                    {/* Blend bar chart */}
                    <div className="space-y-2 mb-4">
                      {(result.recipe as any[]).map((item: any, i: number) => (
                        <div key={i}>
                          <div className="flex justify-between text-xs mb-1">
                            <span className="font-bold text-slate-800">{String(item.crude?.name)}</span>
                            <span className="font-mono font-bold" style={{ color: BLEND_COLORS[i % BLEND_COLORS.length] }}>
                              {Number(item.fraction_pct).toFixed(1)}% · {Number(item.daily_mbd).toFixed(3)} mbd
                            </span>
                          </div>
                          <div className="h-2.5 bg-slate-100 rounded overflow-hidden">
                            <div
                              className="h-full rounded transition-all duration-500"
                              style={{
                                width: `${Number(item.fraction_pct)}%`,
                                backgroundColor: BLEND_COLORS[i % BLEND_COLORS.length],
                              }}
                            />
                          </div>
                        </div>
                      ))}
                    </div>

                    {/* Blended assay properties */}
                    <div className="grid grid-cols-3 gap-2 pt-3 border-t border-slate-100">
                      <div className="text-center">
                        <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-slate-400">Blend API</p>
                        <p className={`text-sm font-bold mt-0.5 ${
                          result.meets_spec ? "text-emerald-700" : "text-red-600"
                        }`}>{fixed(result.blend_properties?.api_gravity)}°</p>
                      </div>
                      <div className="text-center">
                        <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-slate-400">Sulfur</p>
                        <p className={`text-sm font-bold mt-0.5 ${
                          result.meets_spec ? "text-emerald-700" : "text-red-600"
                        }`}>{fixed(result.blend_properties?.sulfur_pct, 3)}%</p>
                      </div>
                      <div className="text-center">
                        <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-slate-400">Viscosity</p>
                        <p className={`text-sm font-bold mt-0.5 ${
                          result.meets_spec ? "text-emerald-700" : "text-red-600"
                        }`}>{fixed(result.blend_properties?.viscosity_cst, 1)} cSt</p>
                      </div>
                    </div>
                    {result.meets_spec !== undefined && (
                      <div className={`mt-3 text-[10px] font-mono font-bold uppercase px-2 py-1 rounded text-center ${
                        result.meets_spec
                          ? "bg-emerald-50 text-emerald-700 border border-emerald-200"
                          : "bg-amber-50 text-amber-700 border border-amber-200"
                      }`}>\
                        {result.meets_spec ? "✓ All assay constraints satisfied" : "⚠ Blend outside spec — manual review needed"}\
                      </div>
                    )}
                  </>
                )}

                {result.status !== "optimal" && (
                  <p className="text-xs text-red-700 font-medium">{String(result.message || "No feasible blend found.")}</p>
                )}
              </div>
            ))}
          </div>
          <p className="text-[10px] text-slate-400 font-mono text-center">Solver: scipy HiGHS LP · Max 60% single-grade concentration · Objective: maximise throughput availability</p>
        </>
      )}
    </div>
  );
}

/* ── Route Comparison Panel (Suez vs Cape) ─────────────────────────────────── */
function RouteComparePanel({ data }: { data: EnergyResilienceDashboard }) {
  // Derive corridor risk from live RAG data
  const corridorRisk = useMemo(() => {
    const ragRisk = data.rag?.risk_by_corridor as Record<string, any> | undefined;
    if (!ragRisk) return 0.65;
    const babScore = ragRisk["Bab el-Mandeb"]?.risk_score ?? 0;
    const hormuzScore = ragRisk["Strait of Hormuz"]?.risk_score ?? 0;
    return Math.max(babScore, hormuzScore);
  }, [data]);

  const [routeData, setRouteData] = useState<any>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchRoutes = async () => {
    setLoading(true); setError(null);
    try {
      const res = await fetch(
        `${BASE}/api/energy-resilience/route-comparison?corridor_risk=${corridorRisk.toFixed(3)}`,
        { headers: authHeaders() }
      );
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setRouteData(await res.json());
    } catch (e: any) {
      setError(e.message || "Failed to fetch route comparison");
    } finally { setLoading(false); }
  };

  const recColor: Record<string, string> = {
    suez: "border-blue-300 bg-blue-50",
    cape: "border-amber-300 bg-amber-50",
    cape_strongly_recommended: "border-red-300 bg-red-50",
  };
  const recTextColor: Record<string, string> = {
    suez: "text-blue-800",
    cape: "text-amber-800",
    cape_strongly_recommended: "text-red-800",
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="border border-blue-200 bg-blue-50 rounded shadow-sm p-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-blue-500">Geospatial Routing Engine · Gulf → India</p>
            <h2 className="font-headline text-lg font-bold text-slate-900 mt-1">Suez Canal vs Cape of Good Hope</h2>
            <p className="text-xs text-slate-600 mt-1">
              Live corridor risk: <span className={`font-bold ${
                corridorRisk >= 0.75 ? "text-red-600" : corridorRisk >= 0.5 ? "text-amber-600" : "text-emerald-600"
              }`}>{pct(corridorRisk)}</span> · War-risk insurance and charter rate impact computed per tanker class.
            </p>
          </div>
          <button
            onClick={fetchRoutes}
            disabled={loading}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white text-xs font-bold rounded hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            {loading ? <Loader2 size={13} className="animate-spin" /> : <Navigation size={13} />}
            {loading ? "Computing…" : "Compare Routes"}
          </button>
        </div>
        {error && <p className="mt-3 text-xs text-red-600 font-mono">{error}</p>}
      </div>

      {!routeData && !loading && (
        <div className="border border-dashed border-slate-300 rounded p-10 text-center">
          <Navigation size={32} className="text-blue-300 mx-auto mb-3" />
          <p className="text-sm text-slate-500 font-medium">Click "Compare Routes" to run the routing engine</p>
          <p className="text-xs text-slate-400 mt-1">Computes cost, transit days, war-risk premium &amp; CO₂ for Suez and Cape routes</p>
        </div>
      )}

      {routeData && (
        <>
          {/* Recommendation banner */}
          <div className={`border-2 rounded p-4 ${recColor[routeData.recommendation] || "border-slate-200 bg-slate-50"}`}>
            <p className={`text-sm font-bold ${recTextColor[routeData.recommendation] || "text-slate-800"}`}>
              {routeData.recommendation === "cape_strongly_recommended" ? "🚨" : routeData.recommendation === "cape" ? "⚠️" : "✅"}
              {" "}{String(routeData.recommendation_text)}
            </p>
            <p className="text-xs text-slate-500 mt-1 font-mono">
              Breakeven risk threshold: {pct(routeData.breakeven_risk)} · Current: {pct(routeData.corridor_risk_score)}
            </p>
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className="border border-slate-200 bg-white rounded p-3 text-center">
              <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-slate-400">Extra Days (Cape)</p>
              <p className="text-xl font-bold text-amber-700 mt-1">+{fixed(routeData.time_delta_days, 1)}d</p>
            </div>
            <div className="border border-slate-200 bg-white rounded p-3 text-center">
              <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-slate-400">Extra Cost (Cape)</p>
              <p className={`text-xl font-bold mt-1 ${
                routeData.cost_delta_usd <= 0 ? "text-emerald-700" : "text-red-600"
              }`}>{routeData.cost_delta_usd <= 0 ? "−" : "+"}${Math.abs(routeData.cost_delta_usd / 1000).toFixed(0)}K</p>
            </div>
            <div className="border border-slate-200 bg-white rounded p-3 text-center">
              <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-slate-400">Risk Reduction</p>
              <p className="text-xl font-bold text-emerald-700 mt-1">{pct(routeData.risk_reduction)}</p>
            </div>
            <div className="border border-slate-200 bg-white rounded p-3 text-center">
              <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-slate-400">War Risk (Suez)</p>
              <p className="text-xl font-bold text-red-600 mt-1">{pct(routeData.war_risk_suez)}</p>
            </div>
          </div>

          {/* Route table — VLCC + Suezmax side by side */}
          <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
            {/* Suez routes */}
            <div className="border border-blue-200 bg-white rounded shadow-sm p-5">
              <div className="flex items-center gap-2 mb-4">
                <span className="w-3 h-3 rounded-full bg-blue-500 inline-block" />
                <p className="text-xs font-mono font-bold uppercase tracking-widest text-blue-600">Suez Canal / Red Sea</p>
                <span className="ml-auto text-[10px] font-mono font-bold text-slate-400">War risk: {pct(routeData.war_risk_suez)}</span>
              </div>
              <div className="space-y-3">
                {(routeData.suez_routes as any[]).map((r: any, i: number) => (
                  <div key={i} className="bg-slate-50 border border-slate-200 rounded p-3">
                    <p className="text-xs font-bold text-slate-800 mb-2">{String(r.tanker_class)}</p>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <p className="text-[9px] font-mono font-bold uppercase text-slate-400">Distance</p>
                        <p className="font-bold text-slate-800 mt-0.5">{Math.round(r.distance_km).toLocaleString()} km</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-mono font-bold uppercase text-slate-400">Transit</p>
                        <p className="font-bold text-slate-800 mt-0.5">{fixed(r.transit_days, 1)} days</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-mono font-bold uppercase text-slate-400">Cost</p>
                        <p className="font-bold text-blue-700 mt-0.5">${(r.cost_usd / 1_000_000).toFixed(2)}M</p>
                      </div>
                    </div>
                    <div className="flex gap-3 mt-2">
                      <span className="text-[9px] font-mono text-slate-400">CO₂: {fixed(r.co2_tons, 0)}t</span>
                      <span className="text-[9px] font-mono text-red-500">Risk: {pct(r.risk_score)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>

            {/* Cape routes */}
            <div className="border border-emerald-200 bg-white rounded shadow-sm p-5">
              <div className="flex items-center gap-2 mb-4">
                <span className="w-3 h-3 rounded-full bg-emerald-500 inline-block" />
                <p className="text-xs font-mono font-bold uppercase tracking-widest text-emerald-600">Cape of Good Hope</p>
                <span className="ml-auto text-[10px] font-mono font-bold text-slate-400">War risk: {pct(routeData.war_risk_cape)}</span>
              </div>
              <div className="space-y-3">
                {(routeData.cape_routes as any[]).map((r: any, i: number) => (
                  <div key={i} className="bg-slate-50 border border-slate-200 rounded p-3">
                    <p className="text-xs font-bold text-slate-800 mb-2">{String(r.tanker_class)}</p>
                    <div className="grid grid-cols-3 gap-2 text-xs">
                      <div>
                        <p className="text-[9px] font-mono font-bold uppercase text-slate-400">Distance</p>
                        <p className="font-bold text-slate-800 mt-0.5">{Math.round(r.distance_km).toLocaleString()} km</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-mono font-bold uppercase text-slate-400">Transit</p>
                        <p className="font-bold text-slate-800 mt-0.5">{fixed(r.transit_days, 1)} days</p>
                      </div>
                      <div>
                        <p className="text-[9px] font-mono font-bold uppercase text-slate-400">Cost</p>
                        <p className="font-bold text-emerald-700 mt-0.5">${(r.cost_usd / 1_000_000).toFixed(2)}M</p>
                      </div>
                    </div>
                    <div className="flex gap-3 mt-2">
                      <span className="text-[9px] font-mono text-slate-400">CO₂: {fixed(r.co2_tons, 0)}t</span>
                      <span className="text-[9px] font-mono text-emerald-600">Risk: {pct(r.risk_score)}</span>
                      <span className="text-[9px] font-mono text-amber-600">+{fixed(r.extra_days_vs_suez, 1)}d vs Suez</span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <p className="text-[10px] text-slate-400 font-mono text-center">
            Origin: {String(routeData.origin_label)} → Destination: {String(routeData.destination_label)}
          </p>
        </>
      )}
    </div>
  );
}

function RagPanel({ data }: { data: EnergyResilienceDashboard }) {
  const corridors = Object.entries(data.rag.risk_by_corridor).map(([name, values]) => ({ name, ...values })) as any[];
  const wb = (data.rag as any).india_vulnerability as Record<string, any> | undefined;

  return (
    <div className="space-y-4">
      {/* India Vulnerability Card — World Bank PPP vs Nominal */}
      {wb && (
        <div className="border border-blue-200 bg-blue-50 rounded shadow-sm p-5">
          <div className="flex flex-wrap items-center justify-between gap-3 mb-1">
            <div>
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-blue-500">World Bank Open Data · {wb.data_year}</p>
              <h2 className="font-headline text-lg font-bold text-slate-900 mt-1">India Energy Vulnerability Profile</h2>
            </div>
            <div className="text-right">
              <p className="text-[10px] font-mono font-bold text-blue-700 bg-blue-100 border border-blue-200 px-2 py-1 rounded">
                ₹{wb.usd_inr_rate}/USD nominal &nbsp;·&nbsp; ₹{wb.ppp_rate}/intl$ PPP
              </p>
            </div>
          </div>

          {/* PPP explanation banner */}
          <div className="mt-3 mb-4 bg-amber-50 border border-amber-200 rounded p-3 text-xs text-amber-800 leading-relaxed">
            <span className="font-bold">Why two numbers?</span> Nominal (₹{wb.usd_inr_rate}/USD) = what India
            pays in <span className="font-bold">foreign exchange</span> — the actual forex outflow.
            PPP (₹{wb.ppp_rate}/intl$) = the <span className="font-bold">real domestic impact</span> — what
            the same cost means in Indian purchasing power terms.
            At a PPP ratio of <span className="font-bold">{wb.ppp_ratio}×</span>, ₹1 in India
            buys {wb.ppp_ratio}× more than the nominal rate implies,
            because wages, land and services are far cheaper than in the US.
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Nominal forex cost */}
            <div className="bg-white border border-slate-200 rounded p-4">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400 mb-3">
                Forex / Nominal (₹{wb.usd_inr_rate}/USD)
              </p>
              <div className="space-y-3">
                <div>
                  <p className="text-[10px] text-slate-400 font-mono uppercase">GDP (nominal)</p>
                  <p className="text-xl font-bold text-slate-900 mt-0.5">{String(wb.gdp_inr_formatted ?? "N/A")}</p>
                  <p className="text-[10px] text-slate-400">Actual forex value of economy</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-400 font-mono uppercase">Annual Fuel Import Bill</p>
                  <p className="text-xl font-bold text-red-700 mt-0.5">{String(wb.fuel_import_value_inr ?? "N/A")}</p>
                  <p className="text-[10px] text-slate-400">Foreign exchange actually spent on fuel ({String(wb.fuel_import_value_usd_display ?? "")})</p>
                </div>
              </div>
            </div>

            {/* PPP real domestic impact */}
            <div className="bg-white border border-emerald-200 rounded p-4">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-emerald-600 mb-3">
                PPP / Real Domestic Impact (₹{wb.ppp_rate}/intl$)
              </p>
              <div className="space-y-3">
                <div>
                  <p className="text-[10px] text-slate-400 font-mono uppercase">GDP (PPP)</p>
                  <p className="text-xl font-bold text-slate-900 mt-0.5">{String(wb.gdp_ppp_intl_formatted ?? "N/A")}</p>
                  <p className="text-[10px] text-slate-400">Actual purchasing power of economy</p>
                </div>
                <div>
                  <p className="text-[10px] text-slate-400 font-mono uppercase">Fuel Cost — Domestic Impact</p>
                  <p className="text-xl font-bold text-emerald-700 mt-0.5">{String(wb.fuel_import_value_ppp_inr ?? "N/A")}</p>
                  <p className="text-[10px] text-slate-400">Real burden in Indian purchasing-power terms</p>
                </div>
              </div>
            </div>
          </div>

          {/* Supplemental indicators */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3 mt-3">
            <div className="bg-white border border-blue-100 rounded p-3">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">Energy Import %</p>
              <p className="text-lg font-bold text-amber-700 mt-1">{fixed(wb.energy_import_pct)}%</p>
              <p className="text-[10px] text-slate-400 mt-0.5">Of total energy consumed</p>
            </div>
            <div className="bg-white border border-blue-100 rounded p-3">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">Fuel of Imports</p>
              <p className="text-lg font-bold text-slate-900 mt-1">{fixed(wb.fuel_import_pct_merch)}%</p>
              <p className="text-[10px] text-slate-400 mt-0.5">Of merchandise imports</p>
            </div>
            <div className="bg-white border border-blue-100 rounded p-3">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">PPP Ratio</p>
              <p className="text-lg font-bold text-blue-700 mt-1">{fixed(wb.ppp_ratio, 2)}×</p>
              <p className="text-[10px] text-slate-400 mt-0.5">Domestic vs nominal</p>
            </div>
            <div className="bg-white border border-blue-100 rounded p-3">
              <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-400">CO₂ per Capita</p>
              <p className="text-lg font-bold text-emerald-700 mt-1">{fixed(wb.co2_per_capita, 2)}t</p>
              <p className="text-[10px] text-slate-400 mt-0.5">Metric tons CO₂/year</p>
            </div>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 xl:grid-cols-[420px_minmax(0,1fr)] gap-4">
        <div className="border border-slate-200 bg-white rounded shadow-sm p-5">
          <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Vector Risk Store</p>
          <h2 className="font-headline text-xl font-bold text-slate-900 mt-1">{data.rag.vector_store}</h2>
          <div className="mt-5 space-y-3">
            {corridors.map((corridor) => (
              <div key={corridor.name} className="bg-slate-50 border border-slate-200 rounded p-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-bold text-slate-900">{corridor.name}</span>
                  <span className="text-xs font-mono font-bold text-red-600">{pct(corridor.risk_score)}</span>
                </div>
                <div className="mt-3 h-2 bg-white border border-slate-200 rounded overflow-hidden">
                  <div className="h-full bg-red-500" style={{ width: pct(corridor.risk_score) }} />
                </div>
              </div>
            ))}
          </div>
        </div>
        <div className="border border-slate-200 bg-white rounded shadow-sm p-5">
          <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400 mb-4">Extracted Threat Documents</p>
          <div className="space-y-3">
            {data.rag.documents.map((doc, index) => (
              <div key={index} className="border border-slate-200 rounded p-4">
                <div className="flex flex-wrap items-center gap-2 mb-2">
                  <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-blue-600 bg-blue-50 border border-blue-100 px-2 py-1 rounded">
                    {String(doc.source)}
                  </span>
                  <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-slate-500">{String(doc.threat_type)}</span>
                </div>
                <p className="text-sm font-bold text-slate-900">{String(doc.title)}</p>
                {(doc as any).narrative && (
                  <p className="text-xs text-slate-600 font-medium mt-2 leading-relaxed">{String((doc as any).narrative)}</p>
                )}
                <p className="text-xs text-slate-500 font-mono font-bold mt-2">
                  {String(doc.corridor)} / likelihood {pct(doc.likelihood)} / severity {pct(doc.severity)}
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

function LedgerPanel({ data }: { data: EnergyResilienceDashboard }) {
  const rec = data.exchange_ledger.recommendation;
  const from = (rec.from_refinery || {}) as Record<string, unknown>;
  const to = (rec.to_refinery || {}) as Record<string, unknown>;
  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-4">
      <div className="border border-slate-200 bg-white rounded shadow-sm p-5">
        <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400 mb-4">Private Inventory Bands</p>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {data.exchange_ledger.participants.map((refinery, index) => (
            <div key={String(refinery.id || index)} className="bg-slate-50 border border-slate-200 rounded p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-bold text-slate-900">{String(refinery.name)}</p>
                  <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400 mt-1">{String(refinery.operator)}</p>
                </div>
                <span className="text-xs font-mono font-bold text-slate-600">{fixed(refinery.inventory_days)}d</span>
              </div>
              <div className="mt-3 h-2 bg-white border border-slate-200 rounded overflow-hidden">
                <div className="h-full bg-blue-600" style={{ width: `${Math.min(100, Number(refinery.inventory_days || 0) * 10)}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="border border-slate-200 bg-white rounded shadow-sm p-5">
        <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Swap Recommendation</p>
        <div className="mt-5 space-y-4">
          <div className="bg-emerald-50 border border-emerald-200 rounded p-4">
            <div className="flex items-center gap-2 text-emerald-700">
              <CheckCircle2 size={16} />
              <span className="text-xs font-mono font-bold uppercase tracking-widest">{fixed(rec.transfer_mbd, 3)} mbd transfer</span>
            </div>
            <p className="text-sm text-slate-800 font-bold mt-3">{String(from.name)} to {String(to.name)}</p>
            <p className="text-xs text-slate-600 font-medium mt-2">{String(rec.reason)}</p>
          </div>
          <div className="bg-slate-50 border border-slate-200 rounded p-4">
            <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Privacy Boundary</p>
            <p className="text-sm text-slate-600 font-medium leading-relaxed mt-2">{String(rec.privacy_boundary)}</p>
          </div>
        </div>
      </div>
    </div>
  );
}
function EsgPanel({ data }: { data: any }) {
  const esg = data.esg || { routes: [] };
  const routes = esg.routes || [];

  const chartData = routes.map((r: any) => ({
    name: r.mode === "tanker_vlcc" && r.lane === "Cape of Good Hope" ? "Cape Route (VLCC)" : r.mode === "tanker_vlcc" ? "Direct Route (VLCC)" : "Direct (Suezmax)",
    emissions: r.co2_data?.co2_emissions_metric_tons || 0,
    cost: r.co2_data?.carbon_cost_usd || 0,
  }));

  return (
    <div className="grid grid-cols-1 xl:grid-cols-[minmax(0,1fr)_380px] gap-4">
      <div className="border border-slate-200 bg-white rounded shadow-sm p-5 min-h-[320px]">
        <div className="flex items-center justify-between mb-5">
          <div>
            <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">Carbon & Emission Metrics</p>
            <h2 className="font-headline text-xl font-bold text-slate-900 mt-1">Comparative CO₂ Footprint</h2>
          </div>
          <span className="text-xs font-mono font-bold text-emerald-600 bg-emerald-50 border border-emerald-100 px-2.5 py-1 rounded">
            IMO Guidelines
          </span>
        </div>

        <div className="h-64">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="name" tick={{ fontSize: 10 }} />
              <YAxis tick={{ fontSize: 11 }} />
              <Tooltip formatter={(value) => [`${value} Tons`, 'Emissions']} />
              <Bar dataKey="emissions" fill="#059669" radius={[4, 4, 0, 0]} barSize={52} />
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="space-y-4">
        <div className="border border-slate-200 bg-white rounded shadow-sm p-5">
          <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400">ESG Performance</p>
          <div className="mt-4 space-y-3">
            <MetricTile label="Average ESG Rating" value={`${esg.average_esg_score || 85.0}/100`} icon={Leaf} tone="text-emerald-600" />
            <MetricTile label="Carbon Offset Cost" value={`$${esg.carbon_price_per_ton || 85}/ton`} icon={Activity} tone="text-slate-700" />
            <MetricTile label="Total CO₂ Saved" value={`${(esg.total_emissions_avoided_tons || 3450).toLocaleString()} t`} icon={Boxes} tone="text-blue-600" />
          </div>
        </div>

        <div className="border border-slate-200 bg-white rounded shadow-sm p-5 space-y-3">
          <p className="text-xs font-mono font-bold uppercase tracking-widest text-slate-400 mb-2">Maritime Reroute Scenarios</p>
          {routes.map((r: any, idx: number) => (
            <div key={idx} className="bg-slate-50 border border-slate-200 rounded p-3 space-y-2">
              <div className="flex items-center justify-between">
                <span className="font-bold text-sm text-slate-900 uppercase">{r.mode.replace("_", " ")}</span>
                <span className="text-xs font-semibold text-slate-500">{r.distance_km.toLocaleString()} km</span>
              </div>
              <p className="text-xs text-slate-600">Transit: <span className="font-semibold">{r.transit_days} Days</span></p>
              {r.co2_data && <CO2Badge co2Data={r.co2_data} />}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}


const EnergyResilience = () => {
  const [module, setModule] = useState<ModuleKey>("ais");
  const queryClient = useQueryClient();
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ["energy-resilience", "dashboard"],
    queryFn: api.energyResilience.dashboard,
    staleTime: 5 * 60 * 1000,
  });
  const refresh = useMutation({
    mutationFn: api.energyResilience.dashboard,
    onSuccess: (next) => queryClient.setQueryData(["energy-resilience", "dashboard"], next),
  });

  const activeContent = useMemo(() => {
    if (!data) return null;
    if (module === "ais") return <AisPanel data={data} />;
    if (module === "spr") return <SprPanel data={data} />;
    if (module === "compatibility") return <CompatibilityPanel data={data} />;
    if (module === "blend") return <BlendPanel data={data} />;
    if (module === "routes") return <RouteComparePanel data={data} />;
    if (module === "rag") return <RagPanel data={data} />;
    if (module === "esg") return <EsgPanel data={data} />;
    return <LedgerPanel data={data} />;
  }, [data, module]);

  if (isLoading) {
    return (
      <div className="h-[calc(100vh-120px)] flex items-center justify-center border border-slate-200 bg-white rounded">
        <Loader2 size={24} className="animate-spin text-red-500" />
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="border border-red-200 bg-red-50 rounded p-6 text-red-700">
        <p className="font-bold">Energy resilience dashboard failed to load.</p>
        <p className="text-sm mt-2">{error instanceof Error ? error.message : "Backend unavailable"}</p>
      </div>
    );
  }

  return (
    <div className="min-h-[calc(100vh-120px)] space-y-4">
      <div className="border border-slate-200 bg-white rounded shadow-sm p-5">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-red-500">
              <Shield size={18} />
              <span className="text-xs font-mono font-bold uppercase tracking-widest">National Energy Security</span>
            </div>
            <h1 className="font-headline text-2xl md:text-3xl font-bold text-slate-900 mt-2">
              AI-Driven Energy Supply Chain Resilience
            </h1>
          </div>
          <button
            type="button"
            onClick={() => refresh.mutate()}
            disabled={refresh.isPending}
            className="inline-flex items-center justify-center gap-2 px-4 py-2 bg-slate-900 text-white hover:bg-slate-800 disabled:opacity-50 rounded text-xs font-mono font-bold uppercase tracking-widest transition-colors"
          >
            {refresh.isPending ? <Loader2 size={14} className="animate-spin" /> : <RefreshCw size={14} />}
            Refresh Model
          </button>
        </div>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-3 mt-5">
          <MetricTile label="Resilience Score" value={pct(data.national_resilience_score)} icon={BarChart3} tone={data.status === "critical" ? "text-red-600" : "text-amber-600"} />
          <MetricTile label="Status" value={data.status.toUpperCase()} icon={AlertTriangle} tone={data.status === "critical" ? "text-red-600" : "text-emerald-600"} />
          <MetricTile label="High-Risk Corridors" value={String(data.ais.high_risk_corridors.length)} icon={Anchor} tone="text-blue-600" />
          <MetricTile label="Viable Crudes" value={String(data.compatibility.matches.reduce((sum, row) => sum + (((row.alternatives as unknown[]) || []).length), 0))} icon={Boxes} tone="text-emerald-600" />
        </div>
      </div>

      <div className="border border-slate-200 bg-white rounded shadow-sm p-2 flex flex-wrap gap-2">
        {MODULES.map((item) => {
          const Icon = item.icon;
          const selected = module === item.key;
          return (
            <button
              key={item.key}
              type="button"
              onClick={() => setModule(item.key)}
              className={`inline-flex items-center gap-2 px-3 py-2 rounded text-xs font-mono font-bold uppercase tracking-widest transition-colors ${selected ? "bg-red-50 text-red-600 border border-red-200" : "text-slate-500 hover:text-slate-900 hover:bg-slate-50 border border-transparent"
                }`}
            >
              <Icon size={14} />
              {item.label}
            </button>
          );
        })}
      </div>

      {activeContent}
    </div>
  );
};

export default EnergyResilience;
