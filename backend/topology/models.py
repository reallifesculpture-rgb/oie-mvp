from pydantic import BaseModel
from datetime import datetime
from typing import List, Literal

class VortexMarker(BaseModel):
    index: int
    timestamp: datetime
    price: float
    strength: float
    direction: Literal["clockwise", "counterclockwise"]

class TopologySnapshot(BaseModel):
    symbol: str
    timestamp: datetime
    coherence: float
    energy: float
    vortexes: List[VortexMarker]
