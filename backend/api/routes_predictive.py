from fastapi import APIRouter, HTTPException
from backend.data.replay_engine import engine as replay_engine
from backend.predictive.engine import engine as predictive_engine
from backend.predictive.models import PredictiveSnapshot

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "predictive router active"}

@router.get("/{symbol}", response_model=PredictiveSnapshot)
def get_predictive(symbol: str):
    window = replay_engine.get_window(window_size=predictive_engine.window_size)
    if not window:
        raise HTTPException(status_code=400, detail="No data available in replay engine")
    snapshot = predictive_engine.compute(symbol=symbol, bars=window)
    return snapshot
