"""
OIE MVP - Indices Data Fetcher
===============================

Descarcă date OHLCV pentru indici bursieri (S&P 500, Nasdaq, Dow Jones, etc.)

Surse suportate:
- Yahoo Finance (via yfinance) - Gratuit, date zilnice și intraday

Simboluri comune:
- ^GSPC = S&P 500 (US500)
- ^NDX = Nasdaq 100 (US100)
- ^DJI = Dow Jones Industrial (US30)
- ^RUT = Russell 2000
- ^VIX = Volatility Index
- ^FTSE = FTSE 100 (UK100)
- ^GDAXI = DAX (GER40)
- ^N225 = Nikkei 225 (JPN225)

Utilizare:
    python -m backend.backtest.indices_fetcher --symbol ^GSPC --interval 15m --days 60
"""

import os
import csv
import yfinance as yf
from datetime import datetime, timedelta
from typing import List, Optional, Dict
from dataclasses import dataclass
from pathlib import Path
import pandas as pd


@dataclass
class OHLCVBar:
    """Structura bare OHLCV"""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float
    buy_volume: Optional[float] = None
    sell_volume: Optional[float] = None
    delta: Optional[float] = None

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
            'delta': self.delta
        }


# Mapare simboluri comune la Yahoo Finance
SYMBOL_MAP = {
    # US Indices
    'US500': '^GSPC',      # S&P 500
    'SPX': '^GSPC',
    'SP500': '^GSPC',
    'US100': '^NDX',       # Nasdaq 100
    'NAS100': '^NDX',
    'NASDAQ': '^IXIC',     # Nasdaq Composite
    'US30': '^DJI',        # Dow Jones
    'DOW': '^DJI',
    'RUSSELL': '^RUT',     # Russell 2000
    'VIX': '^VIX',         # Volatility Index
    
    # European Indices
    'UK100': '^FTSE',      # FTSE 100
    'FTSE': '^FTSE',
    'GER40': '^GDAXI',     # DAX
    'DAX': '^GDAXI',
    'FRA40': '^FCHI',      # CAC 40
    'CAC': '^FCHI',
    'EU50': '^STOXX50E',   # Euro Stoxx 50
    
    # Asian Indices
    'JPN225': '^N225',     # Nikkei 225
    'NIKKEI': '^N225',
    'HK50': '^HSI',        # Hang Seng
    'CN50': '000300.SS',   # China CSI 300
    
    # ETFs (can use as proxies)
    'SPY': 'SPY',          # S&P 500 ETF
    'QQQ': 'QQQ',          # Nasdaq 100 ETF
    'DIA': 'DIA',          # Dow Jones ETF
    'IWM': 'IWM',          # Russell 2000 ETF
    
    # Futures - nu funcționează direct cu yfinance
    # Pentru futures intraday, folosiți alte surse
}


class YahooFinanceFetcher:
    """
    Descarcă date de la Yahoo Finance.
    
    Limitări yfinance:
    - Intraday (1m, 5m, 15m, 30m, 1h): max 60 zile istoric
    - Daily și mai mare: istoric complet disponibil
    """
    
    VALID_INTERVALS = ['1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo']
    
    def __init__(self):
        pass
    
    def resolve_symbol(self, symbol: str) -> str:
        """Convertește simboluri comune la formatul Yahoo Finance"""
        upper = symbol.upper()
        if upper in SYMBOL_MAP:
            return SYMBOL_MAP[upper]
        return symbol  # Returnează așa cum e
    
    def get_max_days(self, interval: str) -> int:
        """Returnează numărul maxim de zile disponibile pentru un interval"""
        if interval in ['1m']:
            return 7  # Max 7 zile pentru 1m
        elif interval in ['2m', '5m', '15m', '30m', '60m', '90m', '1h']:
            return 60  # Max 60 zile pentru intraday
        else:
            return 3650  # ~10 ani pentru daily
    
    def fetch(
        self, 
        symbol: str, 
        interval: str = '15m',
        days: int = 60
    ) -> List[OHLCVBar]:
        """
        Descarcă date OHLCV.
        
        Args:
            symbol: Simbol sau shorthand (US500, SP500, etc.)
            interval: Interval (1m, 5m, 15m, 30m, 1h, 1d, etc.)
            days: Număr de zile (limitat pentru intraday)
        
        Returns:
            Lista de bare OHLCV
        """
        # Rezolvă simbolul
        yf_symbol = self.resolve_symbol(symbol)
        
        # Verifică limitări
        max_days = self.get_max_days(interval)
        if days > max_days:
            print(f"⚠️ Pentru interval {interval}, max {max_days} zile disponibile. Ajustăm la {max_days}.")
            days = max_days
        
        print(f"\n📊 Descărcare {symbol} ({yf_symbol}) interval {interval}")
        print(f"   Perioadă: {days} zile")
        
        # Descarcă
        ticker = yf.Ticker(yf_symbol)
        
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)
        
        try:
            df = ticker.history(
                start=start_date,
                end=end_date,
                interval=interval,
                auto_adjust=True
            )
        except Exception as e:
            print(f"❌ Eroare la descărcare: {e}")
            return []
        
        if df.empty:
            print(f"❌ Nu s-au găsit date pentru {symbol}")
            return []
        
        # Convertește la OHLCVBar
        bars = []
        for idx, row in df.iterrows():
            # Handle timezone
            if hasattr(idx, 'tz_localize'):
                ts = idx.to_pydatetime()
            else:
                ts = idx
            
            # Fă timestamp-ul naive dacă e timezone-aware
            if hasattr(ts, 'tzinfo') and ts.tzinfo is not None:
                ts = ts.replace(tzinfo=None)
            
            # Estimăm buy/sell volume din direcția candelei
            vol = float(row['Volume']) if row['Volume'] and row['Volume'] > 0 else 0
            o, c = float(row['Open']), float(row['Close'])
            
            if c > o:
                ratio = 0.55 + 0.15 * min(1, (c - o) / (float(row['High']) - float(row['Low']) + 1e-9))
            elif c < o:
                ratio = 0.45 - 0.15 * min(1, (o - c) / (float(row['High']) - float(row['Low']) + 1e-9))
            else:
                ratio = 0.5
            
            bar = OHLCVBar(
                timestamp=ts,
                open=o,
                high=float(row['High']),
                low=float(row['Low']),
                close=c,
                volume=vol,
                buy_volume=vol * ratio,
                sell_volume=vol * (1 - ratio),
                delta=vol * ratio - vol * (1 - ratio)
            )
            bars.append(bar)
        
        print(f"✅ Descărcat {len(bars)} bare")
        print(f"   De la: {bars[0].timestamp}")
        print(f"   Până la: {bars[-1].timestamp}")
        
        return bars


class IndicesDataManager:
    """Manager pentru date indici"""
    
    def __init__(self, data_dir: str = None):
        if data_dir is None:
            data_dir = os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'historical')
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.fetcher = YahooFinanceFetcher()
    
    def get_cache_path(self, symbol: str, interval: str) -> Path:
        """Returnează path-ul cache"""
        # Curăță simbolul pentru nume fișier
        clean_symbol = symbol.replace('^', '').replace('.', '_').upper()
        return self.data_dir / f"yahoo_{clean_symbol}_{interval}.csv"
    
    def download(
        self,
        symbol: str,
        interval: str = '15m',
        days: int = 60
    ) -> List[OHLCVBar]:
        """Descarcă și salvează date"""
        bars = self.fetcher.fetch(symbol, interval, days)
        
        if not bars:
            return []
        
        # Salvează
        cache_path = self.get_cache_path(symbol, interval)
        self.save_to_csv(bars, cache_path)
        print(f"\n💾 Salvat în: {cache_path}")
        
        return bars
    
    def save_to_csv(self, bars: List[OHLCVBar], path: Path):
        """Salvează în CSV"""
        with open(path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=[
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'buy_volume', 'sell_volume', 'delta'
            ])
            writer.writeheader()
            for bar in bars:
                writer.writerow(bar.to_dict())
    
    def load_from_csv(self, path: Path) -> List[OHLCVBar]:
        """Încarcă din CSV"""
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
                    delta=float(row['delta']) if row.get('delta') else None
                )
                bars.append(bar)
        return bars


def print_available_indices():
    """Afișează indicii disponibili"""
    print("\n📊 INDICI DISPONIBILI:")
    print("=" * 60)
    
    print("\n🇺🇸 INDICI US:")
    print("   US500 / SPX / SP500  → S&P 500 (^GSPC)")
    print("   US100 / NAS100       → Nasdaq 100 (^NDX)")
    print("   NASDAQ               → Nasdaq Composite (^IXIC)")
    print("   US30 / DOW           → Dow Jones (^DJI)")
    print("   RUSSELL              → Russell 2000 (^RUT)")
    print("   VIX                  → Volatility Index (^VIX)")
    
    print("\n🇪🇺 INDICI EUROPENI:")
    print("   UK100 / FTSE         → FTSE 100 (^FTSE)")
    print("   GER40 / DAX          → DAX (^GDAXI)")
    print("   FRA40 / CAC          → CAC 40 (^FCHI)")
    print("   EU50                 → Euro Stoxx 50 (^STOXX50E)")
    
    print("\n🌏 INDICI ASIATICI:")
    print("   JPN225 / NIKKEI      → Nikkei 225 (^N225)")
    print("   HK50                 → Hang Seng (^HSI)")
    
    print("\n📈 ETF-uri (Proxy pentru indici):")
    print("   SPY                  → S&P 500 ETF")
    print("   QQQ                  → Nasdaq 100 ETF")
    print("   DIA                  → Dow Jones ETF")
    print("   IWM                  → Russell 2000 ETF")
    
    print("\n⚠️ LIMITĂRI:")
    print("   - Intervale intraday (1m-1h): max 60 zile istoric")
    print("   - Interval 1m: max 7 zile")
    print("   - Date daily: istoric complet disponibil")
    print("=" * 60)


def main():
    """CLI pentru descărcarea datelor de indici"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Descarcă date OHLCV pentru indici bursieri"
    )
    parser.add_argument('--symbol', default='US500',
                        help='Simbol index (US500, US100, US30, DAX, etc.)')
    parser.add_argument('--interval', default='15m',
                        help='Interval (1m, 5m, 15m, 30m, 1h, 1d)')
    parser.add_argument('--days', type=int, default=60,
                        help='Număr zile (default: 60, max 60 pentru intraday)')
    parser.add_argument('--list', action='store_true',
                        help='Afișează lista de indici disponibili')
    
    args = parser.parse_args()
    
    print("=" * 60)
    print("OIE MVP - Indices Data Fetcher")
    print("=" * 60)
    
    if args.list:
        print_available_indices()
        return
    
    manager = IndicesDataManager()
    bars = manager.download(args.symbol, args.interval, args.days)
    
    if bars:
        print("\n📊 STATISTICI:")
        opens = [b.open for b in bars]
        closes = [b.close for b in bars]
        print(f"   Preț Start: {opens[0]:.2f}")
        print(f"   Preț Final: {closes[-1]:.2f}")
        pct_change = ((closes[-1] - opens[0]) / opens[0]) * 100
        print(f"   Schimbare: {pct_change:+.2f}%")
        print(f"   Volum Total: {sum(b.volume for b in bars):,.0f}")
        
        print("\n✅ Gata pentru backtesting!")
        cache_path = manager.get_cache_path(args.symbol, args.interval)
        print(f"   python -m backend.backtest.backtest_runner --data {cache_path}")


if __name__ == '__main__':
    main()
