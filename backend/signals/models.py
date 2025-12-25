from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel

SignalType = Literal[
    "predictive_breakout_long",
    "predictive_breakout_short",
    "flow_neutral_watch",
]

class Signal(BaseModel):
    symbol: str
    timestamp: datetime
    type: SignalType
    confidence: float
    breakout_probability: float
    IFI: float
    energy_collapse_risk: float
    description: Optional[str] = None
