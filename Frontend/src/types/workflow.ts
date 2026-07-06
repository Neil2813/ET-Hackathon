/**
 * Shared workflow / risk visualization types (see claude.md).
 */

export type WorkflowStage = "DETECT" | "ASSESS" | "DECIDE" | "ACT" | "AUDIT";

export type WorkflowRunStatus = "running" | "waiting_approval" | "complete" | "error";

export interface WorkflowState {
  workflow_id: string;
  stage: WorkflowStage;
  status: WorkflowRunStatus;
  created_at: string;
  updated_at: string;
}

export interface ReasoningStep {
  agent: string;
  stage: string;
  detail: string;
  status: "success" | "error" | "fallback";
  timestamp: string;
  timestamp_ms: number;
  output?: Record<string, unknown>;
}

/** Riskwise-style country row; map intensity via averageRiskToScore. */
export interface HeatmapData {
  country: string;
  average_risk: string;
  breakdown: string;
}

export interface Signal {
  signal_id: string;
  title: string;
  event_type: string;
  severity: number;
  location: string;
  lat: number;
  lng: number;
  source: string;
  source_url: string;
  source_type: "government" | "news" | "geopolitical" | "regional";
  verified: boolean;
  corroborated_by: string[];
  corroboration_count: number;
  detected_at: string;
  relevance_score: number;
}

export interface SupplierNode {
  supplier_id: string;
  name: string;
  city: string;
  country: string;
  tier: 1 | 2 | 3;
  transport_mode: "sea" | "tanker" | "pipeline" | "mixed";
  category: string;
  node_role?: "crude_producer" | "refinery" | "spr_terminal";
  crude_grade?: string;
  api_gravity?: number;
  sulfur_pct?: number;
  refinery_profile?: string[];
  compatible_refineries?: string[];
  throughput_mbd?: number;
  import_share_pct?: number;
  lat: number;
  lng: number;
  exposure_score: number;
  exposure_label: "Low Risk" | "Medium Risk" | "High Risk";
  risk_points: 1 | 3 | 5;
  is_backup: boolean;
  email?: string;
}

export interface RouteOption {
  mode: "sea" | "tanker_vlcc" | "tanker_suezmax";
  engine?: "haversine" | "maritime_tanker";
  distance_km: number;
  transit_days?: number;
  cost_usd: number;
  cost_local?: number;
  currency?: string;
  lane?: string;
  chokepoint?: string;
  capacity_mmbbl?: number;
  draft_m?: number;
  charter_rate_usd_day?: number;
  restrictions?: string[];
  selected: boolean;
  recommended: boolean;
}

export interface AssessmentCard {
  workflow_id: string;
  affected_suppliers: SupplierNode[];
  exposure_usd: number;
  exposure_local?: number;
  exposure_currency?: string;
  days_at_risk: number;
  confidence: number;
  analysis_summary: string;
  inflation_risk?: string;
  spr_cover_days?: number;
  domestic_fuel_price_delta_pct?: number;
  power_sector_stress?: "LOW" | "MODERATE" | "HIGH" | "SEVERE";
  currency_risk_index: number;
}

export interface AuditCertificate {
  workflow_id: string;
  generated_at: string;
  response_time_seconds: number;
  stages_completed: string[];
  compliance_frameworks: string[];
  pdf_url?: string;
}

export interface AgentRoutePlan {
  original_query: string;
  needs_scheduler: boolean;
  requested_agents: string[];
  use_assistant_only: boolean;
  needs_report: boolean;
}

export interface AgentChatResult {
  conversation_id: string;
  sequence: string[];
  route: AgentRoutePlan | Record<string, unknown>;
  supervisor?: Record<string, unknown>;
  outputs: Record<string, unknown> & {
    agent_statuses?: Record<string, "Idle" | "Running" | "Completed" | "Failed">;
    shared_state?: Record<string, unknown>;
    audit_log?: Array<Record<string, unknown>>;
  };
  text: string;
}
