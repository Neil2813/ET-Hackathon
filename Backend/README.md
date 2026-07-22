# Praecantator Backend Engine: Architecture & Technical Operations

The Praecantator Backend is the highly resilient, fully autonomous engine driving the supply chain risk intelligence platform. This document serves as an exhaustive breakdown of the architectural philosophies, multi-agent frameworks, enterprise constraint policies, and core Python modules governing the system's execution context.

Our objective with the backend is to facilitate "Zero-Touch" threat detection mapping precisely to actionable operational outcomes (e.g., dynamically rerouting logistics networks globally), securely shielded by rigorous enterprise grade access policies.

---

## 1. Architectural Foundations

![System Architecture](../diagrams/System%20Architecture.jpeg)


### 1.1 Stateless Edge / Stateful Subsystems

![Database ER](../diagrams/Database%20ER.jpeg)

The Praecantator backend is designed to operate seamlessly across high-availability multi-instance deployments. 
- **The FastAPI Edge:** The API layer is natively stateless. Identity verification, Request scoping, and Tenant extraction occur globally at the middleware dependency layer without touching the database via secure JWT propagation. All endpoints enforce strict validation using **Pydantic Schemas**, providing a bulletproof contract for the frontend.
- **The State Storage (`services.firestore_store` & `alembic`):** Core graph models and customer topology are persisted in Firestore. Relational local tracking (like local fallbacks and migrations) is systematically managed using **Alembic**, providing version-controlled, concurrent-safe database schemas (avoiding fragile startup DDL execution).
- **Background Task Delegation (`scheduler.tasks`):** Background cron jobs (e.g., `worldmonitor_cron_loop`) and model training are completely decoupled from the ASGI application boundary into a distinct **Celery Beat** worker cluster for robust, distributed asynchronous execution.
- **The Graph Representation (`models.supply_graph`):** Supply chain networks are strictly mathematical. Using underlying Graph Neural Network (GNN) principles in PyTorch (and encapsulated effectively in `CustomerSupplyGraph`), all vendor data is synthesized into isolated Spatial Quadrant nodes preventing Out of Memory (OOM) failures natively during live disaster evaluations.
- **Live ERP State Sync:** Instead of relying on static configurations from onboarding models, operational telemetry (like localized margin percent and live safety stock burn rate) dynamically injects into the execution boundary via `services/erp_sync.py` prior to invoking mathematical propagation logic.

### 1.2 The OODA Loop Pipeline

![Data Ingestion Pipeline](../diagrams/Data%20Ingestion.jpeg)

At the absolute core of the risk management platform lies the `autonomous_pipeline.py`. Relying on LangGraph for deterministic graph iterations, Praecantator translates intelligence intercepts into actionable items using the `[DETECT -> ASSESS -> DECIDE -> ACT -> AUDIT]` cognitive loop.

Instead of generating unstructured text, Large Language Models run in strict constrained schemas dictating parameters like "Re-Routed Ports", "Total USD Savings", and "Fallback Vendors."

---

## 2. Core Operational Modules

### 2.1 Multi-Agent Orchestration & Determinism

![Multi-Agent Interaction](../diagrams/Agent%20Interaction.jpeg)

Located in `agents/autonomous_pipeline.py`, the autonomous pipeline drives business logic using specialized analytical agents.

*   **Political Risk / Signal Agent (`political_risk_agent.py` & `signal_agent.py`):** Operates on the frontlines actively crawling structured and real-time feeds (GDELT geopolitical events, OPEC+ meeting bulletins, EIA/IEA reports, OFAC sanctions list, and simulated tanker AIS stream) to construct "Risk Polygons" near key shipping lanes.
*   **Strategic Reserve Optimisation Agent (`spr_optimization_agent.py`):** The AI layer that models optimal Strategic Petroleum Reserve (SPR) drawdown rates and replenishment window estimates against gross supply gap forecasts and refinery demand curves, using a trained Reinforcement Learning (PPO/SAC) policy.
*   **Disruption Scenario Modeller (`scenario_modeller.py`):** Propagates supply shocks (e.g., 40% Strait of Hormuz throughput loss) through refinery run-rates, Brent oil prices, retail fuel prices, power-sector diesel stress, and cumulative GDP trajectory impacts under testable, explicit assumptions.
*   **Assessment Agent (`assessment_agent.py`):** Synthesizes the downstream delays. Instead of making generic warnings, this step predicts structural disruption impacts and calculates Value-at-Risk (VaR) in USD for refineries.
*   **Routing Agent (`routing_agent.py`):** Acts as the logistical brain. Evaluates alternative long-haul sea corridors, comparing transit costs, days, and CO2 emissions for Suez Canal transits vs. Cape of Good Hope detours for VLCC and Suezmax tankers.
*   **LP Blend Optimizer (`energy_resilience.py`):** Uses `scipy.optimize.linprog` (HiGHS solver) to calculate the optimal crude grade recipe substitution matching refinery assay parameters exactly (API gravity, sulfur %, viscosity) when primary global grades are disrupted.
*   **RFQ & Audit Agent (`rfq_agent.py` & `audit_agent.py`):** Transitions virtual mathematical outcomes into real-world business mechanics by drafting communication quotes to backup suppliers and compiling the full trace of an executed run into an immutable PDF audit certificate.

### 2.2 Enterprise Isolation & Tenancy Governance

![Security and Governance Model](../diagrams/Security%20and%20Governance.jpeg)

The primary requirement for operating B2B Multi-Tenant platforms is preventing "data bleed." Praecantator employs pervasive isolation protocols.

*   **Authorization Substrate (`services.authorization.py`):** Introduces Role-Based Access Controls (RBAC). It evaluates internal policy schemas, confirming that users inherently contain permissions required to interact with API endpoints. If an onboarded user with `tenant_A` attempts to access logistics mapped natively for `tenant_B`, the endpoint evaluates the incoming bearer token logic, instantly dropping the request and returning `403 Forbidden`.
*   **Strict Context Boundary (`services.tenant_quota.py`):** Every API transaction is tightly bound through a contextual barrier explicitly ensuring load limits and payload separation.

### 2.3 Reliability: Idempotency & Fault Tolerance
Since Praecantator relies strictly on automated LLM execution crossing multiple network hurdles, maintaining deterministic reliability is quintessential.

*   **Idempotency Guards (`services.idempotency.py`):** Interacts flawlessly with the `action_confirmation.py` implementation. Should a pipeline break midway during the `ACT` execution stage due to SMTP failures or API quotas, the idempotency cache traps the duplicate request. It forces any execution trace to explicitly be evaluated against the operational payload structure before moving on.
*   **Compensation and State Recovery:** The `stage_policy.py` file details what must be completed before agents pass information to adjacent nodes. If a failure is found, the system is forced into a terminal fallback state, awaiting a manual replay initialization (`replay_autonomous_run()`).

### 2.4 Governance & Safety Protocols

![Execution and Governance Sequence](../diagrams/Execution%20and%20Governance.jpeg)

To maintain operator trust, the system integrates heavy procedural checkpoints for human validation.

*   **Checkpoints (`services.governance_checkpoint.py`):** If a disruption algorithm detects a multi-million dollar threat that intends to invoke radical logistical alterations, the pipeline halts immediately after the `DECIDE` stage. An internal checkpoint generates a required operational review layer. An action is permanently disabled from executing globally until an authoritative human explicitly grants permission.
*   **Reasoning Logger (`agents.reasoning_logger.py`):** No decision is permitted as a "black box." Every AI node inherently executes `log_reasoning_step()`, recording internal metadata processing details chronologically. This is fully streamed onto the front-end to act as a granular audit trail.

---

## 3. Data Integrity & Verification

### 3.1 Network Canonicalization & Validation

![Knowledge Graph Schema](../diagrams/Knowledge%20Graph%20Schema.jpeg)

To guarantee mapping consistency, generic external names are forcefully rejected unless validated by `services.master_data_validator.py`.
Users must provide legitimate geospatial constraints. If spatial bounding constraints fail, a deterministic fuzzy string-matching fallback actively searches global signal text matrices against exact entity mapping names protecting against zero-match failure latency.
Staging validation boundaries explicitly check for DUNS / LEI duplications mitigating cascading data conflicts *prior* to finalizing JSON state payloads.

### 3.2 Action Ledgering
Any modification to endpoints must leave physical traces. The `action_confirmation.py` handles tracking event sequences such as transitioning logic from `DRAFT`, validating logic passing as `SENT`, waiting for third-party inputs acknowledging the event as `DELIVERED`, and finishing as `ACKNOWLEDGED`. The separation of internal calculation states from external truth guarantees no single point of arbitrary modification.

### 3.3 Assertive Testing & Coverage
Code correctness is enforced via a comprehensive `pytest` framework, eliminating brittle manual scratch scripts. The assertive test suites (e.g., `test_worldbank.py`, `test_energy_resilience.py`) rigorously mock-test external API integrations and mathematically assert that solver constraints and type boundaries are strictly maintained before deployment.

---

## 3.4 Simulation-Derived Design Targets

All performance figures are **model outputs from `scenario_modeller.py`** under stated, auditable assumptions — not empirical measurements against historical data.

For a 40% Strait of Hormuz closure over 30 days:
- **Gross import shock:** ~0.765 MBD — computed as `import_vol × hormuz_share × loss_pct`
- **Peak Brent price:** ~$105/bbl — `baseline_brent + 15 + 25 × (loss_pct/100)`
- **Retail fuel increase:** ~₹11.25/litre — `price_spike × ₹0.45/bbl coefficient`
- **GDP growth drag:** ~−0.48 pp/month — `−0.15% per $10 Brent spike − 0.12% per 10% refinery run-rate drop`
- **Refinery floor guarded at:** 86% — explicit `refinery_operational_floor_pct` assumption

All equations are inspectable in [`services/scenario_modeller.py`](file:///d:/ET%20Gen%20AI/Solution-Challenge-2026-main/Backend/services/scenario_modeller.py). Run `POST /api/energy-resilience/simulate-scenario` to reproduce any number interactively.

---

## 4. Scaling Considerations & Phase Evolution

The architecture is currently functioning optimally within the limits of its current implementation goals. To advance the backend capabilities, developers should consider referencing:

1.  **Phase 0 (Containment):** The foundation established in strict policy execution and bypassing elimination protocols.
2.  **Phase 1 (Correctness):** Unifying dynamic spatial processing mapping explicitly bound toward `CustomerSupplyGraph`.
3.  **Phase 2 (Reliability):** Eliminating hanging transactions, wrapping states within deterministic idempotency closures.
4.  **Phase 3 (Scalability):** Future updates dictating specific Redis node queuing allocations and advanced Celery workers matching massive input spikes.
5.  **Phase 4 & 5 (Operational Trust):** Current state of the art establishing fully compliant evidence ledgers for Service Level Agreements regarding isolation validation and governance audits.

---

## 5. System Execution Examples: Geopolitical Disruption Scenario

When Houthi forces execute kinetic drone strikes on oil tankers transiting the Bab el-Mandeb strait in the Red Sea, or regional standoffs lead to a partial closure of the Strait of Hormuz, the system orchestrates a response across strategic reserves and refiners:

1. **Detection:** The `Signal Agent` detects an elevated danger level in the Strait of Hormuz based on GDELT news events and AIS tanker speed deviations. The corridor risk score increases to 0.78 (Critical).
2. **Assessment:** Within strict B2B multi-tenant data partitions, the system assesses the cascading impact on India's energy supply chain network. The gross crude oil import gap is calculated at 1.8 MBD (representing a 40% throughput drop for tankers bound for Jamnagar, Paradip, and Mumbai terminals).
3. **SPR Drawdown:** The `Strategic Reserve Optimisation Agent` (PPO policy) evaluates the 1.8 MBD supply gap against a 24-day replenishment window and recommends a daily draw rate of 0.85 MBD from the Visakhapatnam and Mangalore SPR sites to preserve critical stocks, keeping refinery runs stable and reducing power grid stress.
4. **Assay Optimization & Rerouting:** The `Routing Agent` evaluates alternative long-haul sea corridors, calculating the Suez vs. Cape of Good Hope rerouting cost and CO2 trade-offs. Simultaneously, the `LP Blend Optimizer` (`scipy.optimize.linprog`) computes a crude grade substitution recipe matching Jamnagar refinery's assay constraints (API gravity: 33.4, Sulfur: 1.5%, Viscosity: 6.2 cSt) using available sweet/sour alternatives (e.g. US Permian WTI and Iraq Basrah Medium blend fractions).
5. **Governance & RFQ:** Because the total exposure exceeds the tenant’s USD limit, a firm governance checkpoint is triggered. An audit-grade reasoning log is compiled and presented to the operator. Upon manual sign-off in the React Command Center, the system generates AI-drafted RFQ emails for alternative crude cargo purchases and commits the audit trace to the database ledger.

Praecantator’s Python ecosystem allows for uninterrupted execution scaling limitlessly depending on assigned hardware while ensuring perfect fidelity logic without compromise.
