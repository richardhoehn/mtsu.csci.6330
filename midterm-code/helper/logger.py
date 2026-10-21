"""CSV logging for RL, heuristic, and exact route-search experiments."""

from __future__ import annotations

import csv
import json
from dataclasses import MISSING, asdict, dataclass, fields
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union


@dataclass(frozen=True)
class LogRow:
    # Model names can carry training configuration, e.g. RL-N8-1000000steps.
    model: str
    stops: int
    seed: int
    route: List[int]                 # Replay actions 1..N, followed by depot 0.
    reward_mean: float
    reward_max: float
    reward_process_time: float
    created_at: str

    # None means unknown/not supplied, rather than zero, false, or an empty route.
    objective: str = "max_profit"
    serviced_count: Optional[int] = None
    all_serviced: Optional[bool] = None
    unserviced_indices: Optional[List[int]] = None  # Zero-based customers.
    revenue: Optional[float] = None
    cost: Optional[float] = None    # Total actual driver + fuel cost.
    workers: Optional[int] = None
    use_branch_bound: Optional[bool] = None
    shared_bounds: Optional[bool] = None
    split_depth: Optional[int] = None
    nodes_visited: Optional[int] = None
    branches_pruned: Optional[int] = None
    tasks_submitted: Optional[int] = None
    peak_pending_tasks: Optional[int] = None
    start_method: Optional[str] = None
    complete_route_found: Optional[bool] = None
    best_complete_profit: Optional[float] = None
    best_complete_route: Optional[List[int]] = None


class Logger:
    """Append experiment rows with an explicit, versioned-by-header CSV schema.

    Use a new CSV filename for the expanded schema. Existing CSV files are
    never silently rewritten or mixed with rows having different columns.
    """

    FIELDNAMES = [field.name for field in fields(LogRow)]
    _LIST_FIELDS = {"route", "unserviced_indices", "best_complete_route"}
    _BOOL_FIELDS = {"all_serviced", "use_branch_bound", "shared_bounds", "complete_route_found"}
    _FLOAT_FIELDS = {
        "reward_mean", "reward_max", "reward_process_time",
        "revenue", "cost", "best_complete_profit",
    }

    def __init__(self, filename: Union[str, Path], *, create_dirs: bool = True) -> None:
        self.path = Path(filename)
        if create_dirs:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_header()

    def _ensure_header(self) -> None:
        if not self.path.exists() or self.path.stat().st_size == 0:
            with self.path.open("w", newline="", encoding="utf-8") as f:
                csv.DictWriter(f, fieldnames=self.FIELDNAMES).writeheader()
            return
        with self.path.open("r", newline="", encoding="utf-8") as f:
            existing_header = next(csv.reader(f), None)
        if existing_header != self.FIELDNAMES:
            raise ValueError(
                f"CSV header mismatch in {self.path}.\n"
                "The route-results logger has a different column layout. "
                "Use a new filename so previous experiment data remains intact."
            )

    @staticmethod
    def _now_iso_utc() -> str:
        return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    def log(
        self, *, model: str, stops: int, seed: int,
        route: Union[List[int], Tuple[int, ...]],
        reward_mean: float, reward_max: float,
        reward_process_time: float,
        route_result: Optional[Dict[str, Any]] = None,
        search_stats: Optional[Dict[str, Any]] = None,
        best_complete_result: Optional[Dict[str, Any]] = None,
        complete_route_found: Optional[bool] = None,
        objective: str = "max_profit",
    ) -> None:
        """Log one scenario/model summary.

        route_result describes the route stored in `route`, normally the
        maximum-profit evaluation. Completion and cost fields describe that
        route, rather than an aggregate across multiple RL evaluations.
        """
        result = route_result or {}
        stats = search_stats or {}
        if route_result is not None:
            if list(route) != list(result["route_actions"]):
                raise ValueError("route must match route_result['route_actions'].")
            if int(stops) != int(result["required_count"]):
                raise ValueError("stops must match route_result['required_count'].")

        # EnvRoute reports revenue and profit to cents. Their difference is
        # the combined operating cost, avoiding a possible one-cent mismatch
        # from adding two independently rounded cost components.
        cost = None
        if result.get("revenue") is not None and result.get("profit") is not None:
            cost = round(float(result["revenue"]) - float(result["profit"]), 2)
        elif result.get("driver_cost") is not None and result.get("fuel_cost") is not None:
            cost = round(float(result["driver_cost"]) + float(result["fuel_cost"]), 2)

        complete = best_complete_result
        if complete is not None:
            if not complete.get("all_serviced") or int(complete["required_count"]) != int(stops):
                raise ValueError("best_complete_result must service every stop in this scenario.")
            if complete_route_found is False:
                raise ValueError("A complete result cannot have complete_route_found=False.")
            complete_route_found = True

        row = LogRow(
            model=str(model), stops=int(stops), seed=int(seed),
            route=list(route),
            reward_mean=float(reward_mean), reward_max=float(reward_max),
            reward_process_time=float(reward_process_time),
            created_at=self._now_iso_utc(), objective=str(objective),
            serviced_count=result.get("serviced_count"), all_serviced=result.get("all_serviced"),
            unserviced_indices=result.get("unserviced_indices"),
            revenue=result.get("revenue"), cost=cost, workers=stats.get("workers"),
            use_branch_bound=stats.get("use_branch_bound"), shared_bounds=stats.get("shared_bounds"),
            split_depth=stats.get("split_depth"), nodes_visited=stats.get("nodes_visited"),
            branches_pruned=stats.get("branches_pruned"), tasks_submitted=stats.get("tasks_submitted"),
            peak_pending_tasks=stats.get("peak_pending_tasks"), start_method=stats.get("start_method"),
            complete_route_found=complete_route_found,
            best_complete_profit=complete["profit"] if complete is not None else None,
            best_complete_route=list(complete["route_actions"]) if complete is not None else None,
        )
        self.append(row)

    def log_solver(self, *, model: str, stops: int, seed: int, solver) -> None:
        """Copy a finished solver's results into one CSV row.

        This calls log() with values from the solver. It does not search,
        train, evaluate new routes, or change the solver's results.
        """
        if solver.process_time is None or solver.best_profit is None:
            raise ValueError("Run solver.process() before logging the solver.")
        self.log(
            model=model, stops=stops, seed=seed,
            route=solver.best_route,
            reward_mean=solver.best_reward, reward_max=solver.best_reward,
            reward_process_time=solver.process_time,
            route_result=solver.best_profit, search_stats=solver.stats,
            best_complete_result=solver.best_complete,
            complete_route_found=solver.best_complete is not None,
        )

    def append(self, row: Union[LogRow, Dict[str, Any]]) -> None:
        if isinstance(row, LogRow):
            data = asdict(row)
        else:
            data = dict(row)
            data.setdefault("created_at", self._now_iso_utc())
            data.setdefault("objective", "max_profit")
            # Optional omitted measurements are unknown. Follow declared
            # dataclass defaults so this remains correct if columns change.
            for field in fields(LogRow):
                if field.default is not MISSING:
                    data.setdefault(field.name, field.default)

        output = {}
        for key in self.FIELDNAMES:
            if key not in data:
                raise KeyError(f"Missing field {key!r} in experiment row.")
            value = data[key]
            if value is None:
                output[key] = ""
            elif key in self._LIST_FIELDS:
                output[key] = json.dumps(list(value))
            elif key in self._BOOL_FIELDS:
                if not isinstance(value, bool):
                    raise ValueError(f"{key} must be bool or None.")
                output[key] = "true" if value else "false"
            elif key in self._FLOAT_FIELDS:
                # Retain timing precision for short research benchmarks.
                output[key] = float(value)
            else:
                output[key] = value
        with self.path.open("a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=self.FIELDNAMES).writerow(output)
