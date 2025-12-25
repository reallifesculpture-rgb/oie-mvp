"""
Trade History API Routes
"""
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from backend.services.trade_logger import get_trade_logger

router = APIRouter(tags=["trades"])


@router.get("/ping")
def ping() -> dict:
    return {"status": "ok"}


@router.get("")
@router.get("/")
async def get_trades(
    symbol: Optional[str] = Query(None, description="Filter by symbol (e.g., BTCUSDT)"),
    limit: int = Query(200, ge=1, le=1000, description="Max trades to return"),
    today: bool = Query(False, description="Only show today's trades")
) -> JSONResponse:
    """Get trade history with optional filters"""
    try:
        logger = get_trade_logger()
        trades = logger.get_trades(symbol=symbol, limit=limit, today_only=today)
        return JSONResponse(content={
            "ok": True,
            "count": len(trades),
            "trades": trades
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )


@router.get("/stats")
async def get_stats(
    symbol: Optional[str] = Query(None, description="Filter by symbol")
) -> JSONResponse:
    """Get trading statistics (all-time and today)"""
    try:
        logger = get_trade_logger()
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


@router.post("/reset")
async def reset_trades(
    symbol: Optional[str] = Query(None, description="Symbol to reset (or all if not specified)")
) -> JSONResponse:
    """Reset trade history"""
    try:
        logger = get_trade_logger()
        success = await logger.reset(symbol=symbol)
        return JSONResponse(content={
            "ok": success,
            "message": f"Trades reset" + (f" for {symbol}" if symbol else " (all)")
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={"ok": False, "error": str(e)}
        )
