import asyncio
import httpx
import websockets
import json
import time
import sys

# Forzar salida UTF-8 en Windows para evitar errores de codificación con emojis
if sys.platform == "win32":
    import os
    os.system("chcp 65001 > nul")

async def test_binance_rest():
    print("\n[1] Probando Binance REST (fapi.binance.com)...")
    url = "https://fapi.binance.com/fapi/v1/ping"
    async with httpx.AsyncClient() as client:
        try:
            start = time.time()
            resp = await client.get(url, timeout=10)
            print(f"OK: Binance REST ({resp.status_code}) en {(time.time()-start)*1000:.2f}ms")
        except Exception as e:
            print(f"FAIL: Binance REST: {e}")

async def test_binance_ws():
    print("\n[2] Probando Binance WebSocket (fstream.binance.com)...")
    url = "wss://fstream.binance.com/stream?streams=btcusdt@kline_1m"
    try:
        start = time.time()
        # En websockets 14+, connect es un async context manager directamente
        # Pero para ser compatibles con versiones antiguas y manejar el timeout:
        async with websockets.connect(url, open_timeout=10) as ws:
            print(f"OK: Binance WS Conectado en {(time.time()-start)*1000:.2f}ms")
            msg = await asyncio.wait_for(ws.recv(), timeout=5)
            print(f"OK: Datos recibidos: {msg[:100]}...")
    except Exception as e:
        print(f"FAIL: Binance WS: {e}")

async def test_bitunix_rest():
    print("\n[3] Probando Bitunix REST (fapi.bitunix.com)...")
    url = "https://fapi.bitunix.com/api/v1/futures/market/kline?symbol=BTCUSDT&interval=1m&limit=1"
    async with httpx.AsyncClient() as client:
        try:
            start = time.time()
            resp = await client.get(url, timeout=10)
            print(f"OK: Bitunix REST ({resp.status_code}) en {(time.time()-start)*1000:.2f}ms")
            print(f"   Data: {json.dumps(resp.json(), indent=2)[:200]}...")
        except Exception as e:
            print(f"FAIL: Bitunix REST: {e}")

async def main():
    print("=== SLINGSHOT DIAGNOSTICO DE RED ===")
    await test_binance_rest()
    await test_binance_ws()
    await test_bitunix_rest()
    print("\n====================================")

if __name__ == "__main__":
    asyncio.run(main())
