import sys
import os

# Set dummy environment variables to bypass Firestore calls
os.environ["ENABLE_IN_PROCESS_SCHEDULERS"] = "false"

# Add current directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

import logging
logging.basicConfig(level=logging.INFO)

from main import _bootstrap_ml_models

print("Starting bootstrap ML models pre-training...")
_bootstrap_ml_models()
print("Bootstrap finished!")

# Check if model files were created
from pathlib import Path
backend_dir = Path(__file__).resolve().parent
gnn_weights = backend_dir / "ml" / "gnn_weights.pt"
spr_weights = backend_dir / "ml" / "spr_ppo_weights.zip"

print(f"GNN weights exist: {gnn_weights.exists()} (size: {gnn_weights.stat().st_size if gnn_weights.exists() else 0} bytes)")
print(f"SPR weights exist: {spr_weights.exists()} (size: {spr_weights.stat().st_size if spr_weights.exists() else 0} bytes)")
