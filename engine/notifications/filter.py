"""
Capa 6: Filtro Anti-Spam de Señales.
Evita que el bot de Telegram spamee al trader con señales repetidas del mismo activo
en el mismo lado (LONG/SHORT) dentro de una ventana de tiempo configurable.
"""
import time
from typing import Optional


class NotificationFilter:
    """
    Deduplica notificaciones de señales para evitar spam.
    
    Reglas:
    - Cooldown por (asset + direction): no notificar el mismo lado en el mismo activo
      dentro de COOLDOWN_SECONDS (default: 15 min = 1 vela de 15m).
    - Máximo MAX_SIGNALS_PER_HOUR por activo por hora.
    """

    def __init__(self, cooldown_seconds: int = 900, max_per_hour: int = 4):
        """
        :param cooldown_seconds: Tiempo mínimo entre 2 notificaciones del mismo tipo.
                                 Default: 900s = 15 minutos (1 vela de 15m).
        :param max_per_hour: Máximo de señales por activo por hora.
        """
        self.cooldown_seconds = cooldown_seconds
        self.max_per_hour = max_per_hour

        # {(asset, direction): timestamp_ultimo_envio}
        self._last_sent: dict[tuple, float] = {}
        # {asset: [timestamps de ultima hora]}
        self._hourly_counts: dict[str, list[float]] = {}

    def _get_direction(self, signal_type: str) -> str:
        """Extrae la dirección (LONG/SHORT) del tipo de señal."""
        sig_upper = signal_type.upper()
        if 'LONG' in sig_upper:
            return 'LONG'
        elif 'SHORT' in sig_upper:
            return 'SHORT'
        return 'NEUTRAL'

    def should_send(self, asset: str, signal: dict) -> tuple[bool, Optional[str]]:
        """
        Determina si se debe enviar la notificación.
        
        :param asset: Ej: 'BTCUSDT'
        :param signal: Dict con al menos {'type': '...'}
        :return: (True/False, motivo del bloqueo o None si se permite)
        """
        now = time.time()
        direction = self._get_direction(signal.get('type', ''))
        key = (asset, direction)

        # 1. Verificar cooldown por (asset, direction)
        if key in self._last_sent:
            elapsed = now - self._last_sent[key]
            if elapsed < self.cooldown_seconds:
                remaining = int(self.cooldown_seconds - elapsed)
                return False, f"Cooldown activo: {remaining}s restantes para {asset} {direction}"

        # 2. Verificar límite por hora
        if asset not in self._hourly_counts:
            self._hourly_counts[asset] = []
        
        # Limpiar timestamps de más de 1 hora
        one_hour_ago = now - 3600
        self._hourly_counts[asset] = [t for t in self._hourly_counts[asset] if t > one_hour_ago]

        if len(self._hourly_counts[asset]) >= self.max_per_hour:
            return False, f"Límite horario alcanzado: {self.max_per_hour} señales/hora en {asset}"

        # ✅ Señal aprobada → registrar
        self._last_sent[key] = now
        self._hourly_counts[asset].append(now)
        return True, None

    def reset(self, asset: Optional[str] = None):
        """Limpia el estado del filtro (útil para tests o reset manual)."""
        if asset:
            keys_to_remove = [k for k in self._last_sent if k[0] == asset]
            for k in keys_to_remove:
                del self._last_sent[k]
            self._hourly_counts.pop(asset, None)
        else:
            self._last_sent.clear()
            self._hourly_counts.clear()

    def get_stats(self) -> dict:
        """Retorna estadísticas del filtro para debugging."""
        now = time.time()
        stats = {}
        for (asset, direction), ts in self._last_sent.items():
            stats[f"{asset}_{direction}"] = {
                "last_sent_ago_seconds": int(now - ts),
                "cooldown_remaining": max(0, int(self.cooldown_seconds - (now - ts)))
            }
        return stats


# Instancia global singleton — compartida entre todos los handlers de WebSocket
signal_filter = NotificationFilter(cooldown_seconds=900, max_per_hour=4)


if __name__ == "__main__":
    # Test del filtro
    f = NotificationFilter(cooldown_seconds=5)
    sig = {'type': 'LONG 🟢 (TREND PULLBACK)', 'price': 95000}

    ok, reason = f.should_send('BTCUSDT', sig)
    print(f"Primera señal: {'✅ Permitida' if ok else '❌ Bloqueada: ' + reason}")

    ok, reason = f.should_send('BTCUSDT', sig)
    print(f"Segunda señal inmediata: {'✅ Permitida' if ok else '❌ Bloqueada: ' + reason}")

    import time; time.sleep(6)
    ok, reason = f.should_send('BTCUSDT', sig)
    print(f"Señal post-cooldown: {'✅ Permitida' if ok else '❌ Bloqueada: ' + reason}")
