import asyncio
import websockets
import json
import time
import ssl
import certifi

async def test_binance_connection():
    ws_url = "wss://stream.binance.com:9443/ws/btcusdt@ticker"
    print(f"Attempting to connect to: {ws_url}")

    ssl_ctx = ssl.create_default_context(cafile=certifi.where())

    try:
        async with websockets.connect(ws_url, ssl=ssl_ctx) as websocket:
            print("✅ Connection Established Successfully!\n")
            end_time = time.time() + 10

            while time.time() < end_time:
                response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
                data = json.loads(response)
                print(f"Received Data -> {data.get('s')}: ${data.get('c')}")

            print("\n✅ Test Complete: IP is NOT blocked.")

    except websockets.exceptions.InvalidStatusCode as e:
        print(f"\n❌ Connection Failed: Blocked. Status Code: {e.status_code}")
    except Exception as e:
        print(f"\n❌ Connection Failed: {e}")

if __name__ == "__main__":
    asyncio.run(test_binance_connection())
