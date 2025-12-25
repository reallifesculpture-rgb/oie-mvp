from fastapi import APIRouter
from backend.data.replay_engine import engine as replay_engine
from backend.data.models import Bar, ReplayInfo
from typing import Optional

router = APIRouter()

@router.get("/ping")
def ping():
    return {"message": "replay router active"}

@router.get("/info", response_model=ReplayInfo)
def get_info():
    return replay_engine.info()

@router.post("/reset", response_model=Optional[Bar])
def reset():
    return replay_engine.reset()

@router.post("/step", response_model=Optional[Bar])
def step():
    return replay_engine.step()
