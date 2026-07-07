from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass(frozen=True)
class SPRInputs:
    national_consumption_mbd: float = 5.1
    spr_cover_days: float = 9.5
    initial_fill_pct: float = 1.0
    supply_gap_mbd: float = 1.6
    refinery_throughput_mbd: float = 4.7
    demand_shed_limit_pct: float = 0.08
    planning_horizon_days: int = 30
    replenishment_eta_days: int = 21


@dataclass(frozen=True)
class SPRDay:
    day: int
    supply_gap_mbd: float
    refinery_throughput_mbd: float
    spr_draw_mbd: float
    demand_management_mbd: float
    unmet_demand_mbd: float
    spr_inventory_mmbbl: float
    spr_cover_days_remaining: float
    stress_index: float


_cached_ppo_model = None
_cached_ppo_model_mtime = 0.0

def _get_ppo_model():
    """Cache the loaded PPO model to avoid reading from disk on every API call."""
    global _cached_ppo_model, _cached_ppo_model_mtime
    try:
        from stable_baselines3 import PPO
        from pathlib import Path
        model_path = Path(__file__).resolve().parents[1] / "ml" / "spr_ppo_weights"
        zip_path = Path(f"{model_path}.zip")
        if not zip_path.exists():
            return None
        mtime = zip_path.stat().st_mtime
        if _cached_ppo_model is None or mtime != _cached_ppo_model_mtime:
            _cached_ppo_model = PPO.load(str(model_path))
            _cached_ppo_model_mtime = mtime
        return _cached_ppo_model
    except Exception:
        return None


def optimize_spr_drawdown(inputs: SPRInputs | dict[str, Any] | None = None) -> dict[str, Any]:
    """Compute a testable SPR drawdown schedule for an import shock.

    If a trained reinforcement learning policy (PPO) is found in the ml/ directory,
    the drawdown scheduler uses its predictions to compute daily rates.
    Otherwise, it falls back to a transparent heuristic scheduler.
    """

    if isinstance(inputs, dict):
        cfg = SPRInputs(**{k: v for k, v in inputs.items() if k in SPRInputs.__annotations__})
    elif isinstance(inputs, SPRInputs):
        cfg = inputs
    else:
        cfg = SPRInputs()

    initial_inventory = cfg.national_consumption_mbd * cfg.spr_cover_days * cfg.initial_fill_pct
    inventory = initial_inventory
    max_daily_draw = max(0.0, min(cfg.supply_gap_mbd, cfg.refinery_throughput_mbd * 0.38))
    demand_shed_cap = cfg.national_consumption_mbd * cfg.demand_shed_limit_pct
    refinery_floor = cfg.refinery_throughput_mbd * 0.86
    days: list[SPRDay] = []

    # Attempt to load pre-cached PPO model
    ppo_model = _get_ppo_model()
    policy_type = "Reinforcement Learning (PPO)" if ppo_model is not None else "Deterministic Heuristics"
    if ppo_model is not None:
        import numpy as np

    for day in range(1, cfg.planning_horizon_days + 1):
        gap = max(0.0, cfg.supply_gap_mbd)
        if day >= cfg.replenishment_eta_days:
            gap *= 0.62

        target_draw = 0.0
        used_ppo = False
        
        if ppo_model is not None:
            try:
                obs = np.array([
                    inventory / initial_inventory if initial_inventory > 0 else 0.0,
                    gap / 5.0,
                    1.0 - (day / cfg.planning_horizon_days)
                ], dtype=np.float32)
                
                action, _ = ppo_model.predict(obs, deterministic=True)
                act_val = float(action[0] if hasattr(action, "__len__") else action)
                target_draw = min(max_daily_draw, act_val * gap)
                used_ppo = True
            except Exception:
                pass
                
        if not used_ppo:
            required_for_refinery_floor = max(0.0, refinery_floor - (cfg.refinery_throughput_mbd - gap))
            target_draw = min(max_daily_draw, max(required_for_refinery_floor, gap * 0.72))
            
        spr_draw = min(target_draw, inventory)
        remaining_gap = max(0.0, gap - spr_draw)
        demand_management = min(demand_shed_cap, remaining_gap)
        unmet = max(0.0, remaining_gap - demand_management)

        inventory = max(0.0, inventory - spr_draw)
        cover_days = inventory / cfg.national_consumption_mbd if cfg.national_consumption_mbd > 0 else 0.0
        throughput_after_gap = max(0.0, cfg.refinery_throughput_mbd - gap + spr_draw)
        stress = min(
            1.0,
            (unmet / max(0.1, cfg.national_consumption_mbd) * 0.55)
            + ((cfg.refinery_throughput_mbd - throughput_after_gap) / max(0.1, cfg.refinery_throughput_mbd) * 0.30)
            + ((cfg.spr_cover_days - cover_days) / max(0.1, cfg.spr_cover_days) * 0.15),
        )

        days.append(
            SPRDay(
                day=day,
                supply_gap=round(gap, 3),
                refinery_throughput_mbd=round(throughput_after_gap, 3),
                spr_draw_mbd=round(spr_draw, 3),
                demand_management_mbd=round(demand_management, 3),
                unmet_demand_mbd=round(unmet, 3),
                spr_inventory_mmbbl=round(inventory, 3),
                spr_cover_days_remaining=round(cover_days, 2),
                stress_index=round(stress, 3),
            )
        )

    exhaustion_day = next((d.day for d in days if d.spr_inventory_mmbbl <= 0.001), None)
    peak_unmet = max((d.unmet_demand_mbd for d in days), default=0.0)
    avg_stress = sum(d.stress_index for d in days) / len(days) if days else 0.0

    return {
        "inputs": asdict(cfg),
        "initial_inventory_mmbbl": round(initial_inventory, 3),
        "exhaustion_day": exhaustion_day,
        "peak_unmet_demand_mbd": round(peak_unmet, 3),
        "average_stress_index": round(avg_stress, 3),
        "schedule": [asdict(day) for day in days],
        "policy_summary": (
            f"Draw SPR via {policy_type} schedule. Bounded demand management applied, "
            "preserving inventory until alternate cargoes arrive."
        ),
    }
