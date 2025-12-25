import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

from backend.trading.binance_connector import BinanceTestnetConnector

async def check_binance():
    connector = BinanceTestnetConnector()

    if await connector.connect():
        print('=== BINANCE TESTNET STATUS ===')
        print(f'Balance: ${connector.balance:,.2f} USDT')

        # Get positions
        account = await connector.get_account()

        print('\n=== OPEN POSITIONS ===')
        has_positions = False
        for pos in account.get('positions', []):
            if float(pos['positionAmt']) != 0:
                has_positions = True
                print(f"Symbol: {pos['symbol']}")
                print(f"  Side: {'LONG' if float(pos['positionAmt']) > 0 else 'SHORT'}")
                print(f"  Size: {pos['positionAmt']}")
                print(f"  Entry: {pos['entryPrice']}")
                print(f"  PnL: {pos['unrealizedProfit']}")

        if not has_positions:
            print('No open positions')

        # Get open orders
        orders = await connector.get_open_orders('BTCUSDT')
        print('\n=== OPEN ORDERS ===')
        if orders:
            for order in orders:
                print(f"Order {order['orderId']}: {order['side']} {order['type']} @ {order.get('stopPrice', order.get('price', 'MARKET'))}")
        else:
            print('No open orders')

        await connector.disconnect()
    else:
        print('Failed to connect to Binance Testnet')

if __name__ == '__main__':
    asyncio.run(check_binance())
