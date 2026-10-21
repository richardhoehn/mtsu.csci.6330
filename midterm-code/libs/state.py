"""Truck state and feasibility checks for one depot-to-depot route."""

from __future__ import annotations

from math import hypot, isfinite
from numbers import Integral
from typing import List, Tuple

from .config import MAX_DIST, MAX_DRIVE, MAX_PALLET, MAX_WEIGHT, MIN_PER_DIST
from .stop import Stop


class State:
    """Track movement, service progress, and the load carried by one truck.

    Deliveries are loaded at the depot before departure. Pickups add load;
    deliveries remove load. Every permitted customer visit reserves enough
    driving time and distance for a direct return to the depot.

    State updates the supplied Stop objects in place so EnvRoute can observe
    their serviced flags. Callers should copy scenarios before sharing them
    between independent routes or solvers.
    """

    # Allow negligible floating-point error at a resource boundary.
    _EPSILON = 1e-9

    def __init__(self, depot: Stop, stops: List[Stop]):
        self.depot = depot
        self.stops = stops

        self.MAX_DRIVE = float(MAX_DRIVE)  # Minutes
        self.MAX_DIST = float(MAX_DIST)    # Miles
        self.MAX_WEIGHT = int(MAX_WEIGHT)  # Pounds
        self.MAX_PALLET = int(MAX_PALLET)  # Pallet positions

        self.reset_progress()

    # ---------------- Validation and resets ----------------
    def _validate_inputs(self) -> None:
        if self.depot.type != "DEPOT":
            raise ValueError("The depot must have type 'DEPOT'.")

        for stop in [self.depot, *self.stops]:
            if not (isfinite(stop.x) and isfinite(stop.y)):
                raise ValueError(f"Stop {stop.id!r} must have finite coordinates.")

            for name in ("weight", "pallet"):
                value = getattr(stop, name)
                if isinstance(value, bool) or not isinstance(value, Integral) or value < 0:
                    raise ValueError(
                        f"Stop {stop.id!r}: {name} must be a nonnegative integer."
                    )

        if self.depot.weight != 0 or self.depot.pallet != 0:
            raise ValueError("The depot must have zero weight and pallets.")

        for stop in self.stops:
            if stop.type not in ("PU", "DO"):
                raise ValueError(f"Customer {stop.id!r} must have type 'PU' or 'DO'.")

        initial_weight = sum(s.weight for s in self.stops if s.type == "DO")
        initial_pallets = sum(s.pallet for s in self.stops if s.type == "DO")

        if initial_weight > self.MAX_WEIGHT:
            raise ValueError("Initial delivery load exceeds maximum truck weight.")
        if initial_pallets > self.MAX_PALLET:
            raise ValueError("Initial delivery load exceeds maximum pallet capacity.")

    def reset_progress(self) -> None:
        """Start a fresh route at the depot with all deliveries loaded."""
        self._validate_inputs()

        self.cur = self.depot
        self.total_drive = 0.0
        self.total_dist = 0.0

        self.total_weight = sum(s.weight for s in self.stops if s.type == "DO")
        self.total_weight_do = 0
        self.total_weight_pu = 0

        self.total_pallet = sum(s.pallet for s in self.stops if s.type == "DO")
        self.total_pallet_do = 0
        self.total_pallet_pu = 0

        self.depot.serviced = False
        for stop in self.stops:
            stop.serviced = False

    # ---------------- Status and geometry ----------------
    def all_serviced(self) -> bool:
        """Whether every customer was serviced; separate from route termination."""
        return all(s.serviced for s in self.stops)

    @staticmethod
    def dist_between(a: Stop, b: Stop) -> float:
        """Straight-line distance in miles."""
        return hypot(a.x - b.x, a.y - b.y)

    def dist_to(self, target: Stop) -> float:
        return self.dist_between(self.cur, target)

    def drive_to(self, target: Stop) -> float:
        """Driving minutes at the configured constant speed."""
        return self.dist_to(target) * MIN_PER_DIST

    @property
    def dist_home(self) -> float:
        return self.dist_to(self.depot)

    @property
    def drive_home(self) -> float:
        return self.drive_to(self.depot)

    # ---------------- Remaining resources ----------------
    @property
    def drive_remaining(self) -> float:
        return max(0.0, self.MAX_DRIVE - self.total_drive)

    @property
    def dist_remaining(self) -> float:
        return max(0.0, self.MAX_DIST - self.total_dist)

    @property
    def weight_remaining(self) -> int:
        """Available payload capacity, rather than weight currently on board."""
        return max(0, self.MAX_WEIGHT - self.total_weight)

    @property
    def pallet_remaining(self) -> int:
        return max(0, self.MAX_PALLET - self.total_pallet)

    # ---------------- Feasibility ----------------
    def _travel_fits(self, additional_dist: float) -> bool:
        return (
            self.total_dist + additional_dist <= self.MAX_DIST + self._EPSILON
            and self.total_drive + additional_dist * MIN_PER_DIST
            <= self.MAX_DRIVE + self._EPSILON
        )

    def can_return_home(self) -> bool:
        """A return can be feasible even when customers remain unserviced."""
        return self._travel_fits(self.dist_home)

    def can_service(self, s: Stop) -> bool:
        if s is self.depot:
            return self.can_return_home()

        if s.type not in ("PU", "DO") or s.serviced:
            return False

        # Reserve the return leg without adding it to the actual route totals.
        visit_and_return_dist = self.dist_to(s) + self.dist_between(s, self.depot)
        if not self._travel_fits(visit_and_return_dist):
            return False

        load_change = 1 if s.type == "PU" else -1 
        new_weight = self.total_weight + load_change * int(s.weight)
        new_pallets = self.total_pallet + load_change * int(s.pallet)

        return (
            0 <= new_weight <= self.MAX_WEIGHT
            and 0 <= new_pallets <= self.MAX_PALLET
        )

    # ---------------- Apply validated transitions ----------------
    def move_to(self, s: Stop) -> Tuple[float, float, bool]:
        """Return to the depot without changing the truck's load.

        Episode termination is owned by EnvRoute, not by State.
        """
        if s is not self.depot:
            raise ValueError("move_to() is only for returning to this state's depot.")
        if not self.can_return_home():
            raise ValueError("Return to depot exceeds the remaining travel budget.")

        drive = self.drive_to(s)
        dist = self.dist_to(s)
        self.total_drive += drive
        self.total_dist += dist
        self.cur = s
        s.serviced = True
        return drive, dist, True

    def move_and_service(self, s: Stop) -> Tuple[float, float, bool]:
        """Visit a customer; reject infeasible visits before mutating state."""
        if s is self.depot or not self.can_service(s):
            raise ValueError(f"Customer {s.id!r} cannot be serviced from this state.")

        drive = self.drive_to(s)
        dist = self.dist_to(s)
        self.total_drive += drive
        self.total_dist += dist

        if s.type == "PU":
            self.total_weight += int(s.weight)
            self.total_pallet += int(s.pallet)
            self.total_weight_pu += int(s.weight)
            self.total_pallet_pu += int(s.pallet)
        else:
            self.total_weight -= int(s.weight)
            self.total_pallet -= int(s.pallet)
            self.total_weight_do += int(s.weight)
            self.total_pallet_do += int(s.pallet)

        self.cur = s
        s.serviced = True
        return drive, dist, True
