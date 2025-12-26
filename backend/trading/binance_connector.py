"""
OIE MVP - Binance Testnet Paper Trading Connector
==================================================

Conectare la Binance Futures Testnet pentru paper trading.
Suportă:
- Market orders (LONG/SHORT)
- Stop Loss & Take Profit orders
- Position tracking
- Balance management
"""

import os
import time
import hmac
import hashlib
import asyncio
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from enum import Enum
import aiohttp
from urllib.parse import urlencode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class OrderSide(Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(Enum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP_MARKET = "STOP_MARKET"
    TAKE_PROFIT_MARKET = "TAKE_PROFIT_MARKET"


class PositionSide(Enum):
    LONG = "LONG"
    SHORT = "SHORT"
    BOTH = "BOTH"


@dataclass
class Position:
    """Reprezentare poziție deschisă"""
    symbol: str
    side: str  # LONG or SHORT
    entry_price: float
    quantity: float
    unrealized_pnl: float = 0.0
    leverage: int = 1
    liquidation_price: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'symbol': self.symbol,
            'side': self.side,
            'entry_price': self.entry_price,
            'quantity': self.quantity,
            'unrealized_pnl': self.unrealized_pnl,
            'leverage': self.leverage,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class Order:
    """Reprezentare ordin"""
    order_id: str
    symbol: str
    side: str
    type: str
    quantity: float
    price: Optional[float] = None
    stop_price: Optional[float] = None
    status: str = "NEW"
    timestamp: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'type': self.type,
            'quantity': self.quantity,
            'price': self.price,
            'stop_price': self.stop_price,
            'status': self.status,
            'timestamp': self.timestamp.isoformat()
        }


@dataclass
class TradeResult:
    """Rezultat trade executat"""
    success: bool
    order_id: Optional[str] = None
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    price: float = 0.0
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'success': self.success,
            'order_id': self.order_id,
            'symbol': self.symbol,
            'side': self.side,
            'quantity': self.quantity,
            'price': self.price,
            'error': self.error
        }


class BinanceTestnetConnector:
    """
    Connector pentru Binance Futures Testnet

    Usage:
        connector = BinanceTestnetConnector()
        await connector.connect()

        # Open LONG
        result = await connector.open_long("BTCUSDT", 0.001)

        # Open SHORT
        result = await connector.open_short("BTCUSDT", 0.001)

        # Close position
        await connector.close_position("BTCUSDT")
    """

    BASE_URL = "https://testnet.binancefuture.com"
    WS_URL = "wss://stream.binancefuture.com/ws"

    def __init__(self, api_key: str = None, api_secret: str = None):
        self.api_key = api_key or os.getenv("BINANCE_TESTNET_API_KEY")
        self.api_secret = api_secret or os.getenv("BINANCE_TESTNET_SECRET")

        if not self.api_key or not self.api_secret:
            raise ValueError("API Key și Secret sunt necesare. Setează în .env sau pasează ca argumente.")

        self.session: Optional[aiohttp.ClientSession] = None
        self.positions: Dict[str, Position] = {}
        self.orders: Dict[str, Order] = {}
        self.balance: float = 0.0
        self.connected: bool = False
        self.symbol_info: Dict[str, Dict] = {}  # Cache for symbol precision info
    
    def _generate_signature(self, params: Dict[str, Any]) -> str:
        """Generează semnătura HMAC SHA256"""
        query_string = urlencode(params)
        signature = hmac.new(
            self.api_secret.encode('utf-8'),
            query_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        return signature
    
    def _get_timestamp(self) -> int:
        """Returnează timestamp în millisecunde"""
        return int(time.time() * 1000)
    
    async def connect(self):
        """Inițializează conexiunea"""
        if self.session is None:
            self.session = aiohttp.ClientSession(headers={
                'X-MBX-APIKEY': self.api_key
            })
        
        # Test conexiunea
        try:
            account = await self.get_account()
            if account:
                self.connected = True
                print(f"[OK] Connected to Binance Testnet")
                print(f"   Balance: ${self.balance:,.2f} USDT")
                return True
        except Exception as e:
            print(f"[ERROR] Connection failed: {e}")
            return False
        
        return False
    
    async def disconnect(self):
        """Închide conexiunea"""
        if self.session:
            await self.session.close()
            self.session = None
        self.connected = False
    
    async def _request(self, method: str, endpoint: str, params: Dict = None, signed: bool = False) -> Dict:
        """Execută request HTTP"""
        if not self.session:
            await self.connect()
        
        url = f"{self.BASE_URL}{endpoint}"
        params = params or {}
        
        if signed:
            params['timestamp'] = self._get_timestamp()
            params['signature'] = self._generate_signature(params)
        
        try:
            if method == 'GET':
                async with self.session.get(url, params=params) as response:
                    data = await response.json()
                    if response.status != 200:
                        print(f"API Error: {data}")
                    return data
            elif method == 'POST':
                async with self.session.post(url, params=params) as response:
                    data = await response.json()
                    if response.status != 200:
                        print(f"API Error: {data}")
                    return data
            elif method == 'DELETE':
                async with self.session.delete(url, params=params) as response:
                    data = await response.json()
                    return data
        except Exception as e:
            print(f"Request error: {e}")
            return {'error': str(e)}
    
    async def get_account(self) -> Dict:
        """Obține informații cont"""
        data = await self._request('GET', '/fapi/v2/account', signed=True)
        
        if 'totalWalletBalance' in data:
            self.balance = float(data['totalWalletBalance'])
            
            # Update positions
            for pos in data.get('positions', []):
                if float(pos['positionAmt']) != 0:
                    self.positions[pos['symbol']] = Position(
                        symbol=pos['symbol'],
                        side='LONG' if float(pos['positionAmt']) > 0 else 'SHORT',
                        entry_price=float(pos['entryPrice']),
                        quantity=abs(float(pos['positionAmt'])),
                        unrealized_pnl=float(pos['unrealizedProfit']),
                        leverage=int(pos['leverage'])
                    )
        
        return data
    
    async def get_balance(self) -> float:
        """Obține balanța USDT"""
        await self.get_account()
        return self.balance
    
    async def get_price(self, symbol: str) -> float:
        """Obține prețul curent"""
        data = await self._request('GET', '/fapi/v1/ticker/price', {'symbol': symbol})
        return float(data.get('price', 0))

    async def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        Obține informații despre un simbol (precision, min qty, step size)
        Cached pentru performanță.
        """
        if symbol in self.symbol_info:
            return self.symbol_info[symbol]

        data = await self._request('GET', '/fapi/v1/exchangeInfo')

        if 'symbols' in data:
            for sym in data['symbols']:
                sym_name = sym['symbol']
                # Extract quantity precision from LOT_SIZE filter
                qty_precision = 3  # default
                min_qty = 0.001
                step_size = 0.001
                price_precision = 2

                for f in sym.get('filters', []):
                    if f['filterType'] == 'LOT_SIZE':
                        min_qty = float(f['minQty'])
                        step_size = float(f['stepSize'])
                        # Calculate precision from step size
                        step_str = f['stepSize'].rstrip('0')
                        if '.' in step_str:
                            qty_precision = len(step_str.split('.')[1])
                        else:
                            qty_precision = 0
                    elif f['filterType'] == 'PRICE_FILTER':
                        tick_size = f['tickSize'].rstrip('0')
                        if '.' in tick_size:
                            price_precision = len(tick_size.split('.')[1])
                        else:
                            price_precision = 0

                self.symbol_info[sym_name] = {
                    'qty_precision': qty_precision,
                    'min_qty': min_qty,
                    'step_size': step_size,
                    'price_precision': price_precision
                }

        return self.symbol_info.get(symbol, {
            'qty_precision': 3,
            'min_qty': 0.001,
            'step_size': 0.001,
            'price_precision': 2
        })

    def round_quantity(self, symbol: str, quantity: float) -> float:
        """Round quantity to symbol's precision"""
        info = self.symbol_info.get(symbol, {'qty_precision': 3, 'step_size': 0.001})
        precision = info['qty_precision']
        step_size = info['step_size']

        # Round to step size
        quantity = round(quantity / step_size) * step_size
        # Round to precision
        return round(quantity, precision)

    def round_price(self, symbol: str, price: float) -> float:
        """Round price to symbol's precision"""
        info = self.symbol_info.get(symbol, {'price_precision': 2})
        return round(price, info['price_precision'])
    
    async def get_position(self, symbol: str) -> Optional[Position]:
        """Obține poziția pentru un simbol"""
        await self.get_account()
        return self.positions.get(symbol)
    
    async def set_leverage(self, symbol: str, leverage: int) -> bool:
        """Setează leverage"""
        data = await self._request('POST', '/fapi/v1/leverage', {
            'symbol': symbol,
            'leverage': leverage
        }, signed=True)
        
        return 'leverage' in data
    
    async def open_long(self, symbol: str, quantity: float, 
                        stop_loss: float = None, take_profit: float = None) -> TradeResult:
        """
        Deschide poziție LONG
        
        Args:
            symbol: Trading pair (ex: BTCUSDT)
            quantity: Cantitate în BTC
            stop_loss: Preț stop loss (opțional)
            take_profit: Preț take profit (opțional)
        """
        return await self._open_position(symbol, quantity, OrderSide.BUY, stop_loss, take_profit)
    
    async def open_short(self, symbol: str, quantity: float,
                         stop_loss: float = None, take_profit: float = None) -> TradeResult:
        """
        Deschide poziție SHORT
        
        Args:
            symbol: Trading pair (ex: BTCUSDT)
            quantity: Cantitate în BTC
            stop_loss: Preț stop loss (opțional)
            take_profit: Preț take profit (opțional)
        """
        return await self._open_position(symbol, quantity, OrderSide.SELL, stop_loss, take_profit)
    
    async def _open_position(self, symbol: str, quantity: float, side: OrderSide,
                             stop_loss: float = None, take_profit: float = None) -> TradeResult:
        """Deschide poziție"""

        # Market order
        params = {
            'symbol': symbol,
            'side': side.value,
            'type': OrderType.MARKET.value,
            'quantity': quantity
        }

        data = await self._request('POST', '/fapi/v1/order', params, signed=True)

        if 'orderId' in data:
            order_id = str(data['orderId'])

            # Get actual execution price - try multiple sources
            exec_price = 0.0

            # 1. Try avgPrice from response (may not always be present for MARKET orders)
            if 'avgPrice' in data and float(data['avgPrice']) > 0:
                exec_price = float(data['avgPrice'])
                print(f"   [DEBUG] Got price from avgPrice: ${exec_price:,.2f}")

            # 2. If not, calculate from fills (if present)
            if exec_price == 0 and 'fills' in data and len(data['fills']) > 0:
                total_qty = 0.0
                total_value = 0.0
                for fill in data['fills']:
                    qty = float(fill.get('qty', 0))
                    price = float(fill.get('price', 0))
                    total_qty += qty
                    total_value += qty * price
                if total_qty > 0:
                    exec_price = total_value / total_qty
                    print(f"   [DEBUG] Got price from fills: ${exec_price:,.2f}")

            # 3. If still no price, query the order status to get avgPrice (with retry)
            if exec_price == 0:
                for attempt in range(3):
                    await asyncio.sleep(0.5 * (attempt + 1))  # Increasing delay: 0.5s, 1s, 1.5s
                    order_data = await self._request('GET', '/fapi/v1/order', {
                        'symbol': symbol,
                        'orderId': order_id
                    }, signed=True)
                    if 'avgPrice' in order_data and float(order_data['avgPrice']) > 0:
                        exec_price = float(order_data['avgPrice'])
                        print(f"   [DEBUG] Got price from order query (attempt {attempt+1}): ${exec_price:,.2f}")
                        break

            # 4. Query the position for entry price (most reliable for futures)
            if exec_price == 0:
                await asyncio.sleep(0.3)
                position = await self.get_position(symbol)
                if position and position.entry_price > 0:
                    exec_price = position.entry_price
                    print(f"   [DEBUG] Got price from position: ${exec_price:,.2f}")

            # 5. Final fallback: get current market price (ALWAYS do this if price is still 0)
            if exec_price == 0:
                exec_price = await self.get_price(symbol)
                print(f"   [WARNING] Using market price as fallback: ${exec_price:,.2f}")

            result = TradeResult(
                success=True,
                order_id=order_id,
                symbol=symbol,
                side=side.value,
                quantity=quantity,
                price=exec_price
            )

            print(f"[OK] {side.value} {quantity} {symbol} @ ${result.price:,.2f}")

            # Plasează SL/TP dacă sunt specificate
            if stop_loss:
                await self._place_stop_loss(symbol, quantity, stop_loss, side)
            if take_profit:
                await self._place_take_profit(symbol, quantity, take_profit, side)

            return result
        else:
            return TradeResult(
                success=False,
                error=data.get('msg', 'Unknown error')
            )
    
    async def _place_stop_loss(self, symbol: str, quantity: float, price: float, entry_side: OrderSide):
        """Plasează stop loss order"""
        # SL e în direcția opusă intrării
        sl_side = OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY

        # Round price to symbol's precision
        price = self.round_price(symbol, price)

        params = {
            'symbol': symbol,
            'side': sl_side.value,
            'type': OrderType.STOP_MARKET.value,
            'stopPrice': price,
            'closePosition': 'true'
        }

        data = await self._request('POST', '/fapi/v1/order', params, signed=True)

        if 'orderId' in data:
            print(f"   SL set @ ${price:,.4f}")
            return True
        return False

    async def _place_take_profit(self, symbol: str, quantity: float, price: float, entry_side: OrderSide):
        """Plasează take profit order"""
        # TP e în direcția opusă intrării
        tp_side = OrderSide.SELL if entry_side == OrderSide.BUY else OrderSide.BUY

        # Round price to symbol's precision
        price = self.round_price(symbol, price)

        params = {
            'symbol': symbol,
            'side': tp_side.value,
            'type': OrderType.TAKE_PROFIT_MARKET.value,
            'stopPrice': price,
            'closePosition': 'true'
        }

        data = await self._request('POST', '/fapi/v1/order', params, signed=True)

        if 'orderId' in data:
            print(f"   TP set @ ${price:,.4f}")
            return True
        return False
    
    async def close_position(self, symbol: str) -> TradeResult:
        """Închide poziția pentru un simbol"""
        position = await self.get_position(symbol)

        if not position:
            return TradeResult(success=False, error="No position to close")

        # Close în direcția opusă
        side = OrderSide.SELL if position.side == 'LONG' else OrderSide.BUY

        params = {
            'symbol': symbol,
            'side': side.value,
            'type': OrderType.MARKET.value,
            'quantity': position.quantity
        }

        data = await self._request('POST', '/fapi/v1/order', params, signed=True)

        if 'orderId' in data:
            order_id = str(data['orderId'])

            # Get actual execution price - try multiple sources
            exec_price = 0.0

            # 1. Try avgPrice from response
            if 'avgPrice' in data and float(data['avgPrice']) > 0:
                exec_price = float(data['avgPrice'])
                print(f"   [DEBUG] Close price from avgPrice: ${exec_price:,.2f}")

            # 2. Calculate from fills if present
            if exec_price == 0 and 'fills' in data and len(data['fills']) > 0:
                total_qty = 0.0
                total_value = 0.0
                for fill in data['fills']:
                    qty = float(fill.get('qty', 0))
                    price = float(fill.get('price', 0))
                    total_qty += qty
                    total_value += qty * price
                if total_qty > 0:
                    exec_price = total_value / total_qty
                    print(f"   [DEBUG] Close price from fills: ${exec_price:,.2f}")

            # 3. Query order status for avgPrice (with retry)
            if exec_price == 0:
                for attempt in range(3):
                    await asyncio.sleep(0.5 * (attempt + 1))
                    order_data = await self._request('GET', '/fapi/v1/order', {
                        'symbol': symbol,
                        'orderId': order_id
                    }, signed=True)
                    if 'avgPrice' in order_data and float(order_data['avgPrice']) > 0:
                        exec_price = float(order_data['avgPrice'])
                        print(f"   [DEBUG] Close price from order query (attempt {attempt+1}): ${exec_price:,.2f}")
                        break

            # 4. Fallback to current price (ALWAYS if still 0)
            if exec_price == 0:
                exec_price = await self.get_price(symbol)
                print(f"   [WARNING] Close using market price as fallback: ${exec_price:,.2f}")

            # Calculate PnL
            pnl = (exec_price - position.entry_price) * position.quantity
            if position.side == 'SHORT':
                pnl = -pnl

            print(f"[OK] Closed {position.side} {symbol} @ ${exec_price:,.2f} | P&L: ${pnl:,.2f}")

            # Cancel remaining orders
            await self.cancel_all_orders(symbol)

            return TradeResult(
                success=True,
                order_id=order_id,
                symbol=symbol,
                side=side.value,
                quantity=position.quantity,
                price=exec_price
            )

        return TradeResult(success=False, error=data.get('msg', 'Unknown error'))
    
    async def cancel_all_orders(self, symbol: str) -> bool:
        """Anulează toate ordinele pentru un simbol"""
        data = await self._request('DELETE', '/fapi/v1/allOpenOrders', {
            'symbol': symbol
        }, signed=True)
        
        return data.get('code') == 200
    
    async def get_open_orders(self, symbol: str = None) -> List[Dict]:
        """Obține ordinele deschise"""
        params = {}
        if symbol:
            params['symbol'] = symbol
        
        data = await self._request('GET', '/fapi/v1/openOrders', params, signed=True)
        return data if isinstance(data, list) else []


# Singleton instance
_connector: Optional[BinanceTestnetConnector] = None


def get_connector() -> BinanceTestnetConnector:
    """Returnează instanța singleton"""
    global _connector
    if _connector is None:
        _connector = BinanceTestnetConnector()
    return _connector


async def test_connection():
    """Test conexiune la Binance Testnet"""
    print("=" * 60)
    print("Testing Binance Testnet Connection")
    print("=" * 60)
    
    connector = BinanceTestnetConnector()
    
    if await connector.connect():
        # Get price
        price = await connector.get_price("BTCUSDT")
        print(f"\n[INFO] BTCUSDT Price: ${price:,.2f}")
        
        # Get position
        position = await connector.get_position("BTCUSDT")
        if position:
            print(f"\n📍 Current Position:")
            print(f"   Side: {position.side}")
            print(f"   Entry: ${position.entry_price:,.2f}")
            print(f"   Size: {position.quantity}")
            print(f"   PnL: ${position.unrealized_pnl:,.2f}")
        else:
            print("\n📍 No open position")
        
        await connector.disconnect()
        return True
    
    return False


if __name__ == '__main__':
    asyncio.run(test_connection())
