"""
supabase_client.py — Clientes Supabase para el backend Python
==============================================================
Dos clientes con responsabilidades distintas:

  supabase_anon:    anon key   → lecturas generales (si se necesita en el futuro)
  supabase_service: service_role key → escrituras privilegiadas (INSERT señales, etc.)

El cliente service_role bypasea RLS — SOLO debe usarse en backend.
NUNCA exponer al frontend.
"""

from engine.api.config import settings

# Importación diferida para no fallar si supabase no está instalado aún
_supabase_service = None
_supabase_anon    = None
_initialized      = False


def _init_clients():
    global _supabase_service, _supabase_anon, _initialized
    if _initialized:
        return

    _initialized = True

    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        print("[SUPABASE] ⚠️  SUPABASE_URL o SUPABASE_SERVICE_ROLE_KEY no configurados. "
              "Las señales NO se persistirán en la DB.")
        return

    try:
        from supabase import create_client, Client
        _supabase_service = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
        _supabase_anon    = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY or settings.SUPABASE_SERVICE_ROLE_KEY)
        print(f"[SUPABASE] ✅ Clientes inicializados → {settings.SUPABASE_URL}")
    except ImportError:
        print("[SUPABASE] ❌ Paquete 'supabase' no instalado. Ejecuta: pip install supabase>=2.4.0")
    except Exception as e:
        print(f"[SUPABASE] ❌ Error al inicializar clientes: {e}")


# Lazy properties — se inicializan en el primer uso (no en import time)
class _LazyClient:
    """Wrapper lazy que inicializa el cliente Supabase al primer acceso."""
    def __init__(self, which: str):
        self._which = which

    def __getattr__(self, name):
        _init_clients()
        client = _supabase_service if self._which == "service" else _supabase_anon
        if client is None:
            raise RuntimeError(
                f"[SUPABASE] Cliente '{self._which}' no disponible. "
                "Verifica SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY en .env"
            )
        return getattr(client, name)

    def __bool__(self):
        _init_clients()
        return (_supabase_service if self._which == "service" else _supabase_anon) is not None


# Instancias exportadas
supabase_service = _LazyClient("service")  # para INSERT/UPDATE privilegiados
supabase_anon    = _LazyClient("anon")     # para SELECT generales
