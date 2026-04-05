import asyncio
import httpx
import websockets
from colorama import init, Fore

init(autoreset=True)

async def check_ollama():
    print(Fore.CYAN + "[*] Verificando Sistema de Inferencia Ollama Local...")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get("http://localhost:11434/api/tags")
            if resp.status_code == 200:
                print(Fore.GREEN + "  [OK] Conexión Ollama Exitosa.")
                models = resp.json().get('models', [])
                if any("gemma" in m['name'] for m in models):
                    print(Fore.GREEN + "  [OK] Modelo Gemma detectado.")
                else:
                    print(Fore.YELLOW + "  [WARN] No se detectó el modelo 'gemma' en Ollama.")
            else:
                print(Fore.RED + f"  [FAIL] Código inesperado de Ollama: {resp.status_code}")
    except httpx.ConnectError:
        print(Fore.RED + "  [FAIL] Ollama no está respondiendo. ¿Iniciaste el servidor?")
    except Exception as e:
        print(Fore.RED + f"  [ERROR] {e}")

async def check_backend_api():
    print(Fore.CYAN + "\n[*] Verificando Backend FastAPI de Slingshot...")
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            # Evaluamos la ruta health que debería estar disponible
            resp = await client.get("http://localhost:8000/api/v1/health")
            if resp.status_code == 200:
                print(Fore.GREEN + "  [OK] Conexión HTTP al Backend Exitosa.")
            else:
                print(Fore.RED + f"  [FAIL] Backend responde pero con errores: {resp.status_code}")
    except httpx.ConnectError:
        print(Fore.RED + "  [FAIL] Servidor FastAPI fuera de línea o puerto ocupado.")
    except Exception as e:
        print(Fore.RED + f"  [ERROR] {e}")

async def check_websocket():
    print(Fore.CYAN + "\n[*] Probando túnel WebSocket Zero-Latency...")
    try:
        uri = "ws://localhost:8000/api/v1/ws/engine"
        async with websockets.connect(uri, close_timeout=2) as ws:
            print(Fore.GREEN + "  [OK] Flujo WebSocket activo y en espera de datos.")
        # La conexión se deshará correctamente por conextro async limit
    except Exception as e:
        print(Fore.RED + f"  [WARN] Conexión WebSocket rechazada. ¿Backend offline? ({type(e).__name__})")

async def main():
    print(Fore.MAGENTA + "=== SLINGSHOT DOCTOR (HEALTH CHECK) ===")
    await check_ollama()
    await check_backend_api()
    await check_websocket()
    print(Fore.MAGENTA + "=======================================\n")

if __name__ == "__main__":
    asyncio.run(main())
