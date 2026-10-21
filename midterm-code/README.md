# Routing Solver Comparison — Midterm Touchpoint

This project compares three exact route-search approaches: **Sequential**, **Parallel**, and **Cooperative** (parallel search with shared bounds). It includes the Python implementation, sample benchmark results, and a Jupyter notebook with runtime comparisons.

## Setup

Requires Python 3.10+.

```bash
python -m pip install rich pandas numpy matplotlib notebook
```

## Run the Solvers

From the project root:

```bash
python Runner-Best.py
```

Edit `STOPS`, `SEED_RANGE`, and `WORKERS` near the top of `Runner-Best.py` before running.

**Note:** The defaults (12–20 stops, 100 seeds, 20 workers) can take a very long time. For a quick test, use:

```python
STOPS = [5, 6]
SEED_RANGE = 2
WORKERS = 2
```

Results are written to `results/Best-Scenario-00-99.csv`. The runner appends results to this file, so consider backing up the supplied CSV before rerunning.

## View the Results

From the project root:

```bash
cd visuals
jupyter notebook Best-Time-Comparison.ipynb
```

Run the notebook cells to generate charts comparing runtimes, speedup, and variability.

The notebook reads the existing results from `../results/Best-Scenario-00-99.csv`. Generated figures are available in `visuals/images/`.

## Main Files

- `Runner-Best.py` — Benchmark entry point
- `helper/` — Sequential, Parallel, and Cooperative solvers and CSV logger
- `libs/` — Scenario generation and routing environment
- `results/` — Benchmark results (CSV)
- `visuals/` — Jupyter notebook, figures, and summary data
