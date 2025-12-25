from pydantic import BaseModel
from datetime import datetime
from typing import List

class PredictiveSnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    horizon_bars: int
    num_scenarios: int

    IFI: float
    breakout_probability_up: float
    breakout_probability_down: float
    energy_collapse_risk: float

    cone_upper: List[float]
    cone_lower: List[float]
