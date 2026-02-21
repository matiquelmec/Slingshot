import redis
import json
import pandas as pd
from typing import Optional, List

class CacheManager:
    """
    Gestor de Caché Redis ultra-rápido (Capa 1.5).
    Sirve como capa intermedia entre binance_stream.py, fetcher.py y el motor Python.
    Almacena ventanas temporales de Klines y Señales Activas.
    """
    
    def __init__(self, host='localhost', port=6379, db=0):
        try:
            # En producción (Render/Railway), esto será una URL como redis://...
            self.client = redis.StrictRedis(host=host, port=port, db=db, decode_responses=True)
            self.client.ping()
            self.active = True
            print("🚀 Conectado exitosamente a Redis Cache.")
        except redis.ConnectionError:
            print("⚠️ Advertencia: Servidor Redis no detectado localmente. Operando en modo degradado (Sin Caché).")
            self.active = False
            self.client = None

    def store_live_candle(self, symbol: str, interval: str, candle_data: dict):
        """
        Guarda la última vela en vivo recibida por WebSockets.
        Reemplaza la vela anterior para el mismo símbolo e intervalo.
        """
        if not self.active: return
        
        # Serializar datetime a string ISO antes de guardar en JSON
        data_to_store = candle_data.copy()
        if isinstance(data_to_store.get('timestamp'), pd.Timestamp):
            data_to_store['timestamp'] = data_to_store['timestamp'].isoformat()
            
        key = f"live_kline:{symbol.upper()}:{interval}"
        self.client.set(key, json.dumps(data_to_store))

    def get_latest_live_candle(self, symbol: str, interval: str) -> Optional[dict]:
        """Recupera la vela en streaming almacenada en Redis."""
        if not self.active: return None
        
        key = f"live_kline:{symbol.upper()}:{interval}"
        data = self.client.get(key)
        
        if data:
            parsed = json.loads(data)
            # Restaurar Timestamp de Pandas
            parsed['timestamp'] = pd.to_datetime(parsed['timestamp'])
            return parsed
        return None

    def store_historical_df(self, symbol: str, interval: str, df: pd.DataFrame, expire_seconds: int = 3600):
        """
        Guarda un DataFrame completo histórico (ej: las últimas 1000 velas)
        para acceso instantáneo sin tocar disco (.parquet) o red (Binance REST).
        Útil para cálculos de indicadores pesados como SMA 200.
        """
        if not self.active: return
        
        key = f"historical_df:{symbol.upper()}:{interval}"
        # Serializar DF a JSON
        json_data = df.to_json(orient="records", date_format="iso")
        
        # Guardar con límite de tiempo (TTL) para que se renueve automáticamente 
        # (ej: si guardamos 1 hora, expirará y el fetcher volverá a descargar datos frescos)
        self.client.setex(key, expire_seconds, json_data)

    def get_historical_df(self, symbol: str, interval: str) -> Optional[pd.DataFrame]:
        """Recupera el DataFrame histórico parseado."""
        if not self.active: return None
        
        key = f"historical_df:{symbol.upper()}:{interval}"
        data = self.client.get(key)
        
        if data:
            df = pd.read_json(data, orient="records")
            # Restaurar timezone UTC por seguridad
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'], utc=True)
            return df
        return None
        
    def broadcast_signal(self, signal_data: dict):
        """
        Publica una señal de trading en un canal de Redis Pub/Sub.
        Esto permite que otros microservicios (como el bot de Telegram o FastAPI)
        escuchen y procesen señales en milisegundos.
        """
        if not self.active: return
        
        # Serializar datetime
        msg = signal_data.copy()
        if 'timestamp' in msg and isinstance(msg['timestamp'], pd.Timestamp):
             msg['timestamp'] = msg['timestamp'].isoformat()
             
        self.client.publish("slingshot_signals", json.dumps(msg))

if __name__ == "__main__":
    # Test rápido de conexión
    cache = CacheManager()
    if cache.active:
        print("Test: Guardando variable fantasma...")
        cache.client.set("slingshot_test", "100%", ex=10)
        res = cache.client.get("slingshot_test")
        print(f"Resultado Recuperado: {res} (Se auto-destruirá en 10s)")
