import pandas as pd
from datetime import datetime, time, timezone

class TimeFilter:
    """
    Oráculo del Tiempo (Nivel 0).
    Asegura que SLINGSHOT solo opere en zonas de alta liquidez institucional.
    Toda la lógica interna de este bot DEBE usar estricto UTC.
    """
    
    def __init__(self):
        # Todo está en estricto UTC
        # KillZone Londres: 07:00 UTC - 10:00 UTC (Equivale a 02:00 AM - 05:00 AM EST)
        self.london_open = time(7, 0)
        self.london_close = time(10, 0)
        
        # KillZone Nueva York: 13:00 UTC - 16:00 UTC (Equivale a 08:00 AM - 11:00 AM EST)
        self.ny_open = time(13, 0)
        self.ny_close = time(16, 0)
        
    def is_killzone(self, current_time: pd.Timestamp) -> bool:
        """
        Verifica si un timestamp (pandas datetime, debe ser UTC) cae dentro de una KillZone.
        """
        # Asegurarse de que el input tiene info de la zona horaria (y convertir a UTC si es necesario)
        if current_time.tzinfo is None:
            # Asumimos que la data de Binance REST API es UTC nativo, como dicta la convención
            current_time = current_time.tz_localize('UTC')
        else:
            current_time = current_time.tz_convert('UTC')
            
        t = current_time.time()
        
        # Viernes de cierre: Bloqueo total después de las 18:00 UTC para evitar gaps de fin de semana
        if current_time.dayofweek == 4 and t >= time(18, 0):
            return False
            
        # Sábados y Domingos: Bloqueo de mercado tradicional (Aplica a Forex/Indices, 
        # para Crypto permitimos, pero con precaución, aunque los institucionales bajan el volumen)
        in_london = self.london_open <= t <= self.london_close
        in_ny = self.ny_open <= t <= self.ny_close
        
        return in_london or in_ny
        
    def filter_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Recibe el DataFrame con las señales u Order Blocks, 
        y filtra (elimina) todas aquellas que cayeron fuera de una KillZone.
        """
        df = df.copy()
        # Aplicamos vectorizadamente la comprobación de KillZone sobre la columna 'timestamp'
        df['is_killzone'] = df['timestamp'].apply(self.is_killzone)
        
        # Retornamos solo la data válida
        return df[df['is_killzone']].copy()

if __name__ == "__main__":
    # Test rápido de UTC
    import os
    from pathlib import Path
    
    file_path = Path(__file__).parent.parent.parent / "data" / "btcusdt_15m.parquet"
    if os.path.exists(file_path):
        data = pd.read_parquet(file_path)
        
        tf = TimeFilter()
        velas_totales = len(data)
        velas_filtradas = tf.filter_dataframe(data)
        
        print(f"📊 Reloj UTC Activo:")
        print(f"Velas totales escaneadas: {velas_totales}")
        print(f"Velas descartadas por 'Horario Basura': {velas_totales - len(velas_filtradas)}")
        print(f"✅ Velas aprobadas para operar (KillZones): {len(velas_filtradas)}")
        print(f"\nTasa de Inacción: Hemos evitado operar en mercado lento el {round((1 - len(velas_filtradas)/velas_totales)*100, 2)}% del tiempo.")
    else:
        print("Data file not found.")

