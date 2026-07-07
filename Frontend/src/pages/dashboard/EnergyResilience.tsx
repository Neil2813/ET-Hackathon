import { useMemo, useState } from "react";
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
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { api, type EnergyResilienceDashboard } from "@/lib/api";

type ModuleKey = "ais" | "spr" | "compatibility" | "rag" | "ledger";

const MODULES: Array<{ key: ModuleKey; label: string; icon: React.ElementType }> = [
  { key: "ais", label: "AIS Agent", icon: Ship },
  { key: "spr", label: "SPR Policy", icon: Gauge },
  { key: "compatibility", label: "Crude Match", icon: FlaskConical },
  { key: "rag", label: "Risk RAG", icon: BrainCircuit },
  { key: "ledger", label: "Exchange Ledger", icon: GitMerge },
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
  icon: React.ElementType;
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

function AisPanel({ data }: { data: EnergyResilienceDashboard }) {
  const vessels = data.ais.vessels;
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
            <BarChart data={vessels}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} height={54} />
              <YAxis domain={[0, 1]} tick={{ fontSize: 11 }} />
              <Tooltip formatter={(value) => pct(value)} />
              <Bar dataKey="anomaly_score" fill="#dc2626" radius={[4, 4, 0, 0]} />
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
            <LineChart data={chartData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#e5e7eb" />
              <XAxis dataKey="day" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="left" tick={{ fontSize: 11 }} />
              <YAxis yAxisId="right" orientation="right" domain={[0, 1]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Line yAxisId="left" type="monotone" dataKey="spr_cover_days_remaining" stroke="#2563eb" dot={false} strokeWidth={2} />
              <Line yAxisId="right" type="monotone" dataKey="stress_index" stroke="#dc2626" dot={false} strokeWidth={2} />
            </LineChart>
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

function RagPanel({ data }: { data: EnergyResilienceDashboard }) {
  const corridors = Object.entries(data.rag.risk_by_corridor).map(([name, values]) => ({ name, ...values }));
  return (
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
              <p className="text-xs text-slate-500 font-mono font-bold mt-2">
                {String(doc.corridor)} / likelihood {pct(doc.likelihood)} / severity {pct(doc.severity)}
              </p>
            </div>
          ))}
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
    if (module === "rag") return <RagPanel data={data} />;
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
              className={`inline-flex items-center gap-2 px-3 py-2 rounded text-xs font-mono font-bold uppercase tracking-widest transition-colors ${
                selected ? "bg-red-50 text-red-600 border border-red-200" : "text-slate-500 hover:text-slate-900 hover:bg-slate-50 border border-transparent"
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
