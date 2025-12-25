from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class Bar(BaseModel):
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: Optional[float] = None
    sell_volume: Optional[float] = None
    delta: Optional[float] = None
    atr: Optional[float] = None

    def compute_delta(self):
        if self.buy_volume is not None and self.sell_volume is not None:
            self.delta = self.buy_volume - self.sell_volume

class ReplayInfo(BaseModel):
    symbol: str
    current_index: int
    total_bars: int
    current_bar: Optional[Bar] = None
