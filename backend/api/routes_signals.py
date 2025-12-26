from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse

from backend.data.replay_engine import engine as replay_engine
from backend.topology.engine import engine as topology_engine
from backend.predictive.engine import engine as predictive_engine
from backend.signals.engine import engine as signals_engine
from backend.signals.models import Signal
from backend.services.signal_logger import get_signal_logger

router = APIRouter(tags=["signals"])


@router.get("/ping")
def ping() -> dict:
    return {"status": "ok"}


@router.get("/history")
async def get_signal_history(
    symbol: Optional[str] = Query(None, description="Filter by symbol (e.g., BTCUSDT)"),
    limit: int = Query(200, ge=1, le=1000, description="Max signals to return"),
    today: bool = Query(False, description="Only show today's signals"),
    decision: Optional[str] = Query(None, description="Filter by decision (EXECUTED, IGNORED, BLOCKED)")
) -> JSONResponse:
    """Get signal history with optional filters"""
    try:
        logger = get_signal_logger()
        signals = logger.get_signals(symbol=symbol, limit=limit, today_only=today, decision=decision)
        return JSONResponse(content={
            "ok": True,
            "count": len(signals),
            "signals": signals
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/last")
async def get_last_signal(
    symbol: Optional[str] = Query(None, description="Symbol to get last signal for")
) -> JSONResponse:
    """Get the most recent signal"""
    try:
        logger = get_signal_logger()
        signal = logger.get_last_signal(symbol=symbol)
        return JSONResponse(content={
            "ok": True,
            "signal": signal
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/stats")
async def get_signal_stats(
    symbol: Optional[str] = Query(None, description="Filter by symbol")
) -> JSONResponse:
    """Get signal statistics"""
    try:
        logger = get_signal_logger()
        stats = logger.get_stats(symbol=symbol)
        return JSONResponse(content={
            "ok": True,
            "stats": stats
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )

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
