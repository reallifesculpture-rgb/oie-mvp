import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from backend.trading.binance_connector import BinanceTestnetConnector

async def check_positions():
    connector = BinanceTestnetConnector(
        api_key=os.getenv('BINANCE_TESTNET_API_KEY'),
        api_secret=os.getenv('BINANCE_TESTNET_SECRET')
    )

    account = await connector.get_account()
    positions = account.get('positions', [])

    print('=== CURRENT POSITIONS ===')
    total_pnl = 0
    for pos in positions:
        amt = float(pos.get('positionAmt', 0))
        if amt != 0:
            symbol = pos.get('symbol')
            entry = float(pos.get('entryPrice', 0))
            pnl = float(pos.get('unrealizedProfit', 0))
            total_pnl += pnl
            side = 'LONG' if amt > 0 else 'SHORT'

            # Get current price
            price = await connector.get_price(symbol)
            pct_change = ((price - entry) / entry) * 100
            if side == 'SHORT':
                pct_change = -pct_change

            print(f'{symbol}: {side} {abs(amt)}')
            print(f'  Entry: ${entry:,.4f} -> Current: ${price:,.4f} ({pct_change:+.2f}%)')
            print(f'  PnL: ${pnl:,.2f}')
            print()

    print(f'Total Unrealized PnL: ${total_pnl:,.2f}')

    # Check open orders (SL/TP)
    print('\n=== OPEN ORDERS (SL/TP) ===')
    for pos in positions:
        amt = float(pos.get('positionAmt', 0))
        if amt != 0:
            symbol = pos.get('symbol')
            orders = await connector.get_open_orders(symbol)
            if orders:
                for o in orders:
                    otype = o.get('type')
                    stop_price = float(o.get('stopPrice', 0))
                    print(f'{symbol}: {otype} @ ${stop_price:,.4f}')
            else:
                print(f'{symbol}: NO SL/TP orders!')

asyncio.run(check_positions())
