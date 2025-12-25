import csv
import os
from typing import Optional, List
from datetime import datetime
from backend.data.models import Bar, ReplayInfo

class ReplayEngine:
    def __init__(self, symbol: str = "BTCUSD", csv_path: Optional[str] = None):
        self.symbol = symbol
        self.current_index = 0
        self.bars: List[Bar] = []

        if csv_path:
            self.load_csv(csv_path)
        else:
            # Try to load default sample data
            default_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "sample_data.csv")
            if os.path.exists(default_path):
                self.load_csv(default_path)

    def load_csv(self, path: str):
        self.bars = []
        with open(path, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bar = Bar(
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume']),
                    buy_volume=float(row['buy_volume']) if 'buy_volume' in row and row['buy_volume'] else None,
                    sell_volume=float(row['sell_volume']) if 'sell_volume' in row and row['sell_volume'] else None
                )
                bar.compute_delta()
                self.bars.append(bar)
        self.current_index = 0

    def get_current_bar(self) -> Optional[Bar]:
        if 0 <= self.current_index < len(self.bars):
            return self.bars[self.current_index]
        return None

    def reset(self) -> Optional[Bar]:
        if not self.bars:
            self.current_index = -1
            return None
        self.current_index = 0
        return self.bars[0]

    def step(self) -> Optional[Bar]:
        if not self.bars:
            return None

        if self.current_index == -1:
            self.current_index = 0
            return self.bars[0]

        next_index = self.current_index + 1
        if next_index < len(self.bars):
            self.current_index = next_index
            return self.bars[self.current_index]

        return None

    def info(self) -> ReplayInfo:
        current_bar = None
        display_index = -1

        if self.bars and 0 <= self.current_index < len(self.bars):
            current_bar = self.bars[self.current_index]
            display_index = self.current_index

        return ReplayInfo(
            symbol=self.symbol,
            current_index=display_index,
            total_bars=len(self.bars),
            current_bar=current_bar
        )

    def get_window(self, window_size: int) -> List[Bar]:
        if not self.bars:
            return []

        effective_index = max(0, min(self.current_index, len(self.bars) - 1))
        start_index = max(0, effective_index - window_size + 1)

        return self.bars[start_index:effective_index + 1]

engine = ReplayEngine()
