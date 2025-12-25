import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from backend.trading.binance_connector import BinanceTestnetConnector

async def check_and_clean():
    connector = BinanceTestnetConnector()

    if await connector.connect():
        print('=== BINANCE TESTNET STATUS ===')

        # Get current price
        price = await connector.get_price('BTCUSDT')
        print(f'Current Price: ${price:,.2f}')
        print(f'Balance: ${connector.balance:,.2f} USDT')

        # Get positions
        position = await connector.get_position('BTCUSDT')
        print(f'\n=== POSITION ===')
        if position:
            print(f'Side: {position.side}')
            print(f'Size: {position.quantity}')
            print(f'Entry: ${position.entry_price:,.2f}')
            print(f'PnL: ${position.unrealized_pnl:,.2f}')
        else:
            print('No open position')

        # Get open orders
        orders = await connector.get_open_orders('BTCUSDT')
        print(f'\n=== OPEN ORDERS ({len(orders)}) ===')
        for order in orders:
            stop_price = float(order.get('stopPrice', 0))
            diff = ((stop_price - price) / price) * 100
            print(f"Order {order['orderId']}: {order['side']} {order['type']}")
            print(f"  Stop Price: ${stop_price:,.2f} ({diff:+.2f}% from current)")

        # If no position but orders exist, cancel them
        if not position and orders:
            print(f'\n=== CLEANING ORPHAN ORDERS ===')
            print('No position but orders exist - cancelling all...')
            await connector.cancel_all_orders('BTCUSDT')
            print('Done!')

        await connector.disconnect()

if __name__ == '__main__':
    asyncio.run(check_and_clean())
