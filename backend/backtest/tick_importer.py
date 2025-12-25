"""
OIE MVP - Tick Data Importer
=============================

Importator pentru tick data din diverse surse.

SURSE SUPORTATE:

1. BINANCE (Gratuit)
   - Trades historice din API sau ZIP files
   - Delta REAL calculat din fiecare trade
   - https://data.binance.vision/

2. DUKASCOPY (Gratuit)
   - Forex tick data
   - Istoric lung (10+ ani)
   
3. CSV GENERIC
   - Importă orice CSV cu format compatibil
   
4. TARDIS.DEV (Plătit dar de calitate)
   - Order book + trades
   - Delta real

Utilizare:
    python -m backend.backtest.tick_importer --source binance --symbol BTCUSDT --date 2025-01-15
"""

import os
import csv
import gzip
import zipfile
import asyncio
import aiohttp
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass
from pathlib import Path
import json
from io import BytesIO, StringIO


@dataclass
class TickTrade:
    """O singură tranzacție (tick)"""
    timestamp: datetime
    price: float
    quantity: float
    is_buyer_maker: bool  # True = sell (taker sold), False = buy (taker bought)
    trade_id: int = 0
    
    @property
    def side(self) -> str:
        """Returnează direcția: buy sau sell"""
        return "sell" if self.is_buyer_maker else "buy"
    
    def to_dict(self) -> Dict:
        return {
            'timestamp': self.timestamp.isoformat(),
            'price': self.price,
            'quantity': self.quantity,
            'side': self.side,
            'trade_id': self.trade_id
        }


@dataclass
class AggregatedBar:
    """Bară agregată din tick data cu delta real"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: float
    sell_volume: float
    delta: float
    trades_count: int
    vwap: float  # Volume Weighted Average Price
    
    def to_dict(self) -> Dict:
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
            'trades_count': self.trades_count,
            'vwap': self.vwap
        }


class TickAggregator:
    """Agregă tick data în bare OHLCV cu delta real"""
    
    @staticmethod
    def aggregate_to_bars(
        ticks: List[TickTrade],
        interval_seconds: int = 60
    ) -> List[AggregatedBar]:
        """
        Agregă ticks în bare.
        
        Args:
            ticks: Lista de ticks sortată cronologic
            interval_seconds: Dimensiunea barei în secunde (60 = 1m, 300 = 5m, etc.)
        
        Returns:
            Lista de bare agregate cu delta REAL
        """
        if not ticks:
            return []
        
        bars = []
        current_bar_start = None
        current_ticks = []
        
        for tick in ticks:
            # Calculează începutul barei curente
            ts = tick.timestamp
            bar_start = ts.replace(
                second=0,
                microsecond=0,
                minute=(ts.minute // (interval_seconds // 60)) * (interval_seconds // 60)
            )
            
            if current_bar_start is None:
                current_bar_start = bar_start
            
            # Dacă am trecut la o nouă bară, agreg prev bara
            if bar_start != current_bar_start:
                if current_ticks:
                    bar = TickAggregator._create_bar(current_bar_start, current_ticks)
                    bars.append(bar)
                
                current_bar_start = bar_start
                current_ticks = []
            
            current_ticks.append(tick)
        
        # Ultima bară
        if current_ticks:
            bar = TickAggregator._create_bar(current_bar_start, current_ticks)
            bars.append(bar)
        
        return bars
    
    @staticmethod
    def _create_bar(timestamp: datetime, ticks: List[TickTrade]) -> AggregatedBar:
        """Creează o bară din lista de ticks"""
        prices = [t.price for t in ticks]
        
        buy_volume = sum(t.quantity for t in ticks if not t.is_buyer_maker)
        sell_volume = sum(t.quantity for t in ticks if t.is_buyer_maker)
        total_volume = buy_volume + sell_volume
        
        # VWAP
        value_traded = sum(t.price * t.quantity for t in ticks)
        vwap = value_traded / total_volume if total_volume > 0 else ticks[-1].price
        
        return AggregatedBar(
            timestamp=timestamp,
            open=ticks[0].price,
            high=max(prices),
            low=min(prices),
            close=ticks[-1].price,
            volume=total_volume,
            buy_volume=buy_volume,
            sell_volume=sell_volume,
            delta=buy_volume - sell_volume,  # DELTA REAL!
            trades_count=len(ticks),
            vwap=vwap
        )


class BinanceTickFetcher:
    """
    Descarcă tick data de la Binance.
    
    Surse:
    1. API aggTrades (limitat la 1000 per request)
    2. Historical data download (zip files de pe data.binance.vision)
    """
    
    FUTURES_BASE = "https://fapi.binance.com"
    SPOT_BASE = "https://api.binance.com"
    DATA_VISION = "https://data.binance.vision/data"
    
    def __init__(self, use_futures: bool = True):
        self.use_futures = use_futures
        self.base_url = self.FUTURES_BASE if use_futures else self.SPOT_BASE
    
    async def fetch_from_api(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[TickTrade]:
        """
        Descarcă trades via API.
        
        ATENȚIE: Lent pentru perioade lungi!
        Recomandat doar pentru < 1 oră de date.
        """
        ticks = []
        current_start = int(start_time.timestamp() * 1000)
        end_ms = int(end_time.timestamp() * 1000)
        
        endpoint = f"{self.base_url}/fapi/v1/aggTrades" if self.use_futures else f"{self.base_url}/api/v3/aggTrades"
        
        print(f"📡 Descărcare ticks via API pentru {symbol}...")
        
        async with aiohttp.ClientSession() as session:
            while current_start < end_ms:
                params = {
                    'symbol': symbol.upper(),
                    'startTime': current_start,
                    'endTime': min(current_start + 3600_000, end_ms),
                    'limit': limit
                }
                
                async with session.get(endpoint, params=params) as resp:
                    if resp.status != 200:
                        print(f"⚠️ API error: {await resp.text()}")
                        break
                    
                    trades = await resp.json()
                    
                    if not trades:
                        current_start += 3600_000
                        continue
                    
                    for t in trades:
                        tick = TickTrade(
                            timestamp=datetime.fromtimestamp(t['T'] / 1000),
                            price=float(t['p']),
                            quantity=float(t['q']),
                            is_buyer_maker=t['m'],
                            trade_id=t['a']
                        )
                        ticks.append(tick)
                    
                    current_start = trades[-1]['T'] + 1
                    
                await asyncio.sleep(0.1)  # Rate limit
        
        print(f"✅ Descărcat {len(ticks)} ticks")
        return ticks
    
    async def download_daily_zip(
        self,
        symbol: str,
        trade_date: date,
        data_type: str = "aggTrades"
    ) -> List[TickTrade]:
        """
        Descarcă trades dintr-un fișier ZIP zilnic de pe data.binance.vision
        
        MULT mai rapid pentru date istorice complete!
        
        Args:
            symbol: Simbol (ex: BTCUSDT)
            trade_date: Data pentru care să descarce
            data_type: aggTrades sau trades
        
        URL format:
        https://data.binance.vision/data/futures/um/daily/aggTrades/BTCUSDT/BTCUSDT-aggTrades-2025-01-15.zip
        """
        date_str = trade_date.strftime("%Y-%m-%d")
        
        if self.use_futures:
            url = f"{self.DATA_VISION}/futures/um/daily/{data_type}/{symbol}/{symbol}-{data_type}-{date_str}.zip"
        else:
            url = f"{self.DATA_VISION}/spot/daily/{data_type}/{symbol}/{symbol}-{data_type}-{date_str}.zip"
        
        print(f"📥 Descărcare ZIP: {url}")
        
        ticks = []
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                if resp.status == 404:
                    print(f"⚠️ Nu există date pentru {date_str}")
                    return []
                
                if resp.status != 200:
                    print(f"❌ Eroare: {resp.status}")
                    return []
                
                zip_bytes = await resp.read()
        
        # Parsează ZIP
        try:
            with zipfile.ZipFile(BytesIO(zip_bytes)) as zf:
                for filename in zf.namelist():
                    with zf.open(filename) as f:
                        # CSV în ZIP
                        content = f.read().decode('utf-8')
                        reader = csv.reader(StringIO(content))
                        
                        for row in reader:
                            if len(row) < 6:
                                continue
                            
                            try:
                                # Format: agg_trade_id,price,quantity,first_trade_id,last_trade_id,timestamp,is_buyer_maker
                                tick = TickTrade(
                                    timestamp=datetime.fromtimestamp(int(row[5]) / 1000),
                                    price=float(row[1]),
                                    quantity=float(row[2]),
                                    is_buyer_maker=row[6].lower() == 'true' if len(row) > 6 else False,
                                    trade_id=int(row[0])
                                )
                                ticks.append(tick)
                            except (ValueError, IndexError):
                                continue
        except zipfile.BadZipFile:
            print(f"❌ Fișier ZIP invalid")
            return []
        
        print(f"✅ Parsed {len(ticks)} ticks din {date_str}")
        return ticks
    
    async def download_date_range(
        self,
        symbol: str,
        start_date: date,
        end_date: date
    ) -> List[TickTrade]:
        """Descarcă trades pentru o perioadă"""
        all_ticks = []
        current_date = start_date
        
        while current_date <= end_date:
            ticks = await self.download_daily_zip(symbol, current_date)
            all_ticks.extend(ticks)
            current_date += timedelta(days=1)
        
        # Sortează cronologic
        all_ticks.sort(key=lambda t: t.timestamp)
        
        return all_ticks


class DukascopyTickFetcher:
    """
    Descarcă tick data de la Dukascopy (Forex).
    
    Sursa: https://www.dukascopy.com/swiss/english/marketwatch/historical/
    
    Perechi disponibile: EUR/USD, GBP/USD, USD/JPY, etc.
    """
    
    BASE_URL = "https://datafeed.dukascopy.com/datafeed"
    
    # Mapare simboluri
    SYMBOL_MAP = {
        'EURUSD': 'EURUSD',
        'GBPUSD': 'GBPUSD',
        'USDJPY': 'USDJPY',
        'USDCHF': 'USDCHF',
        'AUDUSD': 'AUDUSD',
        'USDCAD': 'USDCAD',
        'NZDUSD': 'NZDUSD',
        'XAUUSD': 'XAUUSD',  # Gold
        'XAGUSD': 'XAGUSD',  # Silver
    }
    
    async def download_hour(
        self,
        symbol: str,
        year: int,
        month: int,
        day: int,
        hour: int
    ) -> List[TickTrade]:
        """
        Descarcă o oră de tick data.
        
        Dukascopy organizează datele pe ore în format bi5 (comprimat).
        """
        # Convertește simbolul
        duka_symbol = self.SYMBOL_MAP.get(symbol.upper(), symbol.upper())
        
        # URL format: https://datafeed.dukascopy.com/datafeed/EURUSD/2024/00/15/00h_ticks.bi5
        # Luna e 0-indexed!
        url = f"{self.BASE_URL}/{duka_symbol}/{year}/{month-1:02d}/{day:02d}/{hour:02d}h_ticks.bi5"
        
        print(f"📥 Dukascopy: {url}")
        
        # Dukascopy folosește format binar, e complex de parsat
        # Pentru simplitate, recomand folosirea bibliotecii `duka` sau descărcare manuală
        
        print("⚠️ Dukascopy bi5 format necesită bibliotecă specială sau descărcare manuală")
        print("   Recomandare: Folosiți https://www.dukascopy.com/swiss/english/marketwatch/historical/")
        
        return []


class GenericCSVImporter:
    """
    Importă tick data din orice CSV cu format compatibil.
    
    Formate suportate:
    1. Standard: timestamp,price,quantity,side
    2. Binance: timestamp,price,quantity,is_buyer_maker
    3. Custom: specificat via column mapping
    """
    
    @staticmethod
    def import_csv(
        filepath: str,
        timestamp_col: str = 'timestamp',
        price_col: str = 'price',
        quantity_col: str = 'quantity',
        side_col: str = 'side',  # 'buy'/'sell' sau 'is_buyer_maker' (true/false)
        timestamp_format: str = None,  # None = auto-detect
        has_header: bool = True
    ) -> List[TickTrade]:
        """
        Importă ticks din CSV.
        
        Args:
            filepath: Calea către fișier
            timestamp_col: Numele coloanei timestamp
            price_col: Numele coloanei preț
            quantity_col: Numele coloanei cantitate
            side_col: Numele coloanei side/direction
            timestamp_format: Format datetime (ex: '%Y-%m-%d %H:%M:%S.%f')
            has_header: Dacă CSV-ul are header
        """
        ticks = []
        
        with open(filepath, 'r', encoding='utf-8') as f:
            if has_header:
                reader = csv.DictReader(f)
            else:
                # Fără header, folosim index-uri
                reader = csv.reader(f)
            
            for row in reader:
                try:
                    if has_header:
                        ts_raw = row[timestamp_col]
                        price = float(row[price_col])
                        quantity = float(row[quantity_col])
                        side_raw = row.get(side_col, 'buy')
                    else:
                        # Presupunem format: timestamp, price, quantity, side
                        ts_raw = row[0]
                        price = float(row[1])
                        quantity = float(row[2])
                        side_raw = row[3] if len(row) > 3 else 'buy'
                    
                    # Parse timestamp
                    if timestamp_format:
                        ts = datetime.strptime(ts_raw, timestamp_format)
                    else:
                        # Auto-detect
                        try:
                            ts = datetime.fromisoformat(ts_raw.replace('Z', '+00:00'))
                        except:
                            try:
                                ts = datetime.fromtimestamp(float(ts_raw) / 1000)
                            except:
                                ts = datetime.strptime(ts_raw, '%Y-%m-%d %H:%M:%S')
                    
                    # Fă timestamp-ul naive
                    if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                        ts = ts.replace(tzinfo=None)
                    
                    # Parse side
                    side_lower = str(side_raw).lower()
                    if side_lower in ['true', 'sell', 's', '1']:
                        is_buyer_maker = True
                    else:
                        is_buyer_maker = False
                    
                    tick = TickTrade(
                        timestamp=ts,
                        price=price,
                        quantity=quantity,
                        is_buyer_maker=is_buyer_maker
                    )
                    ticks.append(tick)
                    
                except (ValueError, KeyError, IndexError) as e:
                    continue
        
        print(f"✅ Importat {len(ticks)} ticks din {filepath}")
        return ticks


class TickDataManager:
    """Manager complet pentru tick data"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'ticks')
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def get_tick_cache_path(self, symbol: str, trade_date: date) -> Path:
        """Returnează path tick data"""
        date_str = trade_date.strftime("%Y%m%d")
        return self.data_dir / f"ticks_{symbol}_{date_str}.csv"
    
    def get_bar_cache_path(self, symbol: str, interval: str, trade_date: date) -> Path:
        """Returnează path bare agregate"""
        date_str = trade_date.strftime("%Y%m%d")
        return self.data_dir / f"bars_{symbol}_{interval}_{date_str}.csv"
    
    def save_ticks(self, ticks: List[TickTrade], filepath: Path):
        """Salvează ticks în CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'price', 'quantity', 'side', 'trade_id'
            ])
            writer.writeheader()
            for tick in ticks:
                writer.writerow(tick.to_dict())
        print(f"💾 Salvat {len(ticks)} ticks în {filepath}")
    
    def save_bars(self, bars: List[AggregatedBar], filepath: Path):
        """Salvează bare în CSV"""
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'buy_volume', 'sell_volume', 'delta',
                'trades_count', 'vwap'
            ])
            writer.writeheader()
            for bar in bars:
                writer.writerow(bar.to_dict())
        print(f"💾 Salvat {len(bars)} bare în {filepath}")
    
    def load_bars(self, filepath: Path) -> List[AggregatedBar]:
        """Încarcă bare din CSV"""
        bars = []
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                bar = AggregatedBar(
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    open=float(row['open']),
                    high=float(row['high']),
                    low=float(row['low']),
                    close=float(row['close']),
                    volume=float(row['volume']),
                    buy_volume=float(row['buy_volume']),
                    sell_volume=float(row['sell_volume']),
                    delta=float(row['delta']),
                    trades_count=int(row['trades_count']),
                    vwap=float(row['vwap'])
                )
                bars.append(bar)
        return bars
    
    async def download_and_aggregate(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
        interval_seconds: int = 60,
        source: str = 'binance'
    ) -> List[AggregatedBar]:
        """
        Descarcă tick data și agregează în bare.
        
        Args:
            symbol: Simbol (ex: BTCUSDT)
            start_date: Data start
            end_date: Data end
            interval_seconds: Dimensiune bară (60 = 1m, 300 = 5m)
            source: Sursă date (binance, dukascopy, csv)
        
        Returns:
            Lista de bare cu delta REAL
        """
        print(f"\n📊 Download tick data pentru {symbol}")
        print(f"   Perioadă: {start_date} → {end_date}")
        print(f"   Interval agregare: {interval_seconds}s")
        
        # Descarcă ticks
        if source == 'binance':
            fetcher = BinanceTickFetcher(use_futures=True)
            ticks = await fetcher.download_date_range(symbol, start_date, end_date)
        else:
            print(f"❌ Sursă necunoscută: {source}")
            return []
        
        if not ticks:
            print("❌ Nu s-au găsit ticks")
            return []
        
        print(f"\n🔄 Agregare {len(ticks)} ticks în bare...")
        
        # Agregează în bare
        bars = TickAggregator.aggregate_to_bars(ticks, interval_seconds)
        
        print(f"✅ Creat {len(bars)} bare cu delta REAL")
        
        # Statistici
        total_volume = sum(b.volume for b in bars)
        total_delta = sum(b.delta for b in bars)
        buy_vol = sum(b.buy_volume for b in bars)
        sell_vol = sum(b.sell_volume for b in bars)
        
        print(f"\n📈 STATISTICI:")
        print(f"   Volum Total: {total_volume:,.2f}")
        print(f"   Buy Volume:  {buy_vol:,.2f} ({buy_vol/total_volume*100:.1f}%)")
        print(f"   Sell Volume: {sell_vol:,.2f} ({sell_vol/total_volume*100:.1f}%)")
        print(f"   Delta Net:   {total_delta:+,.2f}")
        
        return bars


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Tick Data Importer")
    parser.add_argument('--source', choices=['binance', 'csv'], default='binance',
                        help='Sursă date')
    parser.add_argument('--symbol', default='BTCUSDT',
                        help='Simbol (ex: BTCUSDT)')
    parser.add_argument('--date', default=None,
                        help='Data (YYYY-MM-DD) sau "today"')
    parser.add_argument('--days', type=int, default=1,
                        help='Număr zile de descărcat')
    parser.add_argument('--interval', type=int, default=60,
                        help='Interval agregare în secunde (60=1m, 300=5m)')
    parser.add_argument('--csv-file',
                        help='Calea către CSV pentru import manual')
    parser.add_argument('--output',
                        help='Calea output pentru bare agregate')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OIE MVP - Tick Data Importer")
    print("=" * 60)
    
    manager = TickDataManager()
    
    if args.source == 'csv' and args.csv_file:
        # Import din CSV
        ticks = GenericCSVImporter.import_csv(args.csv_file)
        bars = TickAggregator.aggregate_to_bars(ticks, args.interval)
        
        if args.output:
            manager.save_bars(bars, Path(args.output))
    
    elif args.source == 'binance':
        # Descarcă de pe Binance
        if args.date:
            if args.date.lower() == 'today':
                start_date = date.today()
            else:
                start_date = datetime.strptime(args.date, '%Y-%m-%d').date()
        else:
            start_date = date.today() - timedelta(days=1)
        
        end_date = start_date + timedelta(days=args.days - 1)
        
        bars = asyncio.run(manager.download_and_aggregate(
            symbol=args.symbol,
            start_date=start_date,
            end_date=end_date,
            interval_seconds=args.interval,
            source='binance'
        ))
        
        if bars and args.output:
            manager.save_bars(bars, Path(args.output))
        elif bars:
            # Salvează automat
            interval_name = f"{args.interval//60}m" if args.interval >= 60 else f"{args.interval}s"
            output_path = manager.data_dir / f"ticks_aggregated_{args.symbol}_{interval_name}_{start_date}.csv"
            manager.save_bars(bars, output_path)
            print(f"\n💾 Salvat în: {output_path}")
    
    print("\n✅ Gata!")


if __name__ == '__main__':
    main()
