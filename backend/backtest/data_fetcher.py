"""
OIE MVP - Data Fetcher pentru Backtesting
==========================================

Descarcă date OHLCV cu volum buy/sell (delta) de la diverse surse.

Surse suportate:
1. Binance - Date gratuite, include aggTrades pentru calculul delta
2. Bybit - Date gratuite cu delta inclus
3. CSV local - Încarcă date din fișiere existente

Utilizare:
    python -m backend.backtest.data_fetcher --source binance --symbol BTCUSDT --interval 1m --days 30
"""

import os
import csv
import asyncio
import aiohttp
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any, Literal
from dataclasses import dataclass, asdict
import json
from pathlib import Path


@dataclass
class OHLCVBar:
    """Structura bare OHLCV cu delta"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: Optional[float] = None
    sell_volume: Optional[float] = None
    delta: Optional[float] = None
    trades: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'open': self.open,
            'high': self.high,
            'low': self.low,
            'close': self.close,
            'volume': self.volume,
            'buy_volume': self.buy_volume,
            'sell_volume': self.sell_volume,
            'delta': self.delta,
            'trades': self.trades
        }


class BinanceFetcher:
    """
    Descarcă date de la Binance Futures.
    
    Binance oferă:
    - OHLCV klines (gratuit, fără limită)
    - Aggregate trades pentru calculul delta (necesită mai mult timp)
    """
    
    BASE_URL = "https://fapi.binance.com"  # Futures API
    SPOT_URL = "https://api.binance.com"   # Spot API
    
    INTERVALS = {
        '1m': 60_000,
        '3m': 180_000,
        '5m': 300_000,
        '15m': 900_000,
        '30m': 1_800_000,
        '1h': 3_600_000,
        '4h': 14_400_000,
        '1d': 86_400_000,
    }
    
    def __init__(self, use_futures: bool = True):
        self.use_futures = use_futures
        self.base_url = self.BASE_URL if use_futures else self.SPOT_URL
    
    async def fetch_klines(
        self, 
        symbol: str, 
        interval: str, 
        start_time: datetime,
        end_time: datetime,
        limit: int = 1500
    ) -> List[OHLCVBar]:
        """
        Descarcă OHLCV klines de la Binance.
        
        Args:
            symbol: Simbol trading (ex: BTCUSDT)
            interval: Interval (1m, 5m, 15m, 1h, 4h, 1d)
            start_time: Timestamp start
            end_time: Timestamp end
            limit: Max bare per request (max 1500)
        """
        bars = []
        current_start = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        endpoint = f"{self.base_url}/fapi/v1/klines" if self.use_futures else f"{self.base_url}/api/v3/klines"
        
        async with aiohttp.ClientSession() as session:
            while current_start < end_ms:
                params = {
                    'symbol': symbol.upper(),
                    'interval': interval,
                    'startTime': current_start,
                    'endTime': end_ms,
                    'limit': limit
                }
                
                async with session.get(endpoint, params=params) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise Exception(f"Binance API error: {error}")
                    
                    data = await resp.json()
                    
                    if not data:
                        break
                    
                    for kline in data:
                        bar = OHLCVBar(
                            timestamp=datetime.fromtimestamp(kline[0] / 1000),
                            open=float(kline[1]),
                            high=float(kline[2]),
                            low=float(kline[3]),
                            close=float(kline[4]),
                            volume=float(kline[5]),
                            trades=int(kline[8]) if len(kline) > 8 else None
                        )
                        bars.append(bar)
                    
                    # Următorul batch
                    current_start = int(data[-1][0]) + self.INTERVALS.get(interval, 60_000)
                    
                    # Throttle pentru a evita rate limits
                    await asyncio.sleep(0.1)
                    
                    print(f"  Descărcat {len(bars)} bare până la {bars[-1].timestamp}")
        
        return bars
    
    async def fetch_aggTrades_for_delta(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        interval_seconds: int = 60
    ) -> Dict[datetime, tuple]:
        """
        Descarcă aggregate trades pentru a calcula buy/sell volume.
        
        ATENȚIE: Aceasta este o operație lentă pentru perioade lungi!
        Recomandare: Folosiți pentru <= 1 zi de date.
        
        Returns:
            Dict mapping timestamp (truncat la interval) -> (buy_vol, sell_vol)
        """
        delta_map = {}
        current_start = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        endpoint = f"{self.base_url}/fapi/v1/aggTrades" if self.use_futures else f"{self.base_url}/api/v3/aggTrades"
        
        async with aiohttp.ClientSession() as session:
            while current_start < end_ms:
                params = {
                    'symbol': symbol.upper(),
                    'startTime': current_start,
                    'endTime': min(current_start + 3600_000, end_ms),  # Max 1h per request
                    'limit': 1000
                }
                
                async with session.get(endpoint, params=params) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        print(f"Warning: aggTrades error: {error}")
                        current_start += 3600_000
                        continue
                    
                    trades = await resp.json()
                    
                    if not trades:
                        current_start += 3600_000
                        continue
                    
                    for trade in trades:
                        trade_time = datetime.fromtimestamp(trade['T'] / 1000)
                        # Truncează la interval
                        bar_time = trade_time.replace(
                            second=0, 
                            microsecond=0,
                            minute=(trade_time.minute // (interval_seconds // 60)) * (interval_seconds // 60)
                        )
                        
                        qty = float(trade['q'])
                        is_buyer_maker = trade['m']  # True = vânzare, False = cumpărare
                        
                        if bar_time not in delta_map:
                            delta_map[bar_time] = [0.0, 0.0]  # [buy, sell]
                        
                        if is_buyer_maker:
                            delta_map[bar_time][1] += qty  # Sell
                        else:
                            delta_map[bar_time][0] += qty  # Buy
                    
                    if trades:
                        current_start = trades[-1]['T'] + 1
                    else:
                        current_start += 3600_000
                    
                    await asyncio.sleep(0.05)
        
        return delta_map


class BybitFetcher:
    """
    Descarcă date de la Bybit.
    
    Bybit oferă delta direct în unele endpoint-uri!
    """
    
    BASE_URL = "https://api.bybit.com"
    
    async def fetch_klines(
        self,
        symbol: str,
        interval: str,  # 1, 3, 5, 15, 30, 60, 120, 240, 360, 720, D, W, M
        start_time: datetime,
        end_time: datetime,
        category: str = "linear"  # linear = USDT perpetual
    ) -> List[OHLCVBar]:
        """Descarcă klines de la Bybit"""
        bars = []
        current_start = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        # Convertește interval la format Bybit
        interval_map = {
            '1m': '1', '3m': '3', '5m': '5', '15m': '15', '30m': '30',
            '1h': '60', '4h': '240', '1d': 'D'
        }
        bybit_interval = interval_map.get(interval, interval)
        
        async with aiohttp.ClientSession() as session:
            while current_start < end_ms:
                params = {
                    'category': category,
                    'symbol': symbol.upper(),
                    'interval': bybit_interval,
                    'start': current_start,
                    'end': end_ms,
                    'limit': 1000
                }
                
                url = f"{self.BASE_URL}/v5/market/kline"
                
                async with session.get(url, params=params) as resp:
                    if resp.status != 200:
                        error = await resp.text()
                        raise Exception(f"Bybit API error: {error}")
                    
                    data = await resp.json()
                    
                    if data['retCode'] != 0:
                        raise Exception(f"Bybit error: {data['retMsg']}")
                    
                    klines = data['result']['list']
                    
                    if not klines:
                        break
                    
                    # Bybit returnează în ordine descrescătoare
                    for kline in reversed(klines):
                        bar = OHLCVBar(
                            timestamp=datetime.fromtimestamp(int(kline[0]) / 1000),
                            open=float(kline[1]),
                            high=float(kline[2]),
                            low=float(kline[3]),
                            close=float(kline[4]),
                            volume=float(kline[5])
                        )
                        bars.append(bar)
                    
                    # Următorul batch
                    current_start = int(klines[0][0]) + 1
                    
                    await asyncio.sleep(0.1)
                    print(f"  Descărcat {len(bars)} bare până la {bars[-1].timestamp}")
        
        return bars


class DataManager:
    """
    Manager pentru date de backtesting.
    
    Funcționalități:
    - Descarcă și salvează date
    - Încarcă date din cache/CSV
    - Combină OHLCV cu delta
    """
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'historical')
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def get_cache_path(self, symbol: str, interval: str, source: str) -> Path:
        """Returnează calea către fișierul cache"""
        return self.data_dir / f"{source}_{symbol}_{interval}.csv"
    
    async def download_data(
        self,
        symbol: str,
        interval: str,
        days: int = 30,
        source: Literal['binance', 'bybit'] = 'binance',
        include_delta: bool = True,
        use_futures: bool = True
    ) -> List[OHLCVBar]:
        """
        Descarcă date și le salvează în cache.
        
        Args:
            symbol: Simbol (ex: BTCUSDT)
            interval: Interval (1m, 5m, 15m, 1h, 4h, 1d)
            days: Numărul de zile de date
            source: Sursă date (binance, bybit)
            include_delta: Dacă să calculeze delta (mai lent)
            use_futures: Folosește futures vs spot
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        print(f"\n📊 Descărcare date {symbol} ({interval}) de la {source}")
        print(f"   Perioadă: {start_time.date()} → {end_time.date()} ({days} zile)")
        
        # Descarcă OHLCV
        if source == 'binance':
            fetcher = BinanceFetcher(use_futures=use_futures)
            bars = await fetcher.fetch_klines(symbol, interval, start_time, end_time)
            
            # Calculează delta dacă e cerut (doar pentru perioade scurte)
            if include_delta and days <= 7:
                print(f"\n🔄 Calculare delta din aggTrades (poate dura câteva minute)...")
                interval_seconds = {'1m': 60, '5m': 300, '15m': 900, '1h': 3600}
                delta_map = await fetcher.fetch_aggTrades_for_delta(
                    symbol, start_time, end_time,
                    interval_seconds.get(interval, 60)
                )
                
                # Îmbină delta cu barele
                for bar in bars:
                    bar_time = bar.timestamp.replace(second=0, microsecond=0)
                    if bar_time in delta_map:
                        bar.buy_volume = delta_map[bar_time][0]
                        bar.sell_volume = delta_map[bar_time][1]
                        bar.delta = bar.buy_volume - bar.sell_volume
            elif include_delta and days > 7:
                print(f"⚠️ Delta estimation (aggTrades descărcare e lentă pentru > 7 zile)")
                print(f"   Folosim estimare bazată pe preț: delta = volume * sign(close - open)")
                for bar in bars:
                    # Estimare simplă bazată pe direcția candelei
                    if bar.close > bar.open:
                        # Candelă verde → majoritatevolum de cumpărare
                        ratio = 0.6 + 0.2 * min(1, (bar.close - bar.open) / (bar.high - bar.low + 1e-9))
                    elif bar.close < bar.open:
                        # Candelă roșie → majoritate volum de vânzare
                        ratio = 0.4 - 0.2 * min(1, (bar.open - bar.close) / (bar.high - bar.low + 1e-9))
                    else:
                        ratio = 0.5
                    
                    bar.buy_volume = bar.volume * ratio
                    bar.sell_volume = bar.volume * (1 - ratio)
                    bar.delta = bar.buy_volume - bar.sell_volume
                    
        elif source == 'bybit':
            fetcher = BybitFetcher()
            bars = await fetcher.fetch_klines(symbol, interval, start_time, end_time)
            
            # Bybit nu oferă delta direct în klines, folosim estimare
            if include_delta:
                print(f"⚠️ Bybit: Folosim estimare delta bazată pe preț")
                for bar in bars:
                    if bar.close > bar.open:
                        ratio = 0.6
                    elif bar.close < bar.open:
                        ratio = 0.4
                    else:
                        ratio = 0.5
                    bar.buy_volume = bar.volume * ratio
                    bar.sell_volume = bar.volume * (1 - ratio)
                    bar.delta = bar.buy_volume - bar.sell_volume
        else:
            raise ValueError(f"Sursă necunoscută: {source}")
        
        # Salvează în cache
        cache_path = self.get_cache_path(symbol, interval, source)
        self.save_to_csv(bars, cache_path)
        print(f"\n✅ Salvat {len(bars)} bare în {cache_path}")
        
        return bars
    
    def save_to_csv(self, bars: List[OHLCVBar], path: Path):
        """Salvează barele într-un fișier CSV"""
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'open', 'high', 'low', 'close', 
                'volume', 'buy_volume', 'sell_volume', 'delta', 'trades'
            ])
            writer.writeheader()
            for bar in bars:
                writer.writerow(bar.to_dict())
    
    def load_from_csv(self, path: Path) -> List[OHLCVBar]:
        """Încarcă barele din CSV"""
        bars = []
        with open(path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bar = OHLCVBar(
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume']),
                    buy_volume=float(row['buy_volume']) if row.get('buy_volume') else None,
                    sell_volume=float(row['sell_volume']) if row.get('sell_volume') else None,
                    delta=float(row['delta']) if row.get('delta') else None,
                    trades=int(row['trades']) if row.get('trades') else None
                )
                bars.append(bar)
        return bars
    
    def load_or_download(
        self,
        symbol: str,
        interval: str,
        days: int = 30,
        source: str = 'binance',
        force_download: bool = False
    ) -> List[OHLCVBar]:
        """
        Încarcă din cache sau descarcă dacă nu există.
        
        Sincron wrapper pentru download async.
        """
        cache_path = self.get_cache_path(symbol, interval, source)
        
        if cache_path.exists() and not force_download:
            print(f"📂 Încărcare din cache: {cache_path}")
            return self.load_from_csv(cache_path)
        
        # Descarcă async
        return asyncio.run(self.download_data(symbol, interval, days, source))


# ============================================================================
# CLI Interface
# ============================================================================

def main():
    """CLI pentru descărcarea datelor"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Descarcă date OHLCV pentru backtesting OIE MVP"
    )
    parser.add_argument('--source', choices=['binance', 'bybit'], default='binance',
                        help='Sursă date (default: binance)')
    parser.add_argument('--symbol', default='BTCUSDT',
                        help='Simbol trading (default: BTCUSDT)')
    parser.add_argument('--interval', default='1m',
                        help='Interval (1m, 5m, 15m, 1h, 4h, 1d) (default: 1m)')
    parser.add_argument('--days', type=int, default=7,
                        help='Număr zile de date (default: 7)')
    parser.add_argument('--no-delta', action='store_true',
                        help='Nu calcula delta (mai rapid)')
    parser.add_argument('--spot', action='store_true',
                        help='Folosește market spot în loc de futures')
    parser.add_argument('--output', 
                        help='Calea fișierului output (opțional)')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OIE MVP - Data Fetcher pentru Backtesting")
    print("=" * 60)
    
    manager = DataManager()
    
    bars = asyncio.run(manager.download_data(
        symbol=args.symbol,
        interval=args.interval,
        days=args.days,
        source=args.source,
        include_delta=not args.no_delta,
        use_futures=not args.spot
    ))
    
    if args.output:
        manager.save_to_csv(bars, Path(args.output))
        print(f"\n✅ Salvat în: {args.output}")
    
    print("\n📊 Statistici date:")
    print(f"   Total bare: {len(bars)}")
    print(f"   Perioadă: {bars[0].timestamp} → {bars[-1].timestamp}")
    if bars[0].delta is not None:
        total_delta = sum(b.delta for b in bars if b.delta)
        print(f"   Delta total: {total_delta:,.2f}")
    
    print("\n✅ Gata pentru backtesting!")
    print(f"   Folosiți: python -m backend.backtest.backtest_runner --data {manager.get_cache_path(args.symbol, args.interval, args.source)}")


if __name__ == '__main__':
    main()
