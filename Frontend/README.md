# Praecantator - Kinetic Fortress

Praecantator is a high-performance, real-time supply chain monitoring and risk mitigation dashboard. It provides a "Kinetic Fortress" for enterprise logistics, enabling operational visibility, automated workflows, and advanced risk analysis through a map-centric intelligence interface.

## 🚀 Overview

The frontend is built for speed, precision, and reliable data visualization. It integrates global risk feeds with internal logistics data to provide a unified operational nexus.

### Core Modules

- **Operational Nexus (Dashboard)**: Real-time monitoring of KPIs, active risk events, and high-priority exposure nodes.
- **Risk Map**: A globe-projected intelligence interface using @mapcn/heatmap to visualize risk density (earthquakes, geopolitics, etc.) alongside supplier locations.
- **Route Intelligence**: Dynamic corridor optimization using OSRM routing and MapCN tracking to monitor cargo in transit across Sea, Land, and Air. Includes a dedicated **Suez vs Cape Routing Engine** to assess war-risk premiums and breakeven costs dynamically.
- **LP Blend Optimizer**: Integrates with the backend `scipy` HiGHS solver to compute multi-crude substitution recipes when primary grades are disrupted.
- **Entity Manager (Onboarding)**: Facilitates staging massive CSV datasets natively against API validators identifying DUNS and geospatial overlaps securely prior to database commitment.
- **RFQ Manager**: Integrated procurement and request-for-quote handling.
- **Signal Monitor**: Real-time signal intelligence monitoring for supply chain anomalies.

## 🏛 Frontend Architecture

Praecantator utilizes a modern, decoupled architecture designed for high-frequency data updates and complex spatial visualizations.

### High-Level Component Diagram

```mermaid
graph TD
    User((User)) --> UI[React UI Layer]
    UI --> Pages[Page Modules]
    Pages --> Components[Feature Components]
    Components --> Shadcn[Radix UI / Shadcn]
    Components --> MapCN[MapCN / MapLibre]

    UI --> Hooks[Custom React Hooks]
    Hooks --> Query[TanStack Query]
    Query --> API[Axios/Fetch Client]
    API --> Backend[(Praecantator API)]

    subgraph "State Management"
        Query
        LocalState[React State/Ctx]
    end

    subgraph "Visualization Engine"
        MapLibre[MapLibre GL]
        Recharts[Recharts Analytics]
    end
```

### Architectural Decisions

- **Atomic Design Consistency**: Leveraging Shadcn UI over Radix primitives ensures a consistent design language while maintaining full accessibility (ARIA compliant).
- **Reactive Data Layer**: TanStack Query manages the transition between server-side truth and client-side UI, handling caching, revalidation, and optimistic updates.
- **Strict End-to-End Typing**: Completely eliminates `any` casts. Leverages generated TypeScript interfaces mapping exactly to Backend Pydantic models for bulletproof client-server contracts.
- **Spatial First**: Maps are treated as primary interface elements, not just overlays, utilizing MapLibre for vector tile performance.

## 🔄 Operational Workflow

Praecantator follows a rigid **OODA Loop** (Observe, Orient, Decide, Act) adapted for supply chain resilience.

### Sequence Diagram: Incident Response

```mermaid
sequenceDiagram
    participant S as Signal Monitor
    participant E as Engine (AI/Logic)
    participant M as Risk Map
    participant W as Workflow Manager
    participant U as Operator

    S->>E: Ingest Threat Signal (Seismic/Geopol)
    E->>M: Calculate Exposure Overlay
    M->>U: Alert: Supplier Node at Risk
    U->>W: Initialize Mitigation Protocol
    W->>E: Analyze Alt-Routes (OSRM)
    E->>W: Return Optimal Corridor
    W->>U: Approve Decision
    U->>S: Dispatch RFQ / Logistics Update
```

### Response Lifecycle

1.  **DETERMINATION**: Global signals (geopolitical events, natural hazards, news) are ingested via the **Signal Monitor**.
2.  **QUANTIFICATION**: The **Risk Map** and **Exposure Score** modules calculate the mathematical impact on multi-tier supplier nodes.
3.  **STRATEGY**: The **Workflow Engine** evaluates mitigation options (e.g., rerouting cargo, switching suppliers) using AI-assisted analysis.
4.  **EXECUTION**: Integrated **RFQ Manager** triggers procurement actions, while **Route Intelligence** executes corridor optimization via OSRM.
5.  **VALIDATION**: Every decision and execution record is persisted in the **Audit Log** for compliance and performance review.

## 🛠 Tech Stack

- **Core**: React 18, TypeScript 6.
- **Build Tool**: Vite 8.
- **Styling**: Tailwind CSS 4, Lucide Icons.
- **UI Components**: Shadcn UI (Radix UI primitives).
- **Mapping & Visualization**:
  - MapLibre GL
  - MapCN Components (@mapcn/logistics-network, @mapcn/heatmap, @mapcn/delivery-tracker)
  - Recharts for data analytics.
- **State Management & Data Fetching**: React Query (TanStack Query).
- **Form Handling**: React Hook Form + Zod validation.
- **Routing**: React Router DOM 6.

## 🏗 Project Structure

- `src/app/logistics`: Specialized logistics components and network data.
- `src/components/ui`: Atomic UI components (Shadcn + MapCN).
- `src/pages/dashboard`: Primary intelligence modules and views.
- `src/hooks`: Custom React hooks for dashboard data and state.
- `src/lib`: API clients and utility functions.

## 📦 Getting Started

### Prerequisites

- Node.js (Latest LTS recommended)
- npm or yarn

### Installation

1.  Install dependencies:

    ```bash
    npm install
    ```

2.  Configure environment:
    Create a `.env` file in the root:

    ```env
    VITE_API_BASE_URL=http://localhost:5000
    ```

3.  Start development server:

    ```bash
    npm run dev
    ```

## 🖼️ Application Interfaces & Outputs

This gallery showcases the main screens of the Praecantator frontend application:

### 1. Authentication & Onboarding
- **Workspace Registration**:
  ![Register](../Outputs/Register.png)
- **Login Portal**:
  ![Login](../Outputs/Login.png)

### 2. Operational Nexus (Dashboard)
The main command center summarizing KPIs, active events, and critical alerts.
![Command Center](../Outputs/Command%20Center.png)

### 3. Spatial Intelligence (Risk Maps & Globes)
- **Network View**: Interactive supplier/refinery node risk mapping.
  ![Network](../Outputs/Network.png)
- **3D Supply Chain Globe (AR View)**: 3D representation of maritime corridors.
  ![3D Globe](../Outputs/3D%20Globe.png)
- **Google Earth View**: 3D flyover of active incidents.
  ![Google Earth View](../Outputs/Google%20Earth%20View.png)

### 4. Scenario Modelling & Simulation
- **Scenario Modeller**: What-if chokepoint closure modeling.
  ![Scenario Modeller](../Outputs/Scenario%20Modeller.png)
- **Monte Carlo Simulator**: Probabilistic outcome distribution plots.
  ![Monte Carlo](../Outputs/Monte%20Carlo.png)

### 5. Energy Security & Routing
- **SPR Drawdown Scheduling**: RL daily drawdown schedules.
  ![SPR](../Outputs/SPR.png)
- **LP Blend Optimizer**: Solver output matching refinery assay properties.
  ![LP Blend](../Outputs/LP%20Blend.png)
- **Suez vs Cape Router**: Maritime corridor cost-benefit breakdown.
  ![Route Compare](../Outputs/Route%20Compare.png)
- **Exchange Ledger**: Peer-to-peer inventory sharing ledger.
  ![Exchange Ledger](../Outputs/Exchange%20Ledger.png)

### 6. Incident Analysis & Governance
- **Incident View**: Pre-analyzed incident details and OODA timeline.
  ![Incident](../Outputs/Incident.png)
- **Governance Checkpoint & RFQ**: Checkpoint approval interface and drafted backup RFQ email templates.
  ![Governance](../Outputs/Governance.png)
  ![RFQ](../Outputs/RFQ.png)
- **Settings & Conversational Copilot**: Sidebar settings and RAG-driven AI chatbot assistant.
  ![Settings & Chatbot](../Outputs/Settings%20+%20Chatbot.png)

---

## 🔒 Security & Standards

- **Strict Linting**: Configured with ESLint and TypeScript for code quality.
- **ARIA Compliance**: Implements accessible patterns for all interactive components.
- **Style Enforcement**: Uses utility-first CSS via Tailwind to avoid technical debt.
