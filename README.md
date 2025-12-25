# OIE MVP - Algorithmic Trading System

Automated trading system using OIE (Order Imbalance Engine) for signal generation and execution on Binance Futures.

## Features

- Real-time market data via Binance WebSocket
- Topology analysis (vortex detection, flow patterns)
- Predictive engine (IFI, breakout probability)
- Signal generation with confidence scoring
- Paper trading on Binance Testnet
- Web dashboard for monitoring

## Tech Stack

- **Backend**: FastAPI, Python 3.11+
- **Data**: aiohttp, pandas, numpy
- **Trading**: Binance Futures API
- **Frontend**: Vanilla JS, Lightweight Charts

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env
# Edit .env with your Binance API keys

# Run server
uvicorn backend.main:app --host 0.0.0.0 --port 8000
```

## Environment Variables

```
BINANCE_TESTNET_API_KEY=your_api_key
BINANCE_TESTNET_SECRET=your_secret
```

## Railway Deployment

Start command:
```
uvicorn backend.main:app --host 0.0.0.0 --port $PORT
```

## API Endpoints

- `GET /` - Dashboard UI
- `GET /health` - Health check
- `POST /api/v1/trading/start` - Start trading
- `POST /api/v1/trading/stop` - Stop trading
- `GET /api/v1/trading/status` - Get status
- `WS /ws/live` - Live trading WebSocket

## License

Private - All rights reserved
