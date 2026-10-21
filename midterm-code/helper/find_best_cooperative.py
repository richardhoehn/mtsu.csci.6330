"""Cooperative parallel branch-and-bound for the research comparison."""

from __future__ import annotations

from typing import List, Optional

from libs.stop import Stop
from .find_best_parallel import FindBestParallel


class FindBestCooperative(FindBestParallel):
    """Workers share best-profit and best-complete incumbent values.

    A worker prunes only when conservative bounds prove its subtree cannot
    improve either objective. The actual winning routes are returned to the
    parent; shared values are used only for safe pruning.
    """

    def __init__(
        self, depot: Stop, stops: List[Stop], verbose: bool = False,
        workers: Optional[int] = None, *, split_depth: int = 2,
        start_method: Optional[str] = None,
    ):
        super().__init__(
            depot, stops, verbose, workers,
            split_depth=split_depth, use_branch_bound=True,
            share_bounds=True, start_method=start_method,
        )
