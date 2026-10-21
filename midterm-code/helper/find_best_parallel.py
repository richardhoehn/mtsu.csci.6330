"""CPU parallel exact search, optionally sharing branch-and-bound incumbents."""

from __future__ import annotations

import multiprocessing as mp
import os
from concurrent.futures import FIRST_COMPLETED, ProcessPoolExecutor, wait
from numbers import Integral
from time import perf_counter
from typing import List, Optional, TYPE_CHECKING

from libs.env_route import EnvRoute
from libs.stop import Stop
from .find_best import FindBest, _Node, _Problem, _Report, _Search

if TYPE_CHECKING:
    from rich.progress import Progress


class _SharedBounds:
    """Small synchronized shared incumbent ledger; workers return actual routes."""

    def __init__(self, context):
        self.profit = context.RawValue("d", float("-inf"))
        self.complete = context.RawValue("d", float("-inf"))
        self.lock = context.Lock()

    def publish(self, profit: float, complete: float) -> None:
        with self.lock:
            self.profit.value = max(self.profit.value, profit)
            self.complete.value = max(self.complete.value, complete)

    def read(self) -> tuple[float, float]:
        with self.lock:
            return self.profit.value, self.complete.value


_WORKER_PROBLEM = None
_WORKER_SHARED = None
_WORKER_USE_BOUNDS = False


def _initialize_worker(problem: _Problem, use_branch_bound: bool, shared) -> None:
    global _WORKER_PROBLEM, _WORKER_SHARED, _WORKER_USE_BOUNDS
    _WORKER_PROBLEM = problem
    _WORKER_SHARED = shared
    _WORKER_USE_BOUNDS = use_branch_bound


def _search_subtree(node: _Node) -> _Report:
    search = _Search(_WORKER_PROBLEM, _WORKER_USE_BOUNDS, _WORKER_SHARED)
    search.visit(node)
    return search.report


def evaluate_route_worker(depot: Stop, stops: List[Stop], route: List[int]) -> float:
    """Compatibility utility: replay a finished route; invalid routes raise."""
    env = EnvRoute(depot, stops)
    for action in route:
        env.step(action)
    return env.get_result()["profit"]


def _positive_int(value, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral) or value <= 0:
        raise ValueError(f"{name} must be a positive integer.")
    return int(value)


def _available_cpus() -> int:
    # Prefer a scheduler allocation, then affinity, over all host CPUs.
    allocated = os.environ.get("SLURM_CPUS_PER_TASK")
    if allocated and allocated.isdigit() and int(allocated) > 0:
        return int(allocated)
    if hasattr(os, "sched_getaffinity"):
        return len(os.sched_getaffinity(0)) or 1
    return os.cpu_count() or 1


class FindBestParallel(FindBest):
    """Independent CPU search by default; no permutation list is materialized.

    A shallow frontier partitions the exact search into disjoint subtrees.
    At most 2 * workers tasks are queued, so factorial work is not submitted
    or retained in memory at once. Precomputed problem data is installed once
    per worker rather than sent with every route.

    For independent parallel branch-and-bound set use_branch_bound=True.
    For shared pruning also set share_bounds=True, or use FindBestCooperative.
    """

    def __init__(
        self, depot: Stop, stops: List[Stop], verbose: bool = False,
        workers: Optional[int] = None, batch_size: int = 1_000, *,
        split_depth: int = 2, use_branch_bound: bool = False,
        share_bounds: bool = False, start_method: Optional[str] = None,
    ):
        super().__init__(depot, stops, verbose, use_branch_bound=use_branch_bound)
        self.workers = _positive_int(_available_cpus() if workers is None else workers, "workers")
        # Retained for old callers. Work is now split by prefixes, not batches
        # of permutations, so batch_size is not used by the new scheduler.
        self.batch_size = _positive_int(batch_size, "batch_size")
        self.split_depth = _positive_int(split_depth, "split_depth")
        self.share_bounds = bool(share_bounds)
        if self.share_bounds and not self.use_branch_bound:
            raise ValueError("Shared bounds require use_branch_bound=True.")
        self.start_method = start_method

    def process(self, progress: Optional[Progress] = None) -> None:
        self._clear_results()
        started = perf_counter()
        context = mp.get_context(self.start_method)
        problem = _Problem(self.depot, self.stops)
        shared = _SharedBounds(context) if self.share_bounds else None
        shallow = _Search(problem, self.use_branch_bound, shared)
        report = _Report()
        frontier = shallow.frontier(problem.root, self.split_depth)
        max_pending = 2 * self.workers
        task = progress.add_task(type(self).__name__, total=None) if progress is not None else None
        tasks_submitted = 0
        peak_pending = 0

        try:
            # Fetch the first job before starting a pool: empty or entirely
            # unreachable scenarios can finish without launching processes.
            first = next(frontier, None)
            if first is not None:
                with ProcessPoolExecutor(
                    max_workers=self.workers, mp_context=context,
                    initializer=_initialize_worker,
                    initargs=(problem, self.use_branch_bound, shared),
                ) as executor:
                    pending = {executor.submit(_search_subtree, first)}
                    tasks_submitted = 1
                    exhausted = False
                    while pending or not exhausted:
                        while not exhausted and len(pending) < max_pending:
                            node = next(frontier, None)
                            if node is None:
                                exhausted = True
                                break
                            pending.add(executor.submit(_search_subtree, node))
                            tasks_submitted += 1
                        peak_pending = max(peak_pending, len(pending))
                        if not pending:
                            continue
                        completed, pending = wait(pending, return_when=FIRST_COMPLETED)
                        for future in completed:
                            report.merge(future.result())
                        if task is not None:
                            progress.update(task, completed=report.nodes_visited + shallow.report.nodes_visited)
            report.merge(shallow.report)
            self._set_results(report)
            self.process_time = perf_counter() - started
            self.stats.update(
                workers=self.workers, shared_bounds=self.share_bounds,
                use_branch_bound=self.use_branch_bound, split_depth=self.split_depth,
                tasks_submitted=tasks_submitted, peak_pending_tasks=peak_pending,
                start_method=context.get_start_method(),
            )
        finally:
            if task is not None:
                progress.remove_task(task)
        self._print_summary()
