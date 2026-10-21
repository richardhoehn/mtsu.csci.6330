"""Exact sequential search over feasible partial and complete truck routes.

FindBest defaults to exhaustive search, providing a baseline for the CPU
parallel implementation. Set use_branch_bound=True to measure sequential
branch-and-bound with the same bounds used by the cooperative solver.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import isclose, isfinite
from numbers import Integral
from time import perf_counter
from typing import Callable, Iterator, List, Optional, TYPE_CHECKING

from libs.config import BASE_MPG, COST_PER_DRIVE, COST_PER_GAL, MIN_MPG, MPG_HALF_WEIGHT, MIN_PER_DIST
from libs.env_route import EnvRoute
from libs.stop import Stop

if TYPE_CHECKING:
    from rich.progress import Progress


_EPSILON = 1e-9


@dataclass(frozen=True)
class _Node:
    current: int
    remaining: int             # Bit i denotes unvisited customer i.
    distance: float
    drive: float
    weight: int
    pallets: int
    profit: float              # Before charging the final home leg.
    path: tuple[int, ...]      # Customer actions 1..N; excludes depot.


@dataclass(frozen=True)
class _Solution:
    profit: float
    actions: tuple[int, ...]   # Includes final action 0.


@dataclass
class _Report:
    best_profit: Optional[_Solution] = None
    best_complete: Optional[_Solution] = None
    nodes_visited: int = 0
    branches_pruned: int = 0

    def merge(self, other: _Report) -> None:
        if _better(other.best_profit, self.best_profit):
            self.best_profit = other.best_profit
        if _better(other.best_complete, self.best_complete):
            self.best_complete = other.best_complete
        self.nodes_visited += other.nodes_visited
        self.branches_pruned += other.branches_pruned


def _better(candidate: Optional[_Solution], incumbent: Optional[_Solution]) -> bool:
    if candidate is None:
        return False
    if incumbent is None:
        return True
    if candidate.profit > incumbent.profit + _EPSILON:
        return True
    # Deterministic tie-breaking makes worker completion order irrelevant.
    return (
        abs(candidate.profit - incumbent.profit) <= _EPSILON
        and candidate.actions < incumbent.actions
    )


class _Problem:
    """Precomputed numeric search data; validated against the core environment.

    This avoids copying EnvRoute and formatting logs at every search node.
    Finished winning routes are replayed through EnvRoute for reporting.
    """

    def __init__(self, depot: Stop, stops: List[Stop]):
        env = EnvRoute(depot, stops)
        state = env.state
        self.n = len(stops)
        self.max_drive = state.MAX_DRIVE
        self.max_dist = state.MAX_DIST
        self.max_weight = state.MAX_WEIGHT
        self.max_pallet = state.MAX_PALLET
        self.revenue = [float(s.revenue) for s in env.stops]
        self.weight_delta = [int(s.weight) * (1 if s.type == "PU" else -1) for s in env.stops]
        self.pallet_delta = [int(s.pallet) * (1 if s.type == "PU" else -1) for s in env.stops]
        nodes = [env.depot, *env.stops]
        self.dist = [[state.dist_between(a, b) for b in nodes] for a in nodes]
        self.root = _Node(0, (1 << self.n) - 1, 0.0, 0.0, state.total_weight, state.total_pallet, 0.0, ())

        # Bounds require nonnegative revenue/costs and MPG <= BASE_MPG.
        if not (
            isfinite(BASE_MPG) and isfinite(MIN_MPG)
            and 0 < MIN_MPG <= BASE_MPG
            and isfinite(MPG_HALF_WEIGHT) and MPG_HALF_WEIGHT > 0
            and isfinite(COST_PER_DRIVE) and COST_PER_DRIVE >= 0
            and isfinite(COST_PER_GAL) and COST_PER_GAL >= 0
            and isfinite(MIN_PER_DIST) and MIN_PER_DIST > 0
            and all(isfinite(r) and r >= 0 for r in self.revenue)
        ):
            raise ValueError("Search requires finite nonnegative revenues/costs and valid MPG/speed settings.")
        self.min_cost_per_mile = MIN_PER_DIST * COST_PER_DRIVE + COST_PER_GAL / BASE_MPG

    def leg_reward(self, distance: float, weight: int, revenue: float = 0.0) -> float:
        mpg = MIN_MPG + (BASE_MPG - MIN_MPG) / (1.0 + float(weight) / MPG_HALF_WEIGHT)
        return revenue - distance * MIN_PER_DIST * COST_PER_DRIVE - distance / mpg * COST_PER_GAL

    def travel_fits(self, node: _Node, additional_distance: float) -> bool:
        return (
            node.distance + additional_distance <= self.max_dist + _EPSILON
            and node.drive + additional_distance * MIN_PER_DIST <= self.max_drive + _EPSILON
        )

    def return_solution(self, node: _Node) -> _Solution:
        return _Solution(
            node.profit + self.leg_reward(self.dist[node.current][0], node.weight),
            node.path + (0,),
        )

    def children(self, node: _Node) -> list[_Node]:
        result = []
        bits = node.remaining
        while bits:
            bit = bits & -bits
            bits ^= bit
            i = bit.bit_length() - 1
            action = i + 1
            distance = self.dist[node.current][action]
            if not self.travel_fits(node, distance + self.dist[action][0]):
                continue
            weight = node.weight + self.weight_delta[i]
            pallets = node.pallets + self.pallet_delta[i]
            if not (0 <= weight <= self.max_weight and 0 <= pallets <= self.max_pallet):
                continue
            result.append(_Node(
                action, node.remaining ^ bit,
                node.distance + distance, node.drive + distance * MIN_PER_DIST,
                weight, pallets,
                node.profit + self.leg_reward(distance, node.weight, self.revenue[i]),
                node.path + (action,),
            ))
        # Explore promising finished routes first; this only changes order.
        result.sort(key=lambda child: (-self.return_solution(child).profit, child.path))
        return result

    def mst_distance(self, node: _Node) -> float:
        """Minimum spanning tree: a lower bound on a complete continuation."""
        ids = list(dict.fromkeys([node.current, 0, *[
            i + 1 for i in range(self.n) if node.remaining & (1 << i)
        ]]))
        if len(ids) <= 1:
            return 0.0
        pending = {i: self.dist[ids[0]][i] for i in ids[1:]}
        total = 0.0
        while pending:
            nearest = min(pending, key=pending.get)
            total += pending.pop(nearest)
            for i in pending:
                pending[i] = min(pending[i], self.dist[nearest][i])
        return total


class _Search:
    def __init__(self, problem: _Problem, use_branch_bound: bool, shared=None, callback: Optional[Callable] = None):
        self.problem = problem
        self.use_branch_bound = use_branch_bound
        self.shared = shared
        self.callback = callback
        self.report = _Report()
        self._global_profit = float("-inf")
        self._global_complete = float("-inf")

    def record(self, node: _Node) -> None:
        solution = self.problem.return_solution(node)
        changed = False
        if _better(solution, self.report.best_profit):
            self.report.best_profit = solution
            changed = True
        if node.remaining == 0 and _better(solution, self.report.best_complete):
            self.report.best_complete = solution
            changed = True
        self.report.nodes_visited += 1
        if self.shared is not None:
            if changed:
                self.shared.publish(
                    self.report.best_profit.profit,
                    self.report.best_complete.profit if self.report.best_complete else float("-inf"),
                )
            # Stale lower incumbents only reduce pruning; they cannot harm correctness.
            if self.report.nodes_visited == 1 or self.report.nodes_visited % 64 == 0:
                self._global_profit, self._global_complete = self.shared.read()
        if self.callback is not None and self.report.nodes_visited % 2048 == 0:
            self.callback(self.report)

    def prune(self, node: _Node) -> bool:
        if not self.use_branch_bound or node.remaining == 0:
            return False
        p = self.problem
        reachable_revenue = 0.0
        complete_possible = True
        for i in range(p.n):
            if node.remaining & (1 << i):
                # Any continuation visiting i is at least as long as the direct
                # current->i->home path (triangle inequality).
                if p.travel_fits(node, p.dist[node.current][i + 1] + p.dist[i + 1][0]):
                    reachable_revenue += p.revenue[i]
                else:
                    complete_possible = False

        profit_bound = node.profit + reachable_revenue - p.dist[node.current][0] * p.min_cost_per_mile
        profit_incumbent = max(
            self.report.best_profit.profit if self.report.best_profit else float("-inf"),
            self._global_profit,
        )
        can_improve_profit = profit_bound >= profit_incumbent - _EPSILON

        complete_incumbent = max(
            self.report.best_complete.profit if self.report.best_complete else float("-inf"),
            self._global_complete,
        )
        can_improve_complete = False
        if complete_possible:
            mst = p.mst_distance(node)
            if p.travel_fits(node, mst):
                complete_bound = node.profit + reachable_revenue - mst * p.min_cost_per_mile
                can_improve_complete = complete_bound >= complete_incumbent - _EPSILON

        # Two objectives: a branch may be pruned only when it cannot improve
        # either the maximum-profit route or the best complete route.
        if not can_improve_profit and not can_improve_complete:
            self.report.branches_pruned += 1
            return True
        return False

    def visit(self, node: _Node) -> None:
        self.record(node)
        if not self.prune(node):
            for child in self.problem.children(node):
                self.visit(child)

    def frontier(self, node: _Node, depth: int) -> Iterator[_Node]:
        """Score shallow prefixes once and yield disjoint worker subtrees."""
        if depth == 0:
            yield node
            return
        self.record(node)
        if not self.prune(node):
            for child in self.problem.children(node):
                yield from self.frontier(child, depth - 1)


class FindBest:
    def __init__(self, depot: Stop, stops: List[Stop], verbose: bool = False, *, use_branch_bound: bool = False):
        self.depot = depot
        self.stops = stops
        self.verbose = verbose
        self.use_branch_bound = bool(use_branch_bound)
        self._clear_results()

    def _clear_results(self) -> None:
        self.best_route: Optional[List[int]] = None
        self.best_reward = float("-inf")
        self.best_profit: Optional[dict] = None
        self.best_complete: Optional[dict] = None
        self.best_complete_route: Optional[List[int]] = None
        self.best_complete_reward = float("-inf")
        self.process_time: Optional[float] = None
        self.nodes_visited = 0
        self.branches_pruned = 0
        self.stats: dict = {}

    def process(self, progress: Optional[Progress] = None) -> None:
        self._clear_results()
        started = perf_counter()
        task = progress.add_task("FindBest sequential", total=None) if progress is not None else None

        def update(report: _Report) -> None:
            if task is not None:
                progress.update(task, completed=report.nodes_visited)

        try:
            problem = _Problem(self.depot, self.stops)
            search = _Search(problem, self.use_branch_bound, callback=update)
            search.visit(problem.root)
            update(search.report)
            self._set_results(search.report)
            self.process_time = perf_counter() - started
            self.stats.update(workers=1, shared_bounds=False, use_branch_bound=self.use_branch_bound)
        finally:
            if task is not None:
                progress.remove_task(task)
        self._print_summary()

    def _set_results(self, report: _Report) -> None:
        if report.best_profit is None:
            raise RuntimeError("Search failed to evaluate even the empty depot return.")
        self.best_route = list(report.best_profit.actions)
        self.best_profit = self._evaluate_solution(report.best_profit)
        self.best_reward = self.best_profit["profit"]
        if report.best_complete is not None:
            self.best_complete_route = list(report.best_complete.actions)
            self.best_complete = self._evaluate_solution(report.best_complete)
            self.best_complete_reward = self.best_complete["profit"]
        self.nodes_visited = report.nodes_visited
        self.branches_pruned = report.branches_pruned
        self.stats = {"nodes_visited": self.nodes_visited, "branches_pruned": self.branches_pruned}

    def _evaluate_solution(self, solution: _Solution) -> dict:
        # Catch future drift if EnvRoute's costing changes without updating
        # the fast numeric engine. Compare unrounded values, not report cents.
        env = EnvRoute(self.depot, self.stops)
        for action in solution.actions:
            env.step(action)
        if not isclose(solution.profit, env.total_reward, rel_tol=1e-12, abs_tol=1e-7):
            raise RuntimeError("Numeric search profit disagrees with EnvRoute replay.")
        return env.get_result()

    def _print_summary(self) -> None:
        if self.verbose:
            print(
                f"{type(self).__name__}: profit={self.best_reward:,.2f}, "
                f"serviced={self.best_profit['serviced_count']}/{len(self.stops)}, "
                f"nodes={self.nodes_visited:,}, pruned={self.branches_pruned:,}, "
                f"time={self.process_time:.6f}s",
                flush=True,
            )

    def evaluate_result(self, route: List[int]) -> dict:
        """Replay customer actions 1..N followed by exactly one final depot 0."""
        if not route or route[-1] != 0:
            raise ValueError("A finished route must end with depot action 0.")
        env = EnvRoute(self.depot, self.stops)
        for action in route:
            env.step(action)
        return env.get_result()

    def evaluate_route(self, route: List[int]) -> float:
        return self.evaluate_result(route)["profit"]

    def build_route_from_indices(self, indices: List[int]) -> List[Stop]:
        """Legacy name: accepts action indices, not zero-based customer indices."""
        result = [self.depot]
        for index in indices:
            if isinstance(index, bool) or not isinstance(index, Integral) or not 0 <= index <= len(self.stops):
                raise ValueError(f"Invalid route action {index!r}.")
            result.append(self.depot if index == 0 else self.stops[index - 1])
        return result
