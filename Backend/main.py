from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from datetime import datetime, timezone
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load env: base .env
_backend_root = Path(__file__).resolve().parent
load_dotenv(dotenv_path=_backend_root / ".env", override=True)

from services.firestore_store import init_store
from services.firebase_auth import init_firebase_admin_app
from services.energy_resilience import migrate_energy_resilience_schema
from services.worldmonitor_fetcher import worldmonitor_cron_loop
from scheduler.signal_poll import start_signal_scheduler
from services.event_bus import websocket_handler as ws_handler

# Import modular routers
import routers.auth
import routers.onboarding
import routers.signals
import routers.workflow
import routers.incidents
import routers.energy_resilience
import routers.governance
import routers.analytics
import routers.global_monitor
import routers.routing_utils
import routers.audit
import routers.settings
import routers.utility

app = FastAPI(title="SupplyShield API", version="0.2.0")

_DEV_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:5174",
    "http://127.0.0.1:5174",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
]
_env_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
_CORS_ORIGINS = list(dict.fromkeys(_DEV_ORIGINS + _env_origins))
_CORS_ORIGIN_REGEX = os.getenv("CORS_ORIGIN_REGEX", "").strip() or None

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_origin_regex=_CORS_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-Id"],
    max_age=86400,
)

init_store()
migrate_energy_resilience_schema()
_worldmonitor_task: asyncio.Task | None = None


def _bootstrap_ml_models():
    """Run model bootstrapping in a background thread to avoid blocking server startup."""
    import threading
    from pathlib import Path
    
    logger = logging.getLogger("main.bootstrap_ml")
    backend_dir = Path(__file__).resolve().parent
    
    # GNN Risk Propagation Bootstrap
    gnn_weights = backend_dir / "ml" / "gnn_weights.pt"
    if not gnn_weights.exists():
        try:
            logger.info("GNN weights file not found. Bootstrapping GNN training...")
            from ml.gnn_model import train_gnn_model
            from ml.gnn_stub import build_graph_from_dataset
            from scheduler.tasks import _dataset_suppliers
            
            graph = build_graph_from_dataset(_dataset_suppliers())
            report = train_gnn_model(graph, epochs=30)
            logger.info("GNN bootstrap completed: %s", report)
        except Exception as e:
            logger.exception("Failed to bootstrap GNN: %s", e)
            
    # SPR Drawdown PPO Policy Bootstrap
    spr_weights = backend_dir / "ml" / "spr_ppo_weights.zip"
    if not spr_weights.exists():
        try:
            logger.info("SPR PPO weights file not found. Bootstrapping PPO training...")
            from ml.train_rl import train_spr_ppo
            
            report = train_spr_ppo(timesteps=5000)
            logger.info("SPR PPO bootstrap completed: %s", report)
        except Exception as e:
            logger.exception("Failed to bootstrap SPR PPO: %s", e)


@app.on_event("startup")
async def _start_worldmonitor_cron():
    """Initialize Firebase Admin when configured; start worldmonitor background fetcher."""
    init_firebase_admin_app()
    
    # Trigger GNN and SPR RL bootstrap training in a background thread
    import threading
    threading.Thread(target=_bootstrap_ml_models, daemon=True).start()

    if os.getenv("ENABLE_IN_PROCESS_SCHEDULERS", "true").strip().lower() in {"1", "true", "yes"}:
        try:
            start_signal_scheduler()
        except Exception as exc:
            logger.exception("signal scheduler startup failed: %s", exc)
        global _worldmonitor_task
        _worldmonitor_task = asyncio.create_task(worldmonitor_cron_loop())
        def _log_task_result(task: asyncio.Task) -> None:
            try:
                _ = task.result()
            except Exception as task_exc:
                logger.exception("worldmonitor_cron_loop crashed: %s", task_exc)
        _worldmonitor_task.add_done_callback(_log_task_result)


# Mount the modular routers
app.include_router(routers.auth.router)
app.include_router(routers.onboarding.router)
app.include_router(routers.signals.router)
app.include_router(routers.workflow.router)
app.include_router(routers.incidents.router)
app.include_router(routers.energy_resilience.router)
app.include_router(routers.governance.router)
app.include_router(routers.analytics.router)
app.include_router(routers.global_monitor.router)
app.include_router(routers.routing_utils.router)
app.include_router(routers.audit.router)
app.include_router(routers.settings.router)
app.include_router(routers.utility.router)


# ── WebSocket Real-Time Push ──

@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str):
    """Real-time WebSocket for incident, reasoning, and checkpoint push events."""
    try:
        await ws_handler(websocket, tenant_id)
    except Exception as exc:
        logger.warning("websocket endpoint error tenant=%s: %s", tenant_id, exc)
