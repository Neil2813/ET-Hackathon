from __future__ import annotations

import os
import sys
import numpy as np
import gymnasium as gym
from gymnasium import spaces
from pathlib import Path
from stable_baselines3 import PPO

# Set paths
ML_DIR = Path(__file__).resolve().parent
WEIGHTS_PATH = ML_DIR / "spr_ppo_weights"


class SPREnv(gym.Env):
    """
    Gymnasium environment simulating India's Strategic Petroleum Reserve (SPR) drawdown.
    State representation:
      0: Current SPR inventory ratio (inventory / initial_inventory) [0, 1]
      1: Supply gap ratio (gap_mbd / max_refinery_throughput_mbd) [0, 1]
      2: Remaining time ratio (days_remaining / planning_horizon) [0, 1]

    Action:
      0: Drawdown fraction [0, 1] of maximum daily drawdown capacity.
    """
    metadata = {"render_modes": ["human"]}

    def __init__(self):
        super().__init__()
        # Continuous observation space: [inventory_ratio, gap_ratio, remaining_time_ratio]
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(3,), dtype=np.float32
        )
        # Continuous action space: [drawdown_fraction]
        self.action_space = spaces.Box(
            low=0.0, high=1.0, shape=(1,), dtype=np.float32
        )

        # Baseline parameters matching agent definitions
        self.national_consumption = 5.1
        self.refinery_throughput = 4.7
        self.spr_cover_days = 9.5
        self.planning_horizon = 30
        self.replenishment_eta = 21

        # Max daily draw: capped at supply gap or 38% of refinery throughput
        self.max_daily_draw = 1.786  # 4.7 * 0.38
        self.demand_shed_cap = 5.1 * 0.08  # 8% max demand shed

    def reset(self, seed=None, options=None):
        super().reset(seed=seed)
        
        # Initial state setup
        self.initial_inventory = self.national_consumption * self.spr_cover_days
        self.inventory = self.initial_inventory
        self.day = 0
        
        # Randomize supply gap for robust policy training [1.0, 2.5] mbd
        self.supply_gap = self.np_random.uniform(1.0, 2.5)
        
        obs = self._get_obs()
        return obs, {}

    def _get_obs(self):
        inv_ratio = self.inventory / self.initial_inventory if self.initial_inventory > 0 else 0.0
        gap_ratio = self.supply_gap / 5.0
        time_ratio = 1.0 - (self.day / self.planning_horizon)
        return np.array([inv_ratio, gap_ratio, time_ratio], dtype=np.float32)

    def step(self, action):
        self.day += 1
        
        # Supply gap reduces after replenishment ETA
        gap = self.supply_gap
        if self.day >= self.replenishment_eta:
            gap *= 0.62

        draw_fraction = float(action[0])
        target_draw = min(self.max_daily_draw, draw_fraction * gap)
        spr_draw = min(target_draw, self.inventory)
        
        remaining_gap = max(0.0, gap - spr_draw)
        demand_management = min(self.demand_shed_cap, remaining_gap)
        unmet = max(0.0, remaining_gap - demand_management)
        
        # Update state
        self.inventory = max(0.0, self.inventory - spr_draw)
        
        # Stress Index Calculation (lower is better, penalty terms)
        cover_days = self.inventory / self.national_consumption if self.national_consumption > 0 else 0.0
        throughput_after_gap = max(0.0, self.refinery_throughput - gap + spr_draw)
        
        stress = (
            (unmet / self.national_consumption * 0.55)
            + ((self.refinery_throughput - throughput_after_gap) / self.refinery_throughput * 0.30)
            + ((self.spr_cover_days - cover_days) / self.spr_cover_days * 0.15)
        )
        
        # Reward formulation: negative sum of stress index and unmet demand penalties
        reward = -(stress * 10.0 + unmet * 12.0)
        
        # Check if horizon reached
        terminated = self.day >= self.planning_horizon
        truncated = False
        
        obs = self._get_obs()
        return obs, reward, terminated, truncated, {}


def train_policy():
    print("Initializing SPR drawdown training environment...")
    env = SPREnv()
    
    # Define PPO model (MLP policy for low-dimensional vector inputs)
    model = PPO(
        "MlpPolicy",
        env,
        learning_rate=3e-4,
        n_steps=2048,
        batch_size=64,
        n_epochs=10,
        gamma=0.99,
        verbose=1,
        seed=42
    )
    
    timesteps = 50000
    print(f"Training PPO agent for {timesteps} timesteps...")
    model.learn(total_timesteps=timesteps)
    
    print(f"Saving trained PPO weights to {WEIGHTS_PATH}.zip")
    model.save(str(WEIGHTS_PATH))
    print("Policy training and export completed successfully.")


if __name__ == "__main__":
    train_policy()
