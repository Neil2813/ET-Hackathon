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
from routers import (
    auth, onboarding, signals, workflow, incidents,
    energy_resilience, governance, analytics, global_monitor,
    routing_utils, audit, settings, utility, copilot
)

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

_worldmonitor_task: asyncio.Task | None = None


def _bootstrap_ml_models():
    """
    Verify that committed model weight files are loadable at startup.

    We do NOT auto-retrain on a fresh deployment. Reasons:
    1. GNN weights were trained on 5 synthetic samples — the heuristic fallback
       in ml/gnn_stub.py is more defensible than a model with that little data.
    2. SPR PPO needs 50,000+ timesteps (see ml/train_spr_ppo.py) to converge —
       5,000-timestep bootstrap weights are worse than the deterministic heuristic.

    If weights are missing, the system uses its heuristic fallbacks transparently.
    Run the dedicated training scripts (ml/train_spr_ppo.py) offline, commit the
    output weights, and redeploy for the learned model path to activate.
    """
    from pathlib import Path
    logger = logging.getLogger("main.bootstrap_ml")
    backend_dir = Path(__file__).resolve().parent

    # ── Check GNN weights ────────────────────────────────────────────────────
    gnn_weights = backend_dir / "ml" / "gnn_weights.pt"
    if not gnn_weights.exists():
        try:
            from ml.gnn_model import train_gnn_from_csv
            logger.info("Triggering GNN training from CSV at startup...")
            report = train_gnn_from_csv()
            logger.info("GNN training complete: %s", report)
        except Exception as exc:
            logger.error("Failed to train GNN at startup: %s", exc)
    else:
        try:
            import torch
            state = torch.load(str(gnn_weights), weights_only=True)
            logger.info("GNN weights loaded OK (%d parameter tensors, %s bytes)",
                        len(state), gnn_weights.stat().st_size)
        except Exception as exc:
            logger.warning("GNN weights file exists but failed to load (%s). "
                           "Heuristic fallback will be used.", exc)

    # ── Check SPR PPO weights ────────────────────────────────────────────────
    spr_weights = backend_dir / "ml" / "spr_ppo_weights.zip"
    if not spr_weights.exists():
        logger.warning(
            "SPR PPO weights not found at %s. "
            "SPR drawdown will use the deterministic heuristic scheduler. "
            "To activate the PPO policy, run ml/train_spr_ppo.py and commit the output.",
            spr_weights,
        )
    else:
        logger.info("SPR PPO weights present (%s bytes). RL policy will be used.",
                    spr_weights.stat().st_size)



@app.on_event("startup")
async def _start_worldmonitor_cron():
    """Initialize Firebase Admin when configured; start worldmonitor background fetcher."""
    init_store()
    from db.orm_models import init_orm_db
    init_orm_db()
    migrate_energy_resilience_schema()
    init_firebase_admin_app()
    
    # Trigger GNN and SPR RL bootstrap training in a background thread
    import threading
    threading.Thread(target=_bootstrap_ml_models, daemon=True).start()

    if os.getenv("ENABLE_IN_PROCESS_SCHEDULERS", "false").strip().lower() in {"1", "true", "yes"}:
        try:
            start_signal_scheduler()
        except Exception as exc:
            logger.exception("signal scheduler startup failed: %s", exc)


# Mount the modular routers
app.include_router(auth.router)
app.include_router(onboarding.router)
app.include_router(signals.router)
app.include_router(workflow.router)
app.include_router(incidents.router)
app.include_router(energy_resilience.router)
app.include_router(governance.router)
app.include_router(analytics.router)
app.include_router(global_monitor.router)
app.include_router(routing_utils.router)
app.include_router(audit.router)
app.include_router(settings.router)
app.include_router(utility.router)
app.include_router(copilot.router)


# ── WebSocket Real-Time Push ──

@app.websocket("/ws/{tenant_id}")
async def websocket_endpoint(websocket: WebSocket, tenant_id: str):
    """Real-time WebSocket for incident, reasoning, and checkpoint push events."""
    try:
        await ws_handler(websocket, tenant_id)
    except Exception as exc:
        logger.warning("websocket endpoint error tenant=%s: %s", tenant_id, exc)
