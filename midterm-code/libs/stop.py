# Import Sys Libs
from dataclasses import dataclass
from typing import Literal

StopType = Literal["PU", "DO", "DEPOT"]

# Constants
STOP_REVENUE_DO_MULTIPLIER = 1.0
STOP_REVENUE_PU_MULTIPLIER = 1.0


@dataclass(slots=True)
class Stop:
    id: str
    name: str
    type: StopType
    x: float
    y: float
    pallet: int
    weight: int
    serviced: bool = False

    @property
    def revenue(self) -> float:
        if self.type == "PU":
            return float(self.weight * STOP_REVENUE_PU_MULTIPLIER)

        if self.type == "DO":
            return float(self.weight * STOP_REVENUE_DO_MULTIPLIER)

        return 0.0