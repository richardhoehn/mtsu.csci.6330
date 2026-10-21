# scenario.py
import math
import random
from typing import Tuple, List

from .stop import Stop


# Settings
SCENARIO_PALLET_INC = 1
SCENARIO_PALLET_MIN = 1
SCENARIO_PALLET_MAX = 1

SCENARIO_WEIGHT_INC = 1_000
SCENARIO_WEIGHT_MIN = 1_000
SCENARIO_WEIGHT_MAX = 3_000

SCENARIO_GRID_STEP = 10
SCENARIO_GRID_MIN_RANGE = 100
SCENARIO_GRID_STOP_MULTIPLIER = 15
SCENARIO_GRID_MIN_STOP_DIST = 20


class Scenario:

    # Fixed depot
    DEPOT_DEFAULT = Stop(
        id="DEP",
        name="Depot",
        type="DEPOT",
        x=0.0,
        y=0.0,
        pallet=0,
        weight=0,
        serviced=False,
    )

    def __init__(
        self,
        n_stops: int = 10,
        xy_range: int | None = None,
        skew: float = 0.5,
        seed: int | None = None,
    ):
        """
        n_stops: number of random stops to create
        xy_range: optional maximum x/y coordinate. If omitted, the range is
                  automatically calculated from the number of stops.
        skew: probability of a DO (drop-off). Otherwise PU.
        seed: optional random seed. Using the same seed and inputs produces
              the same scenario.
        """

        self.n_stops = int(n_stops)

        self.xy_range = (
            int(xy_range)
            if xy_range is not None
            else max(SCENARIO_GRID_MIN_RANGE, self.n_stops * SCENARIO_GRID_STOP_MULTIPLIER)
        )

        self.skew = float(skew)
        self.seed = seed

        self.depot: Stop = self._clone(self.DEPOT_DEFAULT)
        self.stops: List[Stop] = []

    @staticmethod
    def _clone(s: Stop) -> Stop:
        return Stop(
            type=s.type,
            id=s.id,
            name=s.name,
            x=s.x,
            y=s.y,
            pallet=s.pallet,
            weight=s.weight,
            serviced=False,
        )

    @staticmethod
    def _num_to_alpha(n: int) -> str:
        # Excel-like A..Z, AA..ZZ
        result = ""

        while n > 0:
            n, rem = divmod(n - 1, 26)
            result = chr(65 + rem) + result

        return result

    def get_scenario(self) -> Tuple[Stop, List[Stop]]:
        return self.depot, self.stops

    def build_random(self) -> Tuple[Stop, List[Stop]]:
        # Local random number generator
        rng = random.Random(self.seed)

        self.depot = self._clone(self.DEPOT_DEFAULT)
        self.stops = []

        # Avoid placing a stop on the depot
        used_coords = {(self.depot.x, self.depot.y)}

        for i in range(self.n_stops):

            # Unique coordinate on grid
            while True:
                x = float(
                    rng.randrange(
                        SCENARIO_GRID_STEP,
                        self.xy_range + 1,
                        SCENARIO_GRID_STEP,
                    )
                )

                y = float(
                    rng.randrange(
                        SCENARIO_GRID_STEP,
                        self.xy_range + 1,
                        SCENARIO_GRID_STEP,
                    )
                )

                if (x, y) in used_coords:
                    continue

                # Make sure this stop is not too close to any existing stop
                too_close = any(
                    math.dist((x, y), (existing_x, existing_y)) < SCENARIO_GRID_MIN_STOP_DIST
                    for existing_x, existing_y in used_coords
                )

                if too_close:
                    continue

                
                used_coords.add((x, y))
                break

            # Random pallet count
            pallet_mag = rng.randrange(
                SCENARIO_PALLET_MIN,
                SCENARIO_PALLET_MAX + 1,
                SCENARIO_PALLET_INC,
            )

            # Random weight
            weight_mag = rng.randrange(
                SCENARIO_WEIGHT_MIN,
                SCENARIO_WEIGHT_MAX + 1,
                SCENARIO_WEIGHT_INC,
            )

            # Decide stop type
            tag = self._num_to_alpha(i + 1)

            if rng.random() < self.skew:
                stop_type = "DO"
                str_id = f"DO-{tag}"
                str_name = f"DropOff {tag}"
            else:
                stop_type = "PU"
                str_id = f"PU-{tag}"
                str_name = f"PickUp {tag}"

            self.stops.append(
                Stop(
                    type=stop_type,
                    id=str_id,
                    name=str_name,
                    x=x,
                    y=y,
                    pallet=pallet_mag,
                    weight=weight_mag,
                    serviced=False,
                )
            )

        return self.depot, self.stops

        