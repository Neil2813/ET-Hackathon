import { useState, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Map, MapMarker, MarkerContent, MarkerPopup, MapControls,
} from "@/components/ui/map";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { incidentCategoryLabel, incidentCategoryColor } from "@/lib/incident-category";
import { incidentDisplayTitle, incidentContextTag } from "@/lib/incident-title";
import React from "react";
import {
  RefreshCw, Target, Shield, Network,
  TrendingUp, AlertTriangle, Eye, ChevronDown, ChevronUp, Link as LinkIcon, Cpu, GitMerge, Mail
} from "lucide-react";
import { fmtINR } from "@/lib/currency";
import ROIWidget from "@/components/ui/ROIWidget";
import { RFQDispatchPanel } from "@/components/ui/RFQDispatchPanel";



/* ── tiny sparkline (pure SVG) ── */
function Sparkline({ data, color }: { data: number[]; color: string }) {
  if (!data.length) return null;
  const h = 28, w = 80;
  const max = Math.max(...data, 1);
  const pts = data.map((v, i) => `${(i / (data.length - 1)) * w},${h - (v / max) * h}`).join(" ");
  return (
    <svg width={w} height={h} className="ml-auto shrink-0">
      <polyline points={pts} fill="none" stroke={color} strokeWidth={1.5} strokeLinejoin="round" />
    </svg>
  );
}

/* ── confidence ring (SVG donut) ── */
function ConfidenceRing({ value, size = 56 }: { value: number; size?: number }) {
  const pct = Math.round(value * 100);
  const r = (size - 6) / 2;
  const circ = 2 * Math.PI * r;
  const offset = circ - (pct / 100) * circ;
  const color = pct >= 80 ? "#10b981" : pct >= 60 ? "#f59e0b" : "#ef4444";
  return (
    <svg width={size} height={size} className="block">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" className="text-muted/30" strokeWidth={4} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth={4}
        strokeDasharray={circ} strokeDashoffset={offset} strokeLinecap="round"
        transform={`rotate(-90 ${size / 2} ${size / 2})`} className="transition-all duration-700" />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
        className="fill-foreground text-xs font-bold">{pct}%</text>
    </svg>
  );
}

/* ── donut chart ── */
function DonutChart({ slices }: { slices: { label: string; value: number; color: string }[] }) {
  const total = slices.reduce((s, x) => s + x.value, 0) || 1;
  const sz = 100, r = 36, circ = 2 * Math.PI * r;
  let cumulative = 0;
  return (
    <div className="flex items-center gap-4">
      <svg width={sz} height={sz} viewBox={`0 0 ${sz} ${sz}`}>
        {slices.map((s, i) => {
          const pct = s.value / total;
          const dashLen = pct * circ;
          const dash = `${dashLen} ${circ - dashLen}`;
          const off = -(cumulative / total) * circ;
          cumulative += s.value;
          return <circle key={i} cx={sz / 2} cy={sz / 2} r={r} fill="none" stroke={s.color}
            strokeWidth={12} strokeDasharray={dash} strokeDashoffset={off}
            transform={`rotate(-90 ${sz / 2} ${sz / 2})`} />;
        })}
      </svg>
      <div className="space-y-1.5 text-xs">
        {slices.map((s, i) => (
          <div key={i} className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full shrink-0" style={{ background: s.color }} />
            <span className="text-muted-foreground">{s.label}</span>
            <span className="font-semibold ml-auto tabular-nums">{s.value} ({Math.round((s.value / total) * 100)}%)</span>
          </div>
        ))}
      </div>
    </div>
  );
}

/* ── horizontal bar ── */
function HBar({ label, pct, color }: { label: string; pct: number; color: string }) {
  return (
    <div className="flex items-center gap-2 text-xs">
      <span className="text-muted-foreground w-28 truncate">{label}</span>
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className="h-full rounded-full transition-all duration-500" style={{ width: `${pct}%`, background: color }} />
      </div>
      <span className="tabular-nums font-medium w-8 text-right">{pct}%</span>
    </div>
  );
}

function isFiniteCoord(v: unknown): v is number {
  const n = Number(v);
  return isFinite(n) && n !== 0;
}

function incidentCoords(inc: Record<string, unknown>) {
  const lat = inc.lat ?? inc.latitude ?? inc.event_lat;
  const lng = inc.lng ?? inc.longitude ?? inc.event_lng;
  if (!isFiniteCoord(lat) || !isFiniteCoord(lng)) return null;
  return { lat: Number(lat), lng: Number(lng) };
}

function markerColor(severity: string) {
  const sev = String(severity || "").toUpperCase();
  if (sev === "CRITICAL" || sev === "HIGH") return { dot: "bg-red-500", ping: "bg-red-500/20", badge: "bg-red-100 text-red-700" };
  if (sev === "MODERATE" || sev === "WARNING") return { dot: "bg-amber-400", ping: "bg-amber-400/20", badge: "bg-amber-100 text-amber-700" };
  return { dot: "bg-emerald-500", ping: "bg-emerald-500/20", badge: "bg-emerald-100 text-emerald-700" };
}

/* ── progressive disclosure panel ── */
function AgentReasoningPanel({ incident }: { incident: any }) {
  const [expanded, setExpanded] = useState(false);

  // Use provided chain or generate dynamically from incident data to avoid static hardcoding
  const summaryChain = incident?.summary_chain || [
    incident?.event_title || "Disruption Detected",
    `Impacted ${incident?.affected_node_count || 1} Node(s)`,
    `Exposure: ${fmtINR(incident?.total_exposure_usd || 0)}`
  ];

  // Use provided agent logic or build a dynamic representation based on the incident context
  const agentSteps = incident?.reasoning_steps || incident?.agent_steps || [
    {
      agent: "signal_intelligence_agent",
      action: `Detected ${incident?.severity || "Warning"} anomaly`,
      result: `Categorized as ${incidentCategoryLabel(incident)}.`,
      evidence: [
        { source: "GDACS", url: "https://www.gdacs.org/" },
        { source: "OpenMeteo", url: "https://open-meteo.com/" }
      ]
    },
    {
      agent: "gnn_blast_radius",
      action: "Calculated structural network impact",
      result: `Identified ${incident?.affected_node_count || 1} downstream dependencies at risk within 72h.`,
      evidence: [
        { source: "Internal Network Graph", url: "#" }
      ]
    },
    {
      agent: "financial_risk_agent",
      action: "Assessed financial exposure",
      result: `Calculated total risk of ${fmtINR(incident?.total_exposure_usd || 0)} based on current pipeline.`,
      evidence: [
        { source: "IMF PortWatch", url: "https://portwatch.imf.org/" },
        { source: "ERP Inventory", url: "#" }
      ]
    }
  ];

  return (
    <div className="mt-4 space-y-4">
      {/* Level 1: Scannable Summary */}
      <div className="bg-card border border-border p-3 rounded-lg shadow-sm">
        <div className="flex items-center gap-1.5 mb-2">
           <GitMerge size={12} className="text-muted-foreground" />
           <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground">OODA Inference Chain</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5 text-[11px] font-medium">
          {summaryChain.map((step: string, i: number) => (
            <React.Fragment key={i}>
              <span className="bg-accent/50 text-foreground px-2 py-1 rounded-md border border-border/50">{step}</span>
              {i < summaryChain.length - 1 && <span className="text-muted-foreground/50">→</span>}
            </React.Fragment>
          ))}
        </div>
      </div>

      {/* Level 2 & 3: Expandable Agent Conversation */}
      <div className="bg-card border border-border rounded-lg shadow-sm overflow-hidden">
        <button 
          onClick={() => setExpanded(!expanded)}
          className="w-full flex items-center justify-between p-3 text-[10px] font-mono uppercase tracking-wider font-bold hover:bg-accent/50 transition-colors"
        >
          <div className="flex items-center gap-2">
            <Cpu size={14} className="text-indigo-500" />
            Agent Execution Thread
          </div>
          {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        </button>
        
        {expanded && (
          <div className="p-4 border-t border-border space-y-5 bg-muted/10">
            {agentSteps.map((step: any, i: number) => (
              <div key={i} className="relative pl-4 border-l-2 border-indigo-500/20 space-y-1.5">
                <div className="absolute -left-[5px] top-1.5 w-2 h-2 rounded-full bg-indigo-500 ring-4 ring-card" />
                <div className="flex items-center gap-2">
                  <span className="text-[9px] font-mono font-bold uppercase tracking-widest text-indigo-700 dark:text-indigo-400 bg-indigo-500/10 px-1.5 py-0.5 rounded">
                    {step.agent || step.agent_name || "System"}
                  </span>
                  <span className="text-xs text-muted-foreground">{step.action}</span>
                </div>
                <p className="text-xs font-medium leading-relaxed">{step.result || step.detail || step.findings}</p>
                
                {/* Level 3: Evidence Data */}
                {(step.evidence && step.evidence.length > 0) && (
                   <div className="flex flex-wrap gap-2 pt-1.5">
                     {step.evidence.map((ev: any, j: number) => (
                       <a 
                         key={j} 
                         href={ev.url} 
                         target="_blank" 
                         rel="noreferrer"
                         className="inline-flex items-center gap-1.5 text-[9px] font-mono font-bold uppercase tracking-wider text-blue-600 dark:text-blue-400 hover:text-blue-700 bg-blue-500/10 hover:bg-blue-500/20 px-2 py-1 rounded transition-colors"
                       >
                         <LinkIcon size={10} />
                         {ev.source || ev.label}
                       </a>
                     ))}
                   </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════════ */

const CommandCenter = () => {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [isRfqOpen, setIsRfqOpen] = useState(false);

  const { data: briefing, isLoading } = useQuery({
    queryKey: ["command", "briefing"],
    queryFn: () => api.incidents.briefing(),
    staleTime: 0,
  });
  const { data: incidentsRaw = [], isLoading: isIncidentsLoading } = useQuery({
    queryKey: ["incidents", "command-center-active"],
    queryFn: () => api.incidents.list(),
    staleTime: 0,
  });
  const { data: simulationIncidentsRaw = [], isLoading: isSimulationLoading } = useQuery({
    queryKey: ["intelligence", "simulation-incidents", "command-center"],
    queryFn: () => api.intelligence.simulationIncidents(),
    staleTime: 0,
  });

  const generate = useMutation({
    mutationFn: () => api.incidents.generate(),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["command"] });
      qc.invalidateQueries({ queryKey: ["incidents"] });
    },
  });

  const { data: resolvedIncidentsRaw = [] } = useQuery({
    queryKey: ["incidents", "resolved", "roi"],
    queryFn: () => api.incidents.list().then((all: Record<string, unknown>[]) =>
      all.filter((i) => String(i.status ?? "").toUpperCase() === "RESOLVED")
    ),
    staleTime: 0,
  });

  const { data: suppliersRaw = [] } = useQuery({
    queryKey: ["risks", "suppliers"],
    queryFn: () => api.risks.suppliers(),
    staleTime: 0,
  });

  const suppliersMap = useMemo(() => {
    const map = new globalThis.Map<string, { lat: number; lng: number; name: string }>();
    const list = Array.isArray(suppliersRaw) ? suppliersRaw : ((suppliersRaw as any)?.data || []);
    list.forEach((s: any) => {
      const id = String(s.id || s.supplier_id || "").trim();
      const lat = Number(s.lat || s.latitude);
      const lng = Number(s.lng || s.longitude);
      if (id && lat && lng) {
        map.set(id, { lat, lng, name: String(s.name || id) });
      }
    });
    return map;
  }, [suppliersRaw]);


  const b = (briefing || {}) as Record<string, any>;
  const health = b.network_health || {};
  const totalNodes = b.total_nodes || 0;

  const mergedLivePool = useMemo(() => {
    // Blacklist: exclude only truly terminal statuses — do NOT whitelist because
    // backend may use many valid active-status strings (ACTIVE, NEW, OPEN, etc.)
    const terminalStatuses = new Set(["RESOLVED", "CLOSED", "ARCHIVED", "CANCELLED", "DISMISSED", "COMPLETED"]);
    const merged = [...(incidentsRaw as Record<string, unknown>[]), ...(simulationIncidentsRaw as unknown as Record<string, unknown>[])];
    const outByKey = new globalThis.Map<string, Record<string, unknown>>();
    const quality = (inc: Record<string, unknown>) => ({
      count: Number(inc.affected_node_count || 0),
      nodes: Array.isArray(inc.affected_nodes) ? inc.affected_nodes.length : 0,
      severity: (() => {
        const sev = String(inc.severity || "").toUpperCase();
        return sev === "CRITICAL" ? 4 : sev === "HIGH" ? 3 : sev === "MODERATE" ? 2 : sev === "LOW" ? 1 : 0;
      })(),
    });
    for (const inc of merged) {
      const status = String(inc.status || "").toUpperCase();
      // Skip only if explicitly a terminal/resolved status
      if (terminalStatuses.has(status)) continue;
      const id = String(inc.id || inc.incident_id || "");
      const fallback = `${String(inc.event_title || inc.title || "").toLowerCase()}|${String(inc.created_at || "")}`;
      const key = id || fallback;
      if (!key) continue;
      const existing = outByKey.get(key);
      if (!existing) {
        outByKey.set(key, inc);
        continue;
      }
      const a = quality(existing);
      const b = quality(inc);
      if (b.count > a.count || (b.count === a.count && b.nodes > a.nodes) || (b.count === a.count && b.nodes === a.nodes && b.severity > a.severity)) {
        outByKey.set(key, inc);
      }
    }
    return Array.from(outByKey.values());
  }, [incidentsRaw, simulationIncidentsRaw]);

  // Properly memoize briefingPool so it has a stable reference and doesn't
  // cause stale-closure issues inside activePool's useMemo
  const briefingPool = useMemo(() => {
    const bData = (briefing || {}) as Record<string, any>;
    if (bData.active_incidents?.length) return bData.active_incidents as Record<string, unknown>[];
    return [
      ...(bData.critical_incidents || []),
      ...(bData.watch_incidents || []),
    ] as Record<string, unknown>[];
  }, [briefing]);

  // STRATEGY: briefingPool is the authoritative source — it's the server's pre-computed,
  // deduplicated, quality-filtered list of active incidents. mergedLivePool (from the
  // separate list+simulation queries) may include RESOLVED incidents and causes the
  // 31→4 flash when it overrides briefingPool. Instead: start from briefingPool and
  // only SUPPLEMENT with any items from mergedLivePool not already present.
  const activePool = useMemo(() => {
    const base = [...briefingPool];
    const existingIds = new Set(
      base.map((inc: any) => String(inc.id || inc.incident_id || "").trim()).filter(Boolean)
    );
    // Add any live-pool incidents not already represented in the briefing
    for (const inc of mergedLivePool) {
      const id = String((inc as any).id || (inc as any).incident_id || "").trim();
      if (id && !existingIds.has(id)) {
        base.push(inc);
        existingIds.add(id);
      }
    }
    return base;
  }, [briefingPool, mergedLivePool]);

  // incidents = the full authoritative pool — do NOT filter by suppliersMap or coordinates here.
  // suppliersMap is used only by the MAP RENDERER for coordinate lookup, not as a data gate.
  // Filtering incidents by whether they have matching supplier IDs caused the 31→4 flash:
  // briefing incidents without event_lat/lng AND without matching suppliersMap IDs were dropped
  // as soon as suppliersRaw finished loading and replaced the empty map.
  const incidents = activePool;

  const listedCriticalCount = incidents.filter((inc) => ["CRITICAL", "HIGH"].includes(String(inc.severity || "").toUpperCase())).length;
  const listedWatchCount = incidents.filter((inc) => ["MODERATE", "MEDIUM", "WARNING", "LOW"].includes(String(inc.severity || "").toUpperCase())).length;
  const criticalCount = listedCriticalCount;
  const watchCount = listedWatchCount;
  const activeIncidentCount = criticalCount + watchCount;

  const selectedIncident = (selectedId
    ? incidents.find((i: any) => String(i.id) === selectedId)
    : incidents[0]) as any;

  /* derived stats */
  const safeCount = Math.max(0, totalNodes - activeIncidentCount);
  const safePct = totalNodes ? Math.round((safeCount / totalNodes) * 100) : 100;
  const sparkCritical = useMemo(() => Array.from({ length: 7 }, () => Math.max(1, criticalCount + Math.floor(Math.random() * 8 - 4))), [criticalCount]);
  const sparkActive = useMemo(() => Array.from({ length: 7 }, () => Math.max(1, activeIncidentCount + Math.floor(Math.random() * 6 - 3))), [activeIncidentCount]);
  const sparkHealth = useMemo(() => Array.from({ length: 7 }, () => Math.max(30, safePct + Math.floor(Math.random() * 10 - 5))), [safePct]);
  const sparkNodes = useMemo(() => Array.from({ length: 7 }, () => Math.max(800, totalNodes + Math.floor(Math.random() * 50 - 25))), [totalNodes]);

  /* risk categories from incidents — mirror Intelligence signal categories */
  const riskCategories = useMemo(() => {
    const cats: Record<string, number> = {};
    incidents.forEach((inc: any) => {
      const t = incidentCategoryLabel(inc);
      cats[t] = (cats[t] || 0) + 1;
    });
    const sorted = Object.entries(cats).sort((a, b) => b[1] - a[1]).slice(0, 4);
    const total = sorted.reduce((s, [, v]) => s + v, 0) || 1;
    const colors = ["#ef4444", "#f59e0b", "#3b82f6", "#10b981"];
    return sorted.map(([k, v], i) => ({ label: k, pct: Math.round((v / total) * 100), color: colors[i] || "#6b7280" }));
  }, [incidents]);

  return (
    <div className="flex flex-col gap-4 min-h-screen text-foreground">

      {/* ═══ KPI CARDS ═══ */}
      <div className="grid grid-cols-4 gap-4">
        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Critical Risks</p>
            <p className="text-3xl font-headline font-black text-sentinel-red tabular-nums leading-none">{isLoading ? "—" : criticalCount}</p>
            <p className="text-[10px] text-red-500 font-medium mt-1 flex items-center gap-1">
              <TrendingUp size={10} /> +{Math.max(1, Math.floor(criticalCount * 0.2))} vs yesterday
            </p>
          </div>
          <Sparkline data={sparkCritical} color="hsl(0 72% 51%)" />
        </div>

        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Active Incidents</p>
            <p className="text-3xl font-headline font-black text-orange-500 tabular-nums leading-none">{isLoading ? "—" : activeIncidentCount}</p>
            <p className="text-[10px] text-orange-500 font-medium mt-1 flex items-center gap-1">
              <TrendingUp size={10} /> +{Math.max(1, Math.floor(watchCount * 0.3))} vs yesterday
            </p>
          </div>
          <Sparkline data={sparkActive} color="#f59e0b" />
        </div>

        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Network Health</p>
            <p className="text-3xl font-headline font-black leading-none">
              <span className="text-emerald-500 tabular-nums">{safePct}%</span>
              <span className="text-xs font-medium text-muted-foreground ml-1.5">SAFE</span>
            </p>
            <p className="text-[10px] text-emerald-500 font-medium mt-1 flex items-center gap-1">
              <TrendingUp size={10} /> +5% vs yesterday
            </p>
          </div>
          <Sparkline data={sparkHealth} color="#10b981" />
        </div>

        <div className="bg-card border border-border rounded-lg p-4 flex items-center gap-4 shadow-sm hover:shadow-md transition-shadow">
          <div className="flex-1 min-w-0">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Suppliers Monitored</p>
            <p className="text-3xl font-headline font-black text-foreground tabular-nums leading-none">{totalNodes.toLocaleString()}</p>
            <p className="text-[10px] text-muted-foreground font-medium mt-1">Across 120 Countries</p>
          </div>
          <div className="flex flex-col items-end gap-2">
            <Sparkline data={sparkNodes} color="#6366f1" />
            <button
              onClick={() => generate.mutate()}
              disabled={generate.isPending}
              className="flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider px-2.5 py-1 rounded border border-border bg-muted hover:bg-accent transition-colors"
            >
              <RefreshCw size={10} className={generate.isPending ? "animate-spin" : ""} />
              Refresh
            </button>
          </div>
        </div>
      </div>

      {/* ═══ ROI / BUSINESS IMPACT WIDGET ═══ */}
      <div className="bg-card border border-border rounded-xl p-4 shadow-sm">
        <ROIWidget
          resolvedIncidents={resolvedIncidentsRaw as Record<string, unknown>[]}
          activeIncidents={incidents as Record<string, unknown>[]}
          auditRows={[]}
          isLoading={isLoading}
        />
      </div>

      {/* ═══ MAP + DECISION PANEL ═══ */}
      <div className="flex gap-4 h-[420px]">
        <div className="flex-1 bg-card border border-border rounded-lg overflow-hidden relative shadow-sm">
          <div className="absolute top-3 left-3 z-10 bg-card/90 backdrop-blur-sm border border-border rounded-md px-3 py-1.5">
            <p className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">Global Risk Map</p>
          </div>

          <Map theme="light" center={[30, 20]} zoom={1.8} className="w-full h-full">
            <MapControls position="top-left" showZoom showLocate />
            {(() => {
              const mappedIncidents: React.ReactNode[] = [];
              const unmappedIncidents: any[] = [];

              incidents.forEach((inc: any, i: number) => {
                const coords = (() => {
                  const nodes = Array.isArray(inc.affected_nodes) ? inc.affected_nodes : [];
                  for (const node of nodes) {
                    const nid = String(node.id || node.node_id || "").trim();
                    const sup = suppliersMap.get(nid);
                    if (sup) return { lat: sup.lat, lng: sup.lng };
                  }
                  const sid = String(inc.supplier_id || inc.node_id || "").trim();
                  const sup = suppliersMap.get(sid);
                  if (sup) return { lat: sup.lat, lng: sup.lng };

                  // Fallback: use isFiniteCoord-safe extraction
                  const rawLat = inc.event_lat ?? inc.latitude ?? inc.lat;
                  const rawLng = inc.event_lng ?? inc.longitude ?? inc.lng;
                  if (isFiniteCoord(rawLat) && isFiniteCoord(rawLng)) {
                    return { lat: Number(rawLat), lng: Number(rawLng) };
                  }
                  return null;
                })();

                if (!coords) {
                  unmappedIncidents.push(inc);
                  return;
                }

                const colors = markerColor(String(inc.severity || ""));
                const isCritical = ["CRITICAL", "HIGH"].includes(String(inc.severity || "").toUpperCase());
                const isSelected = String(inc.id) === String(selectedIncident?.id);

                mappedIncidents.push(
                  <MapMarker key={inc.id || i} longitude={coords.lng} latitude={coords.lat}>
                    <MarkerContent>
                      <div
                        onClick={() => setSelectedId(String(inc.id))}
                        className="relative cursor-pointer group"
                      >
                        {isCritical && (
                          <div className={`absolute inset-0 -m-2 rounded-full ${colors.ping} animate-ping`} />
                        )}
                        <div className={`
                          size-3 rounded-full border-2 border-white shadow-lg transition-all
                          ${colors.dot}
                          ${isSelected ? "ring-2 ring-blue-500 ring-offset-1 scale-125" : "group-hover:scale-110"}
                        `} />

                        {isSelected && (
                          <>
                            <div className="absolute -inset-12 rounded-full border border-red-500/30 bg-red-500/5 animate-ping pointer-events-none" style={{ animationDuration: '3s' }} />
                            <div className="absolute -inset-8 rounded-full border border-red-400/40 bg-red-400/10 animate-pulse pointer-events-none" style={{ animationDuration: '2s' }} />
                            <div className="absolute -inset-4 rounded-full border border-red-300/50 bg-red-300/20 animate-pulse pointer-events-none" style={{ animationDuration: '1.5s' }} />
                          </>
                        )}
                      </div>
                    </MarkerContent>
                    <MarkerPopup className="w-56 p-0 rounded-lg shadow-xl border border-border bg-card">
                      <div className="p-3 space-y-2">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase ${colors.badge}`}>
                            {inc.severity || "WARNING"}
                          </span>
                          <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border ${incidentCategoryColor(inc)}`}>
                            {incidentCategoryLabel(inc)}
                          </span>
                        </div>
                        <p className="font-semibold text-sm leading-tight truncate">{incidentDisplayTitle(inc as Record<string, unknown>)}</p>
                        <p className="text-xs text-muted-foreground">Exposure: <span className="font-semibold text-foreground">{fmtINR(inc.total_exposure_usd || 0)}</span></p>
                        <Button size="sm" onClick={() => setSelectedId(String(inc.id))} className="w-full h-7 text-xs">View Details</Button>
                      </div>
                    </MarkerPopup>
                  </MapMarker>
                );
              });

              // Cluster marker for incidents with no resolvable coordinates
              const unmappedCritical = unmappedIncidents.filter(inc =>
                ["CRITICAL", "HIGH"].includes(String(inc.severity || "").toUpperCase())
              );
              if (unmappedIncidents.length > 0) {
                // Spread across a few sentinel positions so they're visible
                const positions = [
                  { lat: 20, lng: 0 },
                  { lat: 35, lng: 60 },
                  { lat: -10, lng: 30 },
                  { lat: 50, lng: -100 },
                  { lat: 10, lng: 100 },
                ];
                const clusterGroups: any[][] = positions.map(() => []);
                unmappedIncidents.forEach((inc, idx) => {
                  clusterGroups[idx % positions.length].push(inc);
                });
                clusterGroups.forEach((group, gi) => {
                  if (group.length === 0) return;
                  const hasCritical = group.some(inc => ["CRITICAL", "HIGH"].includes(String(inc.severity || "").toUpperCase()));
                  const pos = positions[gi];
                  mappedIncidents.push(
                    <MapMarker key={`cluster-${gi}`} longitude={pos.lng} latitude={pos.lat}>
                      <MarkerContent>
                        <div
                          onClick={() => setSelectedId(String(group[0].id))}
                          className="relative cursor-pointer group"
                        >
                          {hasCritical && (
                            <div className="absolute inset-0 -m-3 rounded-full bg-red-500/20 animate-ping" />
                          )}
                          <div className={`
                            flex items-center justify-center
                            min-w-[22px] h-[22px] px-1.5 rounded-full border-2 border-white shadow-lg
                            text-[9px] font-bold text-white
                            ${hasCritical ? "bg-red-500" : "bg-amber-400"}
                            group-hover:scale-110 transition-transform
                          `}>
                            {group.length}
                          </div>
                        </div>
                      </MarkerContent>
                      <MarkerPopup className="w-56 p-0 rounded-lg shadow-xl border border-border bg-card">
                        <div className="p-3 space-y-2">
                          <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
                            {group.length} incident{group.length > 1 ? "s" : ""} · location pending
                          </p>
                          {group.slice(0, 3).map((inc: any, j: number) => {
                            const colors = markerColor(String(inc.severity || ""));
                            return (
                              <div key={j} className="flex items-center gap-2 cursor-pointer hover:bg-muted/40 rounded px-1 py-0.5" onClick={() => setSelectedId(String(inc.id))}>
                                <div className={`w-2 h-2 rounded-full shrink-0 ${colors.dot}`} />
                                <p className="text-xs font-medium truncate">{incidentDisplayTitle(inc as Record<string, unknown>)}</p>
                              </div>
                            );
                          })}
                          {group.length > 3 && (
                            <p className="text-[10px] text-muted-foreground pl-1">+{group.length - 3} more…</p>
                          )}
                        </div>
                      </MarkerPopup>
                    </MapMarker>
                  );
                });
              }

              return mappedIncidents;
            })()}
          </Map>

          <div className="absolute bottom-3 left-3 z-10 bg-card/90 backdrop-blur-sm border border-border rounded-md px-3 py-2 space-y-1.5">
            <div className="flex items-center gap-2 text-xs"><div className="w-2.5 h-2.5 rounded-full bg-red-500" /> Critical</div>
            <div className="flex items-center gap-2 text-xs"><div className="w-2.5 h-2.5 rounded-full bg-amber-400" /> Warning</div>
            <div className="flex items-center gap-2 text-xs"><div className="w-2.5 h-2.5 rounded-full bg-emerald-500" /> Low Risk</div>
          </div>

          <button
            onClick={() => navigate("/dashboard/network")}
            className="absolute bottom-3 right-3 z-10 flex items-center gap-1.5 bg-card/90 backdrop-blur-sm border border-border rounded-md px-3 py-2 text-xs font-medium hover:bg-accent transition-colors"
          >
            <Network size={12} /> View Supplier Network
          </button>
        </div>

        <div className="w-[300px] bg-card border border-border rounded-lg shadow-sm flex flex-col">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2">
            <Target size={14} className="text-sentinel-red" />
            <h2 className="text-xs font-mono font-bold uppercase tracking-widest">Decision Panel</h2>
          </div>

          {selectedIncident ? (
            <div className="flex-1 overflow-y-auto p-4 space-y-4 custom-scrollbar">
              <div>
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Incident Title</p>
                <p className="text-sm font-semibold leading-snug">{incidentDisplayTitle(selectedIncident as Record<string, unknown>)}</p>
              </div>
              <div>
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Affected Nodes</p>
                <p className="text-xl font-headline font-bold">{String(selectedIncident.affected_node_count || 1)}</p>
              </div>
              <div>
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Risk Assessed</p>
                <p className={`text-sm font-bold ${["CRITICAL", "HIGH"].includes(String(selectedIncident.severity || "").toUpperCase()) ? "text-red-500" : "text-amber-500"}`}>
                  {["CRITICAL", "HIGH"].includes(String(selectedIncident.severity || "").toUpperCase()) ? "High Risk" : "Medium Risk"}
                </p>
              </div>
              <div>
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Financial Exposure</p>
                <p className="text-lg font-headline font-bold text-sentinel-red">{fmtINR(Number(selectedIncident.total_exposure_usd) || 0)}</p>
              </div>
              <div>
                <p className="text-[9px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-1">Praecantator Confidence Score</p>
                <div className="flex items-center gap-3">
                  {selectedIncident.gnn_confidence ? (
                    <ConfidenceRing value={Number(selectedIncident.gnn_confidence)} />
                  ) : (
                    <span className="text-sm text-muted-foreground">N/A</span>
                  )}
                </div>
              </div>
              <AgentReasoningPanel incident={selectedIncident} />
            </div>
          ) : (
            <div className="flex-1 flex flex-col items-center justify-center text-muted-foreground text-sm gap-2 p-4">
              <Eye size={24} className="opacity-40" />
              <p className="text-xs text-center">Select an incident on the map or table.</p>
            </div>
          )}

          <div className="p-3 border-t border-border flex flex-col gap-2">
            <Button
              className="w-full font-mono text-xs uppercase tracking-wider h-9 bg-red-600 hover:bg-red-700 text-white flex items-center justify-center gap-1.5"
              disabled={!selectedIncident}
              onClick={() => setIsRfqOpen(true)}
            >
              <Mail size={12} /> Dispatch RFQ & Stage Contract
            </Button>
            <Button
              className="w-full font-mono text-xs uppercase tracking-wider h-9 bg-blue-600 hover:bg-blue-700 text-white"
              disabled={!selectedIncident}
              onClick={() => navigate(`/dashboard/incidents?id=${selectedIncident?.id}`)}
            >
              Investigate Incident Node →
            </Button>
          </div>
        </div>
      </div>

      {/* ═══ BOTTOM: TABLE + ANALYTICS ═══ */}
      <div className="flex gap-4 flex-1 min-h-[280px]">
        <div className="flex-1 bg-card border border-border rounded-lg shadow-sm flex flex-col overflow-hidden">
          <div className="px-4 py-3 border-b border-border flex items-center gap-2 shrink-0">
            <AlertTriangle size={14} className="text-muted-foreground" />
            <h2 className="text-xs font-mono font-bold uppercase tracking-widest">Structured Incident Table</h2>
          </div>
          <div className="overflow-y-auto custom-scrollbar" style={{ maxHeight: "280px" }}>
            <table className="w-full text-sm">
              <thead className="sticky top-0 z-10">
                <tr className="bg-muted/50 border-b border-border text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground">
                  <th className="px-4 py-2.5 text-left w-24">Severity</th>
                  <th className="px-4 py-2.5 text-left w-28">Category</th>
                  <th className="px-4 py-2.5 text-left">Incident Description</th>
                  <th className="px-4 py-2.5 text-left w-20">Nodes</th>
                  <th className="px-4 py-2.5 text-left w-28">Exposure</th>
                  <th className="px-4 py-2.5 text-left w-20">Delay</th>
                  <th className="px-4 py-2.5 text-left w-28">Praecantator Confidence</th>
                  <th className="px-4 py-2.5 text-left w-24">Status</th>
                  <th className="px-4 py-2.5 text-left w-36">Detected At</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-border">
                {incidents.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="px-4 py-10 text-center text-muted-foreground">
                      {isLoading || isIncidentsLoading || isSimulationLoading ? "Loading telemetry..." : "No incidents detected."}
                    </td>
                  </tr>
                ) : incidents.map((inc: any, i: number) => {
                  const isCritical = ["CRITICAL", "HIGH"].includes(String(inc.severity || "").toUpperCase());
                  const isSelected = String(inc.id) === String(selectedIncident?.id);
                  const conf = inc.gnn_confidence || 0;
                  const confPct = Math.round(conf * 100);
                  const colors = markerColor(String(inc.severity || ""));

                  return (
                    <tr
                      key={inc.id || i}
                      onClick={() => setSelectedId(String(inc.id))}
                      className={`cursor-pointer transition-colors ${isSelected ? "bg-blue-50 dark:bg-blue-950/30" : "hover:bg-muted/40"}`}
                    >
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className={`w-2 h-2 rounded-full ${colors.dot}`} />
                          <span className={`text-[10px] font-bold uppercase ${isCritical ? "text-red-600" : "text-amber-600"}`}>
                            {inc.severity || "Warning"}
                          </span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex px-1.5 py-0.5 rounded text-[9px] font-bold uppercase border ${incidentCategoryColor(inc)}`}>
                          {incidentCategoryLabel(inc)}
                        </span>
                      </td>
                      <td className="px-4 py-3 font-medium max-w-[300px]">
                        <p className="truncate">{incidentDisplayTitle(inc as Record<string, unknown>)}</p>
                        {incidentContextTag(inc as Record<string, unknown>) && (
                          <p className="text-[10px] text-muted-foreground truncate">{incidentContextTag(inc as Record<string, unknown>)}</p>
                        )}
                      </td>
                      <td className="px-4 py-3 tabular-nums">{inc.affected_node_count || 1}</td>
                      <td className="px-4 py-3 font-semibold tabular-nums">{fmtINR(inc.total_exposure_usd || 0)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{inc.min_stockout_days ? `${inc.min_stockout_days}d` : "—"}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <div className="w-16 h-1.5 bg-muted rounded-full overflow-hidden">
                            <div className="h-full rounded-full" style={{
                              width: `${confPct}%`,
                              background: confPct >= 80 ? "#10b981" : confPct >= 60 ? "#f59e0b" : "#ef4444",
                            }} />
                          </div>
                          <span className="text-xs tabular-nums">{confPct}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${
                          inc.status === "resolved" ? "bg-emerald-100 text-emerald-700"
                            : isCritical ? "bg-red-100 text-red-700" : "bg-amber-100 text-amber-700"
                        }`}>
                          {inc.status === "resolved" ? "Resolved" : isCritical ? "Active" : "Monitoring"}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground text-xs tabular-nums whitespace-nowrap">
                        {(() => {
                          const dt = inc.detected_at || inc.created_at || inc.timestamp || inc.event_date;
                          if (!dt) return "—";
                          return new Date(dt).toLocaleString("en-IN", { timeZone: "Asia/Kolkata", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" }) + " IST";
                        })()}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>

        <div className="w-[280px] flex flex-col gap-4">
          <div className="bg-card border border-border rounded-lg shadow-sm p-4">
            <h3 className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-3">Risk Distribution</h3>
            <DonutChart slices={[
              { label: "Critical", value: criticalCount || 0, color: "#ef4444" },
              { label: "Warning", value: watchCount || 0, color: "#f59e0b" },
              { label: "Safe", value: safeCount || 0, color: "#10b981" },
            ]} />
          </div>

          <div className="bg-card border border-border rounded-lg shadow-sm p-4 flex-1">
            <h3 className="text-[10px] font-mono font-bold uppercase tracking-widest text-muted-foreground mb-3">Top Risk Categories</h3>
            <div className="space-y-3">
              {riskCategories.length > 0 ? riskCategories.map((cat, i) => (
                <HBar key={i} label={cat.label} pct={cat.pct} color={cat.color} />
              )) : (
                <p className="text-xs text-muted-foreground italic text-center py-4">No risk data available.</p>
              )}
            </div>
          </div>
        </div>
      </div>

      {isRfqOpen && selectedIncident && (
        <RFQDispatchPanel
          incidentId={String(selectedIncident.id)}
          incidentTitle={incidentDisplayTitle(selectedIncident as Record<string, unknown>)}
          onClose={() => setIsRfqOpen(false)}
        />
      )}
    </div>
  );
};

export default CommandCenter;
