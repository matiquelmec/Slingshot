import asyncio
import httpx
import websockets
from colorama import init, Fore

init(autoreset=True)

async def check_ollama():
    # Importar configuraciones locales del engine
    import sys
    sys.path.append('.')
    try:
        from engine.api.config import settings
    except ImportError:
        settings = None

    print(Fore.CYAN + "[*] Verificando Motor de Inferencia de Inteligencia Artificial...")
    
    # ── RUTA CLOUD: Si se usa Groq o Gemini ──────────────────────────
    if settings and (settings.GROQ_API_KEY or settings.GEMINI_API_KEY):
        provider = "Groq" if settings.GROQ_API_KEY else "Gemini"
        key = settings.GROQ_API_KEY if settings.GROQ_API_KEY else settings.GEMINI_API_KEY
        print(Fore.GREEN + f"  [OK] IA en la nube activa ({provider} Cloud API). Omitiendo check de Ollama local.")
        
        # Test de ping rápido a la API para asegurar conexión e internet activo
        try:
            async with httpx.AsyncClient(timeout=4) as client:
                if provider == "Groq":
                    resp = await client.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                        json={"model": "llama-3.3-70b-versatile", "messages": [{"role": "user", "content": "ping"}], "max_tokens": 1}
                    )
                else:
                    resp = await client.post(
                        f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}",
                        json={"contents": [{"parts": [{"text": "ping"}]}]}
                    )
                
                if resp.status_code == 200:
                    print(Fore.GREEN + f"  [OK] Conexión y credenciales de {provider} Cloud validadas exitosamente.")
                else:
                    print(Fore.RED + f"  [FAIL] La API de {provider} respondió con error ({resp.status_code}). Verifica tu clave.")
        except Exception as e:
            print(Fore.RED + f"  [FAIL] Sin conexión a la API de {provider} Cloud. Verifica tu internet: {e}")
        return

    # ── RUTA LOCAL: Si no hay claves, probamos Ollama local ──────────
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
        print(Fore.RED + "  [FAIL] Ollama local no está respondiendo y no hay claves en la nube configuradas.")
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
