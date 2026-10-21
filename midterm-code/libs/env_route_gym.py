from __future__ import annotations

from copy import deepcopy
from math import isfinite
from numbers import Integral
from typing import Iterable

import gymnasium as gym
import numpy as np
from gymnasium import spaces

from .config import BASE_MPG
from .env_route import EnvRoute
from .scenario import Scenario
from .stop import Stop


class EnvRouteGym(gym.Env):
    metadata = {"render_modes": []}
    render_mode = None
    STOP_FEATURES = (
        "x_from_depot", "y_from_depot", "dx_from_truck", "dy_from_truck",
        "distance_to", "drive_to", "weight", "pallets", "revenue", "serviced",
        "is_depot", "is_pickup", "is_delivery", "leg_cost", "feasible",
    )
    TRUCK_FEATURES = (
        "x_from_depot", "y_from_depot", "weight", "pallets", "drive_remaining",
        "distance_remaining", "drive_home", "distance_home", "serviced_fraction",
        "remaining_revenue", "mpg", "profit_so_far",
    )

    def __init__(
        self,
        depot: Stop | None = None,
        stops: list[Stop] | None = None,
        *,
        n_stops: int | None = None,
        scenario_seeds: Iterable[int] | None = None,
        scenario_kwargs: dict | None = None,
        shuffle_stops: bool = False,
        reward_scale: float = 0.001,
        distance_scale: float = 1000.0,
        revenue_scale: float = 10_000.0,
    ):
        super().__init__()
        fixed = depot is not None or stops is not None
        if fixed and (depot is None or stops is None):
            raise ValueError("Supply both depot and stops for a fixed scenario.")
        if fixed and (n_stops is not None or scenario_seeds is not None or scenario_kwargs):
            raise ValueError("Use either a fixed scenario or generated scenarios.")
        if not fixed and (
            isinstance(n_stops, bool) or not isinstance(n_stops, Integral) or n_stops < 0
        ):
            raise ValueError("Generated scenarios need a nonnegative integer n_stops.")
        self.n_stops = len(stops) if fixed else int(n_stops)
        self.n_actions = self.n_stops + 1
        self.shuffle_stops = self._boolean(shuffle_stops, "shuffle_stops")
        for name, value in (
            ("reward_scale", reward_scale), ("distance_scale", distance_scale),
            ("revenue_scale", revenue_scale),
        ):
            if isinstance(value, bool) or not isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be finite and positive.")
        self.reward_scale = float(reward_scale)
        self.distance_scale = float(distance_scale)
        self.revenue_scale = float(revenue_scale)
        self._fixed = fixed
        self._orig_depot = deepcopy(depot)
        self._orig_stops = deepcopy(stops)
        self.scenario_kwargs = dict(scenario_kwargs or {})
        if set(self.scenario_kwargs) - {"xy_range", "skew"}:
            raise ValueError("scenario_kwargs may contain only xy_range and skew.")
        if self.scenario_kwargs.get("xy_range") is not None:
            if self.scenario_kwargs["xy_range"] < 20:
                raise ValueError("xy_range must be at least 20 for this generator.")
        if "skew" in self.scenario_kwargs and not 0 <= self.scenario_kwargs["skew"] <= 1:
            raise ValueError("skew must lie in [0, 1].")
        self.scenario_seeds = () if fixed else tuple(
            self._seed(s) for s in (
                range(501, 2001) if scenario_seeds is None else scenario_seeds
            )
        )
        if not fixed and not self.scenario_seeds:
            raise ValueError("scenario_seeds must contain at least one seed.")

        self.action_space = spaces.Discrete(self.n_actions)
        self.observation_space = spaces.Dict({
            "stops": spaces.Box(
                -np.inf, np.inf, (self.n_actions, len(self.STOP_FEATURES)), np.float32,
            ),
            "truck": spaces.Box(
                -np.inf, np.inf, (len(self.TRUCK_FEATURES),), np.float32,
            ),
        })
        self.core: EnvRoute | None = None
        self.depot: Stop | None = None
        self.stops: list[Stop] = []
        self.scenario_seed: int | None = None
        self._policy_to_core = np.arange(self.n_actions, dtype=np.int64)

    @staticmethod
    def _boolean(value, name: str) -> bool:
        if not isinstance(value, (bool, np.bool_)):
            raise ValueError(f"{name} must be a boolean.")
        return bool(value)

    @staticmethod
    def _seed(value) -> int:
        if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
            raise ValueError("Scenario seeds must be nonnegative integers.")
        return int(value)

    def _require_core(self) -> EnvRoute:
        if self.core is None:
            raise RuntimeError("Call reset() before using the environment.")
        return self.core

    def reset(self, *, seed=None, options=None):
        # seed controls the wrapper RNG, not a specific routing scenario.
        super().reset(seed=seed)
        options = dict(options or {})
        unknown = set(options) - {"scenario_seed", "shuffle_stops"}
        if unknown:
            raise ValueError(f"Unknown reset options: {sorted(unknown)}")
        shuffle = self._boolean(
            options.get("shuffle_stops", self.shuffle_stops), "shuffle_stops",
        )
        if self._fixed:
            if "scenario_seed" in options:
                raise ValueError("scenario_seed is available only in generated-scenario mode.")
            depot, stops = self._orig_depot, self._orig_stops
            scenario_seed = None
        else:
            scenario_seed = (
                self._seed(options["scenario_seed"])
                if "scenario_seed" in options
                else self.scenario_seeds[int(self.np_random.integers(len(self.scenario_seeds)))]
            )
            depot, stops = Scenario(
                n_stops=self.n_stops, seed=scenario_seed, **self.scenario_kwargs,
            ).build_random()
        # Invalid scenarios raise with their seed; never silently filter/resample.
        try:
            core = EnvRoute(depot, stops)
        except ValueError as exc:
            raise ValueError(f"Invalid scenario (seed={scenario_seed}): {exc}") from exc
        self.core = core
        self.depot, self.stops = core.depot, core.stops
        self.scenario_seed = scenario_seed
        customer_actions = (
            self.np_random.permutation(self.n_stops) + 1
            if shuffle else np.arange(1, self.n_actions)
        )
        self._policy_to_core = np.concatenate(([0], customer_actions)).astype(np.int64)
        return self._get_obs(), self._get_info()

    def get_action_mask(self) -> np.ndarray:
        """Policy-order feasibility; a live route always has home action 0."""
        core = self._require_core()
        mask = np.asarray(core.action_mask(), dtype=bool)[self._policy_to_core]
        if not core.done() and not mask[0]:
            raise RuntimeError("Core return-home invariant was violated.")
        return mask

    def action_masks(self) -> np.ndarray:
        """Callable expected by sb3-contrib, including subprocess environments."""
        return self.get_action_mask()

    def _get_obs(self) -> dict[str, np.ndarray]:
        core = self._require_core()
        state = core.state
        nodes = [core.depot, *core.stops]
        feasible = self.get_action_mask()
        rows = []
        for policy_action, core_action in enumerate(self._policy_to_core):
            s = nodes[int(core_action)]
            rows.append([
                (s.x - core.depot.x) / self.distance_scale,
                (s.y - core.depot.y) / self.distance_scale,
                (s.x - state.cur.x) / self.distance_scale,
                (s.y - state.cur.y) / self.distance_scale,
                state.dist_to(s) / self.distance_scale,
                state.drive_to(s) / state.MAX_DRIVE,
                s.weight / state.MAX_WEIGHT, s.pallet / state.MAX_PALLET,
                s.revenue / self.revenue_scale, float(s.serviced),
                float(s.type == "DEPOT"), float(s.type == "PU"), float(s.type == "DO"),
                core.get_leg_cost(s) / self.revenue_scale, float(feasible[policy_action]),
            ])
        truck = [
            (state.cur.x - core.depot.x) / self.distance_scale,
            (state.cur.y - core.depot.y) / self.distance_scale,
            state.total_weight / state.MAX_WEIGHT, state.total_pallet / state.MAX_PALLET,
            state.drive_remaining / state.MAX_DRIVE, state.dist_remaining / state.MAX_DIST,
            state.drive_home / state.MAX_DRIVE, state.dist_home / self.distance_scale,
            len(core.route_idx) / max(1, self.n_stops),
            sum(s.revenue for s in core.stops if not s.serviced) / self.revenue_scale,
            core.current_mpg / BASE_MPG, core.total_reward / self.revenue_scale,
        ]
        return {
            "stops": np.asarray(rows, dtype=np.float32),
            "truck": np.asarray(truck, dtype=np.float32),
        }

    def _get_info(self, economic_reward: float = 0.0, reason: str | None = None) -> dict:
        core = self._require_core()
        info = {
            "scenario_seed": self.scenario_seed,
            "action_mask": self.get_action_mask(),
            "policy_to_core_actions": self._policy_to_core.tolist(),
            "economic_reward": float(economic_reward), "profit": float(core.total_reward),
            "cost": float(core.total_cost), "serviced_count": len(core.route_idx),
            "all_serviced": core.all_serviced(),
        }
        if core.done():
            info["reason"] = reason
            info["result"] = core.get_result()
        return info

    def step(self, action: int):
        core = self._require_core()
        if core.done():
            raise RuntimeError("The route has finished; call reset() before stepping again.")
        # predict() on a non-vector environment may return a scalar ndarray.
        if isinstance(action, np.ndarray) and action.shape == ():
            action = action.item()
        if isinstance(action, bool) or not isinstance(action, Integral):
            raise ValueError("Action must be an integer in 0..N.")
        action = int(action)
        mask = self.get_action_mask()
        if action < 0 or action >= self.n_actions or not mask[action]:
            raise ValueError(f"Action {action} is out of range or infeasible.")
        reason = None
        if action == 0:
            reason = (
                "all_serviced" if core.all_serviced()
                else "no_feasible_customers" if not mask[1:].any()
                else "early_return"
            )
        economic_reward, terminated = core.step(int(self._policy_to_core[action]))
        return (
            self._get_obs(), float(economic_reward * self.reward_scale),
            bool(terminated), False, self._get_info(economic_reward, reason),
        )
