from __future__ import annotations

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
    gymnasium_style = True
except ImportError:
    import gym
    from gym import spaces
    gymnasium_style = False


class SPRDrawdownEnv(gym.Env):
    """
    State representation:
      - spr_level: Current SPR storage percentage (0.0 to 1.0)
      - supply_gap: Current supply gap in mbd normalized by max capacity index (5.0 mbd)
      - remaining_time_pct: Days remaining in the planning horizon (1.0 down to 0.0)

    Action representation:
      - spr_drawdown_pct: Percentage of the current supply gap to fulfill via reserve draw (0.0 to 1.0)
    """

    def __init__(self, horizon: int = 30):
        super().__init__()
        self.horizon = horizon
        self.action_space = spaces.Box(low=0.0, high=1.0, shape=(1,), dtype=np.float32)
        self.observation_space = spaces.Box(low=0.0, high=1.0, shape=(3,), dtype=np.float32)
        self.reset()

    def reset(self, seed: int | None = None, options: dict | None = None) -> tuple[np.ndarray, dict] | np.ndarray:
        if gymnasium_style:
            super().reset(seed=seed)
        self.spr_level = 1.0  # full cover
        self.day = 1
        self.supply_gap = 1.6  # default supply gap in mbd
        obs = np.array([self.spr_level, self.supply_gap / 5.0, 1.0], dtype=np.float32)
        if gymnasium_style:
            return obs, {}
        return obs

    def step(self, action: np.ndarray | list[float] | float) -> tuple[np.ndarray, float, bool, bool, dict] | tuple[np.ndarray, float, bool, dict]:
        act_val = float(action[0] if hasattr(action, "__len__") else action)
        draw_mbd = act_val * self.supply_gap
        
        # Max capacity scale index = 50 MMBbls
        self.spr_level = max(0.0, self.spr_level - (draw_mbd / 50.0))
        
        unmet_demand = max(0.0, self.supply_gap - draw_mbd)
        reward = -(unmet_demand * 5.0) - ((1.0 - self.spr_level) * 2.0)
        
        self.day += 1
        terminated = self.day >= self.horizon or self.spr_level <= 0.0
        truncated = False
        
        obs = np.array([self.spr_level, self.supply_gap / 5.0, 1.0 - (self.day / self.horizon)], dtype=np.float32)
        
        if gymnasium_style:
            return obs, float(reward), terminated, truncated, {}
        return obs, float(reward), terminated, {}
