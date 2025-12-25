import math
import random
from typing import List
from datetime import datetime

from backend.data.models import Bar
from backend.predictive.models import PredictiveSnapshot

class PredictiveEngine:
    def __init__(
        self,
        window_size: int = 200,
        horizon_bars: int = 20,
        num_scenarios: int = 20,
        breakout_atr_mult: float = 1.0,
        collapse_atr_mult: float = 0.5,
    ):
        self.window_size = window_size
        self.horizon_bars = horizon_bars
        self.num_scenarios = num_scenarios
        self.breakout_atr_mult = breakout_atr_mult
        self.collapse_atr_mult = collapse_atr_mult

    def compute(self, symbol: str, bars: List[Bar]) -> PredictiveSnapshot:
        if len(bars) < 2:
            default_price = bars[-1].close if bars else 0.0
            return PredictiveSnapshot(
                symbol=symbol,
                timestamp=bars[-1].timestamp if bars else datetime.now(),
                horizon_bars=self.horizon_bars,
                num_scenarios=self.num_scenarios,
                IFI=0.0,
                breakout_probability_up=0.0,
                breakout_probability_down=0.0,
                energy_collapse_risk=0.0,
                cone_upper=[default_price] * self.horizon_bars,
                cone_lower=[default_price] * self.horizon_bars
            )

        closes = [b.close for b in bars if b.close is not None]
        if len(closes) < 2:
            default_price = closes[0] if closes else 0.0
            return PredictiveSnapshot(
                symbol=symbol,
                timestamp=bars[-1].timestamp,
                horizon_bars=self.horizon_bars,
                num_scenarios=self.num_scenarios,
                IFI=0.0,
                breakout_probability_up=0.0,
                breakout_probability_down=0.0,
                energy_collapse_risk=0.0,
                cone_upper=[default_price] * self.horizon_bars,
                cone_lower=[default_price] * self.horizon_bars
            )

        returns = []
        for i in range(1, len(closes)):
            prev = closes[i - 1]
            curr = closes[i]
            ret = 0.0 if prev == 0 else (curr - prev) / abs(prev)
            returns.append(ret)

        if not returns:
            sigma = 0.0
        else:
            mean_ret = sum(returns) / len(returns)
            var = sum((r - mean_ret) ** 2 for r in returns) / max(1, len(returns) - 1)
            sigma = math.sqrt(var)

        N_atr = min(20, len(bars))
        recent = bars[-N_atr:]
        true_ranges = [(b.high - b.low) for b in recent]
        avg_tr = sum(true_ranges) / len(true_ranges) if true_ranges else 0.0
        atr = avg_tr or 1e-6

        recent_high = max(b.high for b in recent)
        recent_low = min(b.low for b in recent)

        breakout_up_level = recent_high + self.breakout_atr_mult * atr
        breakout_down_level = recent_low - self.breakout_atr_mult * atr

        last_price = closes[-1]

        paths = []
        for s in range(self.num_scenarios):
            price = last_price
            path = []
            for h in range(self.horizon_bars):
                eps = random.gauss(0.0, 1.0)
                step_ret = sigma * eps
                price = price * (1.0 + step_ret)
                path.append(price)
            paths.append(path)

        cone_upper = []
        cone_lower = []
        std_values = []

        for h in range(self.horizon_bars):
            step_values = [path[h] for path in paths]
            mean_h = sum(step_values) / len(step_values)
            var_h = sum((v - mean_h) ** 2 for v in step_values) / max(1, len(step_values) - 1)
            std_h = math.sqrt(var_h)
            std_values.append(std_h)

            upper_h = mean_h + std_h
            lower_h = mean_h - std_h
            cone_upper.append(upper_h)
            cone_lower.append(lower_h)

        count_breakout_up = 0
        count_breakout_down = 0
        for path in paths:
            if any(p >= breakout_up_level for p in path):
                count_breakout_up += 1
            if any(p <= breakout_down_level for p in path):
                count_breakout_down += 1

        breakout_probability_up = count_breakout_up / self.num_scenarios
        breakout_probability_down = count_breakout_down / self.num_scenarios

        collapse_band = self.collapse_atr_mult * atr
        count_collapse = sum(1 for path in paths if abs(path[-1] - last_price) <= collapse_band)
        energy_collapse_risk = count_collapse / self.num_scenarios

        avg_std = sum(std_values) / len(std_values) if std_values else 0.0
        vol_ratio = avg_std / (abs(last_price) + 1e-9)
        IFI = max(0.0, min(100.0, vol_ratio * 10000.0))

        return PredictiveSnapshot(
            symbol=symbol,
            timestamp=bars[-1].timestamp,
            horizon_bars=self.horizon_bars,
            num_scenarios=self.num_scenarios,
            IFI=IFI,
            breakout_probability_up=breakout_probability_up,
            breakout_probability_down=breakout_probability_down,
            energy_collapse_risk=energy_collapse_risk,
            cone_upper=cone_upper,
            cone_lower=cone_lower
        )

engine = PredictiveEngine()
