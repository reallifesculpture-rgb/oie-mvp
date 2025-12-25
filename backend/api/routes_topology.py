from fastapi import APIRouter, HTTPException
from backend.data.replay_engine import engine as replay_engine
from backend.topology.engine import engine as topology_engine
from backend.topology.models import TopologySnapshot

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "topology router active"}

@router.get("/{symbol}", response_model=TopologySnapshot)
def get_topology(symbol: str):
    window = replay_engine.get_window(window_size=topology_engine.window_size)
    if not window:
        raise HTTPException(status_code=400, detail="No data available in replay engine")
    snapshot = topology_engine.compute(symbol=symbol, bars=window)
    return snapshot
