"""initial_schema

Revision ID: d588baa6869d
Revises: 
Create Date: 2026-07-12 09:38:56.511061

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd588baa6869d'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Standard App Tables ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            user_id TEXT PRIMARY KEY,
            email TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            company_name TEXT,
            full_name TEXT DEFAULT '',
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contexts (
            user_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_events (
            workflow_id TEXT PRIMARY KEY,
            stage TEXT NOT NULL,
            confidence REAL NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rfq_events (
            rfq_id TEXT PRIMARY KEY,
            user_id TEXT,
            workflow_id TEXT,
            recipient TEXT NOT NULL,
            subject TEXT NOT NULL,
            body TEXT NOT NULL,
            status TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS rfq_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            rfq_id TEXT NOT NULL,
            direction TEXT NOT NULL,
            sender TEXT,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signals (
            signal_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            payload_hash TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS signals_archive (
            signal_id TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            archived_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            payload TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_reports (
            workflow_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_checkpoints (
            workflow_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS workflow_outcomes (
            workflow_id TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS cache_entries (
            cache_key TEXT PRIMARY KEY,
            payload_json TEXT NOT NULL,
            expires_at TEXT,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS reasoning_steps (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id TEXT NOT NULL,
            agent TEXT NOT NULL,
            stage TEXT NOT NULL,
            detail TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'success',
            output_json TEXT,
            timestamp TEXT NOT NULL,
            timestamp_ms INTEGER NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_reasoning_workflow ON reasoning_steps(workflow_id, timestamp_ms)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'DETECTED',
            severity TEXT NOT NULL DEFAULT 'LOW',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_incidents_status ON incidents(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_incidents_severity ON incidents(severity)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_incidents_tenant ON incidents(tenant_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS master_data_changes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            change_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_master_data_user ON master_data_changes(user_id, created_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS orchestration_runs (
            run_id TEXT PRIMARY KEY,
            orchestration_path TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            tenant_id TEXT NOT NULL DEFAULT 'default',
            status TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_orch_runs_tenant ON orchestration_runs(tenant_id, updated_at)")

    # ── normalized graph nodes & edges ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_nodes (
            tenant_id TEXT NOT NULL,
            node_id TEXT NOT NULL,
            node_type TEXT NOT NULL,
            name TEXT NOT NULL,
            lat REAL,
            lng REAL,
            country TEXT,
            duns_number TEXT,
            tier INTEGER,
            contract_value_usd REAL,
            daily_throughput_usd REAL,
            safety_stock_days INTEGER,
            criticality TEXT,
            single_source BOOLEAN,
            api_gravity REAL,
            sulfur_pct REAL,
            viscosity_cst REAL,
            crude_grade TEXT,
            distillation_profile_json TEXT,
            inventory_days REAL,
            privacy_band TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (tenant_id, node_id)
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS graph_edges (
            tenant_id TEXT NOT NULL,
            from_id TEXT NOT NULL,
            to_id TEXT NOT NULL,
            tier_level INTEGER,
            substitutability REAL,
            mode TEXT,
            PRIMARY KEY (tenant_id, from_id, to_id)
        )
        """
    )

    # ── Energy Resilience Exchange Ledger ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS exchange_ledger (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tenant_id TEXT NOT NULL,
            from_refinery TEXT NOT NULL,
            to_refinery TEXT NOT NULL,
            crude_grade TEXT NOT NULL,
            transfer_mbd REAL NOT NULL,
            privacy_band TEXT NOT NULL,
            reason TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )

    # ── SQLAlchemy ORM Models (CO2, Smart Contract) ──
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS co2_route_events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workflow_id VARCHAR(50),
            mode VARCHAR(30) NOT NULL,
            distance_km FLOAT NOT NULL,
            co2_emissions_metric_tons FLOAT NOT NULL,
            carbon_cost_usd FLOAT NOT NULL,
            esg_score FLOAT NOT NULL,
            created_at DATETIME
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_co2_route_events_workflow_id ON co2_route_events(workflow_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS smart_contract_stages (
            contract_id VARCHAR(50) PRIMARY KEY,
            rfq_id VARCHAR(50) NOT NULL,
            shipper VARCHAR(100) NOT NULL,
            cargo_mt FLOAT NOT NULL,
            route_mode VARCHAR(30) NOT NULL,
            deadline_iso VARCHAR(50) NOT NULL,
            status VARCHAR(30) NOT NULL,
            blockchain_tx_hash VARCHAR(66),
            updated_at DATETIME
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS ix_smart_contract_stages_contract_id ON smart_contract_stages(contract_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_smart_contract_stages_rfq_id ON smart_contract_stages(rfq_id)")


def downgrade() -> None:
    # Safe drops
    op.execute("DROP TABLE IF EXISTS users")
    op.execute("DROP TABLE IF EXISTS contexts")
    op.execute("DROP TABLE IF EXISTS workflow_events")
    op.execute("DROP TABLE IF EXISTS rfq_events")
    op.execute("DROP TABLE IF EXISTS rfq_messages")
    op.execute("DROP TABLE IF EXISTS signals")
    op.execute("DROP TABLE IF EXISTS signals_archive")
    op.execute("DROP TABLE IF EXISTS audit_log")
    op.execute("DROP TABLE IF EXISTS workflow_reports")
    op.execute("DROP TABLE IF EXISTS workflow_checkpoints")
    op.execute("DROP TABLE IF EXISTS workflow_outcomes")
    op.execute("DROP TABLE IF EXISTS cache_entries")
    op.execute("DROP TABLE IF EXISTS reasoning_steps")
    op.execute("DROP TABLE IF EXISTS incidents")
    op.execute("DROP TABLE IF EXISTS master_data_changes")
    op.execute("DROP TABLE IF EXISTS orchestration_runs")
    op.execute("DROP TABLE IF EXISTS graph_nodes")
    op.execute("DROP TABLE IF EXISTS graph_edges")
    op.execute("DROP TABLE IF EXISTS exchange_ledger")
    op.execute("DROP TABLE IF EXISTS co2_route_events")
    op.execute("DROP TABLE IF EXISTS smart_contract_stages")

