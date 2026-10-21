#!/usr/bin/env python3

# Project imports
from libs.scenario import Scenario
from helper.find_best import FindBest
from helper.find_best_parallel import FindBestParallel
from helper.find_best_cooperative import FindBestCooperative
from helper.logger import Logger

# Progress display
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    SpinnerColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


# Stops to evaluate
STOPS = [12, 13, 14, 15, 16, 17, 18, 19, 20]

# Scenario seeds: 0 through SEED_RANGE - 1
SEED_RANGE = 100

# Worker processes for both parallel solvers
WORKERS = 20

# Customer decisions used to divide the parallel search into subtrees
SPLIT_DEPTH = 2

# New filename for the simplified logger schema
RESULTS_FILE = "./results/Best-Scenario-00-99.csv"


progress_cols = [
    SpinnerColumn(),
    TextColumn("[progress.description]{task.description}"),
    BarColumn(),
    TaskProgressColumn(),
    TimeElapsedColumn(),
    TimeRemainingColumn(),
]


def result_signature(solver):
    """Compare maximum-profit and best-complete results."""
    return (
        solver.best_reward,
        tuple(solver.best_route),
        solver.best_complete_reward,
        tuple(solver.best_complete_route)
        if solver.best_complete_route is not None
        else None,
    )


def main():
    # Only the parent process writes to the CSV.
    logger = Logger(RESULTS_FILE)

    with Progress(*progress_cols, transient=True) as progress:
        stops_task = progress.add_task(
            "Working on Stops",
            total=len(STOPS),
        )

        for n_stops in STOPS:
            progress.update(
                stops_task,
                description=f"Working on Stops={n_stops:,}",
            )

            eval_task = progress.add_task(
                "Working on Seed",
                total=SEED_RANGE,
            )

            try:
                for seed in range(SEED_RANGE):
                    progress.update(
                        eval_task,
                        description=f"Working on Seed={seed:,}",
                    )

                    # Build once so every solver gets the same scenario.
                    scenario = Scenario(
                        n_stops=n_stops,
                        seed=seed,
                    )

                    depot_k, stops_k = scenario.build_random()

                    solvers = []

                    if n_stops <= 12:
                        solvers.append(("Sequential", FindBest(depot_k, stops_k)))

                    solvers.extend([
                        ("Parallel",    FindBestParallel(depot_k, stops_k, workers=WORKERS, split_depth=SPLIT_DEPTH)),
                        ("Cooperative", FindBestCooperative(depot_k, stops_k, workers=WORKERS, split_depth=SPLIT_DEPTH)),
                    ])

                    models_task = progress.add_task("Working on Model", total=len(solvers))

                    expected = None

                    try:
                        for model_name, solver in solvers:
                            progress.update(models_task, description=f"Running {model_name}")

                            solver.process(progress=progress)

                            # Exact solvers should return matching results.
                            signature = result_signature(solver)

                            if expected is None:
                                expected = signature
                            elif signature != expected:
                                raise RuntimeError(
                                    f"Exact solvers disagree: "
                                    f"stops={n_stops}, seed={seed}, "
                                    f"model={model_name}. "
                                    f"Expected {expected}, "
                                    f"found {signature}."
                                )

                            # Copy the finished results into one CSV row.
                            logger.log_solver(
                                model=model_name,
                                stops=n_stops,
                                seed=seed,
                                solver=solver,
                            )

                            progress.console.print(
                                f"{model_name} | "
                                f"Stops={n_stops} | Seed={seed} | "
                                f"Profit={solver.best_reward:,.2f} | "
                                f"Serviced="
                                f"{solver.best_profit['serviced_count']}"
                                f"/{n_stops} | "
                                f"Time={solver.process_time:.3f}s"
                            )

                            progress.advance(models_task)

                    finally:
                        progress.remove_task(models_task)

                    progress.advance(eval_task)

            finally:
                progress.remove_task(eval_task)

            progress.advance(stops_task)

    print(f"Results saved to {RESULTS_FILE}")


if __name__ == "__main__":
    main()