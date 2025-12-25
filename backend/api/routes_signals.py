from typing import List
from fastapi import APIRouter, HTTPException

from backend.data.replay_engine import engine as replay_engine
from backend.topology.engine import engine as topology_engine
from backend.predictive.engine import engine as predictive_engine
from backend.signals.engine import engine as signals_engine
from backend.signals.models import Signal

router = APIRouter(prefix="/api/v1/signals", tags=["signals"])

@router.get("/ping")
def ping() -> dict:
    return {"status": "ok"}

@router.get("/{symbol}", response_model=List[Signal])
def get_signals(symbol: str) -> List[Signal]:
    window_size = max(
        getattr(topology_engine, "window_size", 100),
        getattr(predictive_engine, "window_size", 200),
    )
    window = replay_engine.get_window(window_size=window_size)

    if not window:
        raise HTTPException(status_code=400, detail="No data available in replay engine")

    topology_snapshot = topology_engine.compute(symbol=symbol, bars=window)
    predictive_snapshot = predictive_engine.compute(symbol=symbol, bars=window)
    signals = signals_engine.compute(
        symbol=symbol,
        topology=topology_snapshot,
        predictive=predictive_snapshot,
        bars=window,  # Pentru delta trend calculation
    )
    return signals
