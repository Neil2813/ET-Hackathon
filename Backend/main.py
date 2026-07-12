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
        logger.warning(
            "GNN weights not found at %s. "
            "Graph risk propagation will use the heuristic message-passing fallback "
            "(ml/gnn_stub.py). This is intentional and auditable. "
            "To activate the learned GNN layer, train offline and commit the weights.",
            gnn_weights,
        )
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
