from __future__ import annotations

from dataclasses import replace
from numbers import Integral
from typing import List, Tuple

from .config import (
    BASE_MPG,
    COST_PER_DRIVE,
    COST_PER_GAL,
    MIN_MPG,
    MPG_HALF_WEIGHT,
)
from .state import State
from .stop import Stop


class EnvRoute:
    """Visit any feasible subset of customers, then return to the depot.

    Actions: 0 = return to depot; 1..N = customers in supplied order.
    Returning home ends the route, including an early or empty return.
    Servicing the final customer does not end it: the return leg must still
    be executed and charged.

    Reward is actual serviced revenue minus driver and fuel costs. There is
    no completion bonus or invalid-action penalty in this economic ledger.
    """

    def __init__(self, depot: Stop, stops: List[Stop]):
        # Own fresh objects so independent solver evaluations cannot share
        # serviced flags or mutate the caller's scenario.
        self.depot = replace(depot, serviced=False)
        self.stops = [replace(s, serviced=False) for s in stops]
        self.state = State(self.depot, self.stops)

        self.route: List[str] = []
        self.route_idx: List[int] = []  # Zero-based customer indices; no depot.
        self._returned_to_depot = False

        # Keep full precision internally; round only reporting to cents.
        self.total_revenue = 0.0
        self.total_drive_cost = 0.0
        self.total_fuel_cost = 0.0
        self.total_reward = 0.0

    # ---------------- Status and actions ----------------
    def done(self) -> bool:
        """Whether this route has finished at the depot."""
        return self._returned_to_depot

    def all_serviced(self) -> bool:
        """Whether every customer was serviced, independent of termination."""
        return self.state.all_serviced()

    def action_mask(self) -> List[bool]:
        """Validity for actions 0..N, including early return at index 0.

        Finished routes have no actions. While active, the home action is
        always feasible under State's return-reservation invariant.
        """
        if self.done():
            return [False] * (len(self.stops) + 1)
        return [self.state.can_return_home()] + [
            self.state.can_service(s) for s in self.stops
        ]

    def reset(self, depot: Stop, stops: List[Stop]) -> None:
        """Create a fresh route using the supplied scenario and config limits."""
        self.__init__(depot, stops)

    @property
    def current_mpg(self) -> float:
        """Efficiency for the next leg, using the load currently on board."""
        return (
            MIN_MPG
            + (BASE_MPG - MIN_MPG)
            / (1.0 + float(self.state.total_weight) / MPG_HALF_WEIGHT)
        )

    @property
    def total_cost(self) -> float:
        """Actual driver plus fuel costs, at full precision."""
        return self.total_drive_cost + self.total_fuel_cost

    def _leg_costs(self, target: Stop) -> Tuple[float, float, float, float]:
        drive = float(self.state.drive_to(target))
        dist = float(self.state.dist_to(target))
        return drive, dist, drive * COST_PER_DRIVE, dist / self.current_mpg * COST_PER_GAL

    def get_leg_cost(self, target: Stop) -> float:
        """Estimate a leg's cost without moving, using step()'s departure load.

        This estimates cost only; action_mask() determines visit feasibility.
        """
        _, _, driver_cost, fuel_cost = self._leg_costs(target)
        return driver_cost + fuel_cost

    # ---------------- Main transition ----------------
    def step(self, idx: int) -> Tuple[float, bool]:
        """Execute one valid action and return (economic reward, terminated).

        Invalid actions raise ValueError without changing state or profit.
        Calls after a depot return raise RuntimeError. The Gym wrapper can
        handle invalid agent actions separately from the economic ledger.
        """
        if self.done():
            raise RuntimeError("The route has finished; reset before stepping again.")
        if isinstance(idx, bool) or not isinstance(idx, Integral):
            raise ValueError("Action must be an integer: 0 = depot, 1..N = customers.")

        idx = int(idx)
        if idx < 0 or idx > len(self.stops):
            raise ValueError(f"Action {idx} is outside 0..{len(self.stops)}.")

        is_depot = idx == 0
        target = self.depot if is_depot else self.stops[idx - 1]
        if not self.state.can_service(target):
            raise ValueError(f"Action {idx} is infeasible from the current state.")

        # Fuel for this leg depends on the load carried BEFORE destination
        # service: unloading or loading happens only after arrival.
        departure_weight = float(self.state.total_weight)
        mpg_actual = self.current_mpg
        drive, dist, drive_cost, fuel_cost = self._leg_costs(target)

        if is_depot:
            self.state.move_to(target)
            self._returned_to_depot = True
        else:
            self.state.move_and_service(target)
            self.route_idx.append(idx - 1)

        revenue = 0.0 if is_depot else float(target.revenue)
        reward = revenue - drive_cost - fuel_cost

        self.total_revenue += revenue
        self.total_drive_cost += drive_cost
        self.total_fuel_cost += fuel_cost
        self.total_reward += reward

        label = "DEPOT" if is_depot else target.id
        self.route.append(
            f"{str(label).rjust(5)} @ ({target.x:>5.1f}, {target.y:>5.1f}): "
            f"Drive: {drive:>7.2f} | Dist: {dist:>7.2f} | "
            f"Load Before: {departure_weight:>8.0f} | MPG: {mpg_actual:>5.2f} | "
            f"Drive Total: {self.state.total_drive:>7.2f} | "
            f"Dist Total: {self.state.total_dist:>7.2f} | "
            f"Reward: {reward:>9.2f} | Total Reward: {self.total_reward:>10.2f}"
        )

        return reward, self.done()

    # ---------------- Route reporting ----------------
    def get_route(self) -> str:
        """Human-readable log of executed legs, including the depot return."""
        return "\n".join(self.route)

    def get_route_indices(self) -> List[int]:
        """Zero-based indices of visited customers; excludes the depot."""
        return list(self.route_idx)

    def get_route_actions(self) -> List[int]:
        """Executed step() actions for replay: 1..N customers, final 0 if done."""
        actions = [i + 1 for i in self.route_idx]
        if self.done():
            actions.append(0)
        return actions

    def get_unserviced_indices(self) -> List[int]:
        """Zero-based customer indices that remain unserviced."""
        return [i for i, s in enumerate(self.stops) if not s.serviced]

    def get_route_stops(self) -> List[Stop]:
        return [self.stops[i] for i in self.route_idx]

    def get_full_route_stops(self) -> List[Stop]:
        """Depot, visited customers, and final depot when the route is finished."""
        route = [self.depot, *self.get_route_stops()]
        if self.done():
            route.append(self.depot)
        return route

    def get_result(self) -> dict:
        """Summary of a finished valid route; unfinished routes are not results."""
        if not self.done():
            raise RuntimeError("Return to the depot before requesting a route result.")
        if self.state.cur is not self.depot or not self.state.can_return_home():
            raise RuntimeError("Finished-route depot or travel invariant was violated.")

        return {
            "route_indices": self.get_route_indices(),
            "route_actions": self.get_route_actions(),
            "serviced_count": len(self.route_idx),
            "required_count": len(self.stops),
            "all_serviced": self.all_serviced(),
            "unserviced_indices": self.get_unserviced_indices(),
            "revenue": round(self.total_revenue, 2),
            "cost": round(self.total_cost, 2),
            "driver_cost": round(self.total_drive_cost, 2),
            "fuel_cost": round(self.total_fuel_cost, 2),
            "profit": self.get_total_reward(),
        }

    # ---------------- Reward reporting ----------------
    def get_total_reward(self) -> float:
        """Profit so far, or final route profit once done, rounded to cents."""
        return round(float(self.total_reward), 2)

    def get_remaining_revenue(self) -> float:
        return round(sum(s.revenue for s in self.stops if not s.serviced), 2)

    def get_potential_max_reward(self) -> float:
        """Optimistic bound on final profit, with no future operating costs.

        Uses full precision for search comparisons. Once finished, no more
        revenue can be earned on this route, so the bound is its final profit.
        """
        if self.done():
            return float(self.total_reward)
        return float(self.total_reward) + sum(
            s.revenue for s in self.stops if not s.serviced
        )
