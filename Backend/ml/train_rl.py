from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from stable_baselines3 import PPO
from ml.spr_env import SPRDrawdownEnv

logger = logging.getLogger(__name__)
_ML_DIR = Path(__file__).resolve().parent
MODEL_PATH = _ML_DIR / "spr_ppo_weights"


def train_spr_ppo(timesteps: int = 10000) -> dict[str, Any]:
    """
    Train a PPO agent to optimize the Strategic Petroleum Reserve (SPR) drawdown strategy.
    Saves the weights to ml/spr_ppo_weights.zip.
    """
    try:
        env = SPRDrawdownEnv()
        model = PPO(
            "MlpPolicy",
            env,
            verbose=0,
            learning_rate=3e-4,
            n_steps=512,
            batch_size=64,
            n_epochs=10,
            gamma=0.99,
        )
        logger.info("Starting PPO training for SPR drawdown...")
        model.learn(total_timesteps=timesteps)
        
        # stable-baselines3 automatically appends .zip
        model.save(str(MODEL_PATH))
        logger.info("PPO training finished. Model saved to %s.zip", MODEL_PATH)
        
        return {
            "status": "trained",
            "timesteps": timesteps,
            "model_path": f"{MODEL_PATH}.zip",
        }
    except Exception as e:
        logger.exception("Failed to train SPR PPO model: %s", e)
        return {"status": "error", "error": str(e)}
