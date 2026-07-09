from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Integer, Float, DateTime, Text, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

Base = declarative_base()

# Point to same database file as local_store
DB_PATH = Path(os.getenv("LOCAL_DB_PATH") or (Path(__file__).resolve().parents[2] / "local_fallback.db"))
DATABASE_URL = f"sqlite:///{DB_PATH.absolute().as_posix()}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class CO2RouteEvent(Base):
    __tablename__ = "co2_route_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    workflow_id = Column(String(50), nullable=True, index=True)
    mode = Column(String(30), nullable=False)
    distance_km = Column(Float, nullable=False)
    co2_emissions_metric_tons = Column(Float, nullable=False)
    carbon_cost_usd = Column(Float, nullable=False)
    esg_score = Column(Float, nullable=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SmartContractStage(Base):
    __tablename__ = "smart_contract_stages"

    contract_id = Column(String(50), primary_key=True, index=True)
    rfq_id = Column(String(50), nullable=False, index=True)
    shipper = Column(String(100), nullable=False)
    cargo_mt = Column(Float, nullable=False)
    route_mode = Column(String(30), nullable=False)
    deadline_iso = Column(String(50), nullable=False)
    status = Column(String(30), nullable=False, default="STAGED")
    blockchain_tx_hash = Column(String(66), nullable=True)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def init_orm_db() -> None:
    """Initialize ORM tables in the SQLite database."""
    Base.metadata.create_all(bind=engine)


def save_co2_route_event(workflow_id: str | None, mode: str, distance_km: float, co2_tons: float, carbon_cost: float, esg_score: float) -> None:
    session = SessionLocal()
    try:
        event = CO2RouteEvent(
            workflow_id=workflow_id,
            mode=mode,
            distance_km=distance_km,
            co2_emissions_metric_tons=co2_tons,
            carbon_cost_usd=carbon_cost,
            esg_score=esg_score
        )
        session.add(event)
        session.commit()
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.exception("Failed to save CO2 event: %s", e)
    finally:
        session.close()


def list_co2_route_events(workflow_id: str) -> list[dict]:
    session = SessionLocal()
    try:
        events = session.query(CO2RouteEvent).filter(CO2RouteEvent.workflow_id == workflow_id).all()
        return [
            {
                "mode": e.mode,
                "distance_km": e.distance_km,
                "co2_emissions_metric_tons": e.co2_emissions_metric_tons,
                "carbon_cost_usd": e.carbon_cost_usd,
                "esg_score": e.esg_score,
                "created_at": e.created_at.isoformat() if e.created_at else None
            }
            for e in events
        ]
    finally:
        session.close()


def stage_smart_contract_db(contract_id: str, rfq_id: str, shipper: str, cargo_mt: float, route_mode: str, deadline_iso: str, status: str = "STAGED") -> dict:
    session = SessionLocal()
    try:
        stage = SmartContractStage(
            contract_id=contract_id,
            rfq_id=rfq_id,
            shipper=shipper,
            cargo_mt=cargo_mt,
            route_mode=route_mode,
            deadline_iso=deadline_iso,
            status=status
        )
        session.merge(stage)
        session.commit()
        return {
            "contract_id": contract_id,
            "rfq_id": rfq_id,
            "shipper": shipper,
            "cargo_mt": cargo_mt,
            "route_mode": route_mode,
            "deadline_iso": deadline_iso,
            "status": status
        }
    finally:
        session.close()


def get_smart_contract_stage_db(contract_id: str) -> dict | None:
    session = SessionLocal()
    try:
        stage = session.query(SmartContractStage).filter(SmartContractStage.contract_id == contract_id).first()
        if not stage:
            return None
        return {
            "contract_id": stage.contract_id,
            "rfq_id": stage.rfq_id,
            "shipper": stage.shipper,
            "cargo_mt": stage.cargo_mt,
            "route_mode": stage.route_mode,
            "deadline_iso": stage.deadline_iso,
            "status": stage.status,
            "blockchain_tx_hash": stage.blockchain_tx_hash
        }
    finally:
        session.close()

