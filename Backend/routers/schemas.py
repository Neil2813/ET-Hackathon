from __future__ import annotations

from typing import Literal, Any
from pydantic import BaseModel, Field


class Coordinates(BaseModel):
    lat: float | None = None
    lng: float | None = None
    city: str | None = None
    country: str | None = None
    country_code: str = Field(default="US", min_length=2, max_length=2)


class RouteRequest(BaseModel):
    origin: Coordinates
    destination: Coordinates
    target_currency: str = Field(default="USD", min_length=3, max_length=3)
    workflow_id: str | None = None
    commodity: str = "crude_oil"


class SPRRequest(BaseModel):
    national_consumption_mbd: float = 5.1
    spr_cover_days: float = 9.5
    initial_fill_pct: float = Field(default=1.0, ge=0.0, le=1.0)
    supply_gap_mbd: float = 1.6
    refinery_throughput_mbd: float = 4.7
    demand_shed_limit_pct: float = Field(default=0.08, ge=0.0, le=0.3)
    planning_horizon_days: int = Field(default=30, ge=1, le=180)
    replenishment_eta_days: int = Field(default=21, ge=1, le=180)


class EnergyResilienceSPRRequest(SPRRequest):
    brent_trend_pct: float = 4.5
    shipping_queue_days: float = 3.0


class CrudeCompatibilityRequest(BaseModel):
    blocked_grade: str = "iranian_light"


class WorkflowStateUpdate(BaseModel):
    stage: Literal["detect", "assess", "decide", "act", "audit"]
    confidence: float = Field(ge=0.0, le=1.0)


class RegisterRequest(BaseModel):
    email: str
    password: str = Field(min_length=8)
    company_name: str = ""
    full_name: str = ""


class LoginRequest(BaseModel):
    email: str
    password: str
    remember_me: bool = False


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class GoogleAuthRequest(BaseModel):
    id_token: str
    email: str | None = None


class OnboardingRequest(BaseModel):
    user_id: str
    company_name: str
    industry: str
    region: str
    primary_contact_name: str | None = None
    primary_contact_email: str | None = None
    company_size: str | None = None
    logistics_nodes: list[dict] = []
    suppliers: list[dict] = []
    backup_suppliers: list[dict] = []
    alert_threshold: float = 65
    transport_preferences: dict = {"sea": True, "air": True, "land": True}
    gmail_oauth_token: str | None = None
    slack_webhook: str | None = None


class SignalScoreRequest(BaseModel):
    signal_id: str
    event_type: str
    severity: float = Field(ge=0, le=10)
    location: str = ""


class IntelligenceMonteCarloRequest(BaseModel):
    signal: dict
    runs: int = Field(default=300, ge=50, le=1000)


class WorkflowAssessRequest(BaseModel):
    workflow_id: str
    event_type: str
    severity: float = Field(ge=0, le=10)
    suppliers: list[dict] = []


class WorkflowAnalyzeRequest(BaseModel):
    event: dict = {}
    suppliers: list[dict] = []
    assessment: dict | None = None
    workflow_id: str | None = None


class AgentChatRequest(BaseModel):
    message: str
    workflow_id: str | None = None
    session_id: str | None = None
    context: dict = {}


class WorkflowStartRequest(BaseModel):
    workflow_id: str
    user_id: str
    selected_signal: dict = {}
    local_currency: str = "USD"
    affected_suppliers: list[dict] = []


class WorkflowApprovalRequest(BaseModel):
    action: Literal["reroute", "backup_supplier", "both"]
    mode: Literal["sea", "air", "land", "hybrid"] | None = None


class WorkflowReportStageUpsert(BaseModel):
    workflow_id: str
    stage: Literal["detect", "assess", "decide", "act", "audit"]
    payload: dict = {}


class RFQDraftRequest(BaseModel):
    user_id: str
    recipient: str
    event_context: str
    quantities: str


class RFQSendRequest(BaseModel):
    user_id: str
    workflow_id: str
    approval_token: str
    recipient: str
    subject: str
    body: str
    approval_note: str | None = None


class TrainModelResponse(BaseModel):
    model_path: str
    rows: int


# ── Supply Chain Network Models ─────────────────────────────────────────────

class SCNetworkNode(BaseModel):
    id: str
    name: str
    type: str  # supplier_t1 | supplier_t2 | factory | warehouse | port_sea | port_air | destination
    lat: float
    lng: float
    country: str = ""
    criticality: str = "medium"  # critical | high | medium | low
    daily_throughput_usd: float = 100_000
    safety_stock_days: int = 7
    transport_modes: dict = Field(default_factory=lambda: {"sea": False, "air": False, "land": True})


class SCNetworkRoute(BaseModel):
    id: str
    from_node_id: str
    to_node_id: str
    mode: str  # sea | air | land
    transit_days: int = 7
    cost_per_unit_usd: float = 2000
    is_primary: bool = True


class SCNetworkSaveRequest(BaseModel):
    user_id: str
    nodes: list[SCNetworkNode] = []
    routes: list[SCNetworkRoute] = []
    description: str = ""


class SCNetworkMonitorRequest(BaseModel):
    user_id: str
    nodes: list[SCNetworkNode]
    events: list[dict] = []  # RiskEvent-shaped dicts from dashboard/events


class IncidentApproveRequest(BaseModel):
    action: Literal["approve", "dismiss", "override"]
    reason: str = ""


class SeaRouteRequest(BaseModel):
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float


class LandRouteRequest(BaseModel):
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float


class AirRouteRequest(BaseModel):
    from_lat: float
    from_lng: float
    to_lat: float
    to_lng: float
    from_label: str = ""
    to_label: str = ""


class RouteCostRequest(BaseModel):
    mode: str   # air | sea | land | rail | hybrid
    distance_km: float
    weight_kg: float = 5000.0    # default: 5-tonne standard supply chain unit


class CheckpointVerifyRequest(BaseModel):
    checkpoint_id: str


class CheckpointOverrideRequest(BaseModel):
    checkpoint_id: str
    reason: str = Field(min_length=3)


class FeedbackRequest(BaseModel):
    incident_id: str
    verdict: Literal["TRUE_POSITIVE", "FALSE_POSITIVE", "FALSE_NEGATIVE", "UNCERTAIN"]
    notes: str = ""
    affected_stage: str = ""


# ── Energy Resilience API Response Hardened Types ───────────────────────────

class AISForecastResponse(BaseModel):
    model: str
    lead_time_hours: int
    high_risk_corridors: list[str]
    vessels: list[dict[str, Any]]
    live_sources: dict[str, Any]
    generated_at: str


class GeopoliticalRAGResponse(BaseModel):
    vector_store: str
    documents: list[dict[str, Any]]
    risk_by_corridor: dict[str, dict[str, Any]]
    india_vulnerability: dict[str, Any]
    live_sources: dict[str, Any]
    generated_at: str


class CrudeMatchResponse(BaseModel):
    blocked_grade: dict[str, Any]
    matches: list[dict[str, Any]]
    generated_at: str


class ExchangeLedgerResponse(BaseModel):
    tenant_id: str
    participants: list[dict[str, Any]]
    recommendation: dict[str, Any]
    generated_at: str


class EnergyResilienceSPRResponse(BaseModel):
    inputs: dict[str, Any]
    initial_inventory_mmbbl: float
    exhaustion_day: int | None = None
    peak_unmet_demand_mbd: float
    average_stress_index: float
    schedule: list[dict[str, Any]]
    policy_summary: str
    agent: str
    state_space: list[str]
    action_space: list[str]
    recommended_action: dict[str, Any]
    market_inputs: dict[str, Any]


class EnergyResilienceDashboardResponse(BaseModel):
    tenant_id: str
    generated_at: str
    national_resilience_score: float
    status: str
    ais: AISForecastResponse
    spr: EnergyResilienceSPRResponse
    compatibility: CrudeMatchResponse
    rag: GeopoliticalRAGResponse
    exchange_ledger: ExchangeLedgerResponse
    esg: dict[str, Any]


class CrudeBlendRecipeResponse(BaseModel):
    blocked_grade: dict[str, Any]
    refineries_analysed: int
    feasible_count: int
    infeasible_count: int
    blend_recipes: list[dict[str, Any]]
    generated_at: str


class RouteComparisonResponse(BaseModel):
    suez_routes: list[dict[str, Any]]
    cape_routes: list[dict[str, Any]]
    corridor_risk_score: float
    war_risk_suez: float
    war_risk_cape: float
    cost_delta_usd: float
    time_delta_days: float
    risk_reduction: float
    breakeven_risk: float
    recommendation: str
    recommendation_text: str
    origin_label: str
    destination_label: str
    generated_at: str

