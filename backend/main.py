from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, Response
import asyncio
import os

from backend.api.routes_replay import router as replay_router
from backend.api.routes_topology import router as topology_router
from backend.api.routes_predictive import router as predictive_router
from backend.api.routes_signals import router as signals_router

from backend.data.replay_engine import engine as replay_engine
from backend.topology.engine import engine as topology_engine
from backend.predictive.engine import engine as predictive_engine
from backend.signals.engine import engine as signals_engine

app = FastAPI(title="OIE MVP API", version="1.0.0")

# Frontend static files
FRONTEND_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(replay_router, prefix="/api/v1/replay", tags=["replay"])
app.include_router(topology_router, prefix="/api/v1/topology", tags=["topology"])
app.include_router(predictive_router, prefix="/api/v1/predictive", tags=["predictive"])
app.include_router(signals_router, prefix="/api/v1/signals", tags=["signals"])

# Live trading runner (lazy import to avoid errors if not configured)
_live_runner = None

def get_live_runner():
    global _live_runner
    if _live_runner is None:
        try:
            from backend.trading.live_runner import LiveTradingRunner
            _live_runner = LiveTradingRunner(symbol="BTCUSDT", interval="1m")
        except Exception as e:
            print(f"Warning: Could not initialize live runner: {e}")
    return _live_runner

@app.get("/")
async def serve_frontend():
    """Serve the frontend dashboard"""
    index_path = os.path.join(FRONTEND_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"message": "Frontend not found. Access /docs for API documentation."}

@app.get("/styles.css")
async def serve_css():
    """Serve CSS file"""
    css_path = os.path.join(FRONTEND_DIR, "styles.css")
    if os.path.exists(css_path):
        return FileResponse(css_path, media_type="text/css")
    return {"error": "CSS not found"}

@app.get("/app.js")
async def serve_js():
    """Serve JS file with no-cache headers"""
    js_path = os.path.join(FRONTEND_DIR, "app.js")
    if os.path.exists(js_path):
        with open(js_path, 'r', encoding='utf-8') as f:
            content = f.read()
        return Response(
            content=content,
            media_type="application/javascript",
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"error": "JS not found"}

@app.get("/health")
def health_check():
    return {"status": "ok"}

# ============================================
# LIVE TRADING ENDPOINTS
# ============================================

# Supported symbols
SUPPORTED_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "XRPUSDT"]

# Store runners for different symbol+timeframe combinations
_runners = {}

def get_runner(symbol: str = "BTCUSDT", interval: str = "1m"):
    """Get or create runner for specific symbol and interval"""
    global _runners
    key = f"{symbol}_{interval}"
    if key not in _runners:
        try:
            from backend.trading.live_runner import LiveTradingRunner
            _runners[key] = LiveTradingRunner(symbol=symbol, interval=interval)
        except Exception as e:
            print(f"Warning: Could not initialize {key} runner: {e}")
            return None
    return _runners[key]

def get_all_runners():
    """Get all active runners"""
    return _runners

@app.get("/api/v1/symbols")
async def get_symbols():
    """Returnează lista de simboluri suportate"""
    return {"symbols": SUPPORTED_SYMBOLS}

@app.post("/api/v1/trading/start")
async def start_live_trading(symbol: str = "BTCUSDT", interval: str = "1m"):
    """Pornește live trading cu Binance Testnet pentru un simbol"""
    if symbol not in SUPPORTED_SYMBOLS:
        return {"success": False, "error": f"Symbol {symbol} not supported. Use one of: {SUPPORTED_SYMBOLS}"}

    runner = get_runner(symbol, interval)
    if runner is None:
        return {"success": False, "error": "Live trading not configured"}

    # If already running, return success (it's already working)
    if runner.running:
        return {"success": True, "symbol": symbol, "interval": interval, "status": runner.get_status(), "message": "Already running"}

    success = await runner.start()
    return {"success": success, "symbol": symbol, "interval": interval, "status": runner.get_status()}

@app.post("/api/v1/trading/start-all")
async def start_all_symbols(interval: str = "1m"):
    """Pornește trading pentru toate simbolurile pe un timeframe"""
    results = {}
    for symbol in SUPPORTED_SYMBOLS:
        runner = get_runner(symbol, interval)
        if runner:
            if not runner.running:
                success = await runner.start()
                results[symbol] = {"success": success, "status": "started" if success else "failed"}
            else:
                results[symbol] = {"success": True, "status": "already_running"}
        else:
            results[symbol] = {"success": False, "status": "not_configured"}
    return {"interval": interval, "results": results}

@app.post("/api/v1/trading/stop")
async def stop_live_trading(symbol: str = None, interval: str = None):
    """Oprește live trading și elimină runner-ul pentru restart fresh"""
    global _runners
    if symbol and interval:
        key = f"{symbol}_{interval}"
        if key in _runners and _runners[key].running:
            await _runners[key].stop()
            del _runners[key]  # Remove runner for fresh start
            return {"success": True, "symbol": symbol, "interval": interval}
        return {"success": False, "error": f"{key} not running"}

    # Stop all and clear runners for fresh start
    stopped = []
    for key, runner in list(_runners.items()):
        if runner.running:
            await runner.stop()
            stopped.append(key)
    _runners.clear()  # Clear all runners for fresh start

    return {"success": True, "stopped": stopped}

@app.get("/api/v1/trading/status")
async def get_trading_status():
    """Returnează statusul tuturor perechilor active"""
    runners_status = {}
    total_balance = 0

    for key, runner in _runners.items():
        status = runner.get_status()
        runners_status[key] = {
            "symbol": status.get("symbol"),
            "interval": status.get("interval"),
            "bar": status.get("current_bar"),
            "bars_processed": status.get("bars_processed", 0),
            "topology": status.get("topology"),
            "predictive": status.get("predictive"),
            "signals": status.get("signals", []),
            "stats": status.get("trading_stats")
        }
        if runner.trading_manager and runner.trading_manager.connector:
            total_balance = runner.trading_manager.connector.balance

    if not runners_status:
        return {"running": False, "runners": {}, "balance": 0}

    return {"running": True, "runners": runners_status, "balance": total_balance}

# ============================================
# WEBSOCKET ENDPOINTS
# ============================================

@app.websocket("/ws/live")
async def ws_live_trading(websocket: WebSocket):
    """WebSocket pentru live trading - date reale de la Binance pentru toate simbolurile"""
    await websocket.accept()
    print("[WS] New WebSocket client connected")

    # Get all active runners and add client to them
    runners_added = []
    for key, runner in _runners.items():
        if runner and runner.running:
            runner.add_ws_client(websocket)
            runners_added.append(key)
            print(f"[WS] Added client to {key} runner")

    if not runners_added:
        # No active runners, try to start BTCUSDT 1m
        runner = get_runner("BTCUSDT", "1m")
        if runner:
            runner.add_ws_client(websocket)
            runners_added.append("BTCUSDT_1m")
            if not runner.running:
                await runner.start()

    if not runners_added:
        await websocket.send_json({"error": "No trading runners available"})
        await websocket.close()
        return

    # Send initial status for all runners immediately
    try:
        all_status = {}
        total_balance = 0
        for key in runners_added:
            if key in _runners:
                runner = _runners[key]
                status = runner.get_status()
                all_status[key] = status
                if runner.trading_manager and runner.trading_manager.connector:
                    total_balance = runner.trading_manager.connector.balance

        await websocket.send_json({
            "type": "init",
            "runners": all_status,
            "balance": total_balance,
            "active_symbols": list(set([k.split("_")[0] for k in runners_added]))
        })
    except Exception as e:
        print(f"[WS] Error sending initial status: {e}")

    try:
        # Keep connection alive with heartbeats
        while True:
            try:
                # Wait for messages from client (ping/pong) with shorter timeout
                data = await asyncio.wait_for(websocket.receive_text(), timeout=5)
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat with data from all active runners
                try:
                    all_status = {}
                    total_balance = 0
                    for key in runners_added:
                        if key in _runners:
                            runner = _runners[key]
                            status = runner.get_status()
                            all_status[key] = {
                                "symbol": status.get("symbol"),
                                "interval": status.get("interval"),
                                "bar": status.get("current_bar"),
                                "bars_processed": status.get("bars_processed", 0),
                                "signals": status.get("signals_generated", 0),
                                "trades": status.get("trades_executed", 0),
                                "stats": status.get("trading_stats")
                            }
                            if runner.trading_manager and runner.trading_manager.connector:
                                total_balance = runner.trading_manager.connector.balance

                    await websocket.send_json({
                        "type": "heartbeat",
                        "runners": all_status,
                        "balance": total_balance
                    })
                except Exception as e:
                    print(f"[WS] Heartbeat error: {e}")
            except WebSocketDisconnect:
                print("[WS] Client disconnected")
                break
    finally:
        # Remove client from all runners
        for key in runners_added:
            if key in _runners:
                _runners[key].remove_ws_client(websocket)
        print("[WS] Client removed from all runners")

@app.websocket("/ws")
async def ws_frontend(websocket: WebSocket):
    """WebSocket endpoint for frontend dashboard (demo/replay mode)"""
    await websocket.accept()
    try:
        replay_engine.reset()
        while True:
            bar = replay_engine.step()
            if bar is None:
                # Loop back to start
                replay_engine.reset()
                bar = replay_engine.step()
                if bar is None:
                    break

            window = replay_engine.get_window(window_size=max(
                topology_engine.window_size,
                predictive_engine.window_size,
            ))
            if not window:
                continue

            topology_snapshot = topology_engine.compute(symbol="SIM", bars=window)
            predictive_snapshot = predictive_engine.compute(symbol="SIM", bars=window)
            signals = signals_engine.compute(symbol="SIM", topology=topology_snapshot, predictive=predictive_snapshot, bars=window)

            payload = {
                "type": "update",
                "bar": bar.model_dump(mode='json'),
                "topology": topology_snapshot.model_dump(mode='json'),
                "predictive": predictive_snapshot.model_dump(mode='json'),
                "signals": [s.model_dump(mode='json') for s in signals],
            }
            await websocket.send_json(payload)
            await asyncio.sleep(1)  # 1 second updates
    except WebSocketDisconnect:
        return

@app.websocket("/ws/stream")
async def stream_oie(websocket: WebSocket):
    await websocket.accept()
    try:
        replay_engine.reset()
        while True:
            bar = replay_engine.step()
            if bar is None:
                break

            window = replay_engine.get_window(window_size=max(
                topology_engine.window_size,
                predictive_engine.window_size,
            ))
            if not window:
                break

            topology_snapshot = topology_engine.compute(symbol="SIM", bars=window)
            predictive_snapshot = predictive_engine.compute(symbol="SIM", bars=window)
            signals = signals_engine.compute(symbol="SIM", topology=topology_snapshot, predictive=predictive_snapshot, bars=window)

            payload = {
                "bar": bar.model_dump(mode='json'),
                "topology": topology_snapshot.model_dump(mode='json'),
                "predictive": predictive_snapshot.model_dump(mode='json'),
                "signals": [s.model_dump(mode='json') for s in signals],
            }
            await websocket.send_json(payload)
            await asyncio.sleep(0.2)
    except WebSocketDisconnect:
        return

