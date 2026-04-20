
import pandas as pd
import numpy as np
import json
import os
import sys
import time
from datetime import datetime, timezone
from collections import Counter

# Inyectar path del proyecto para importaciones
sys.path.append(os.getcwd())

from engine.router.gatekeeper import SignalGatekeeper, GatekeeperContext
from engine.risk.risk_manager import RiskManager
from engine.core.logger import logger

# Desactivar logs pesados para el backtest
import logging
logging.getLogger('engine').setLevel(logging.ERROR)

class BacktestSimulator:
    def __init__(self, data_path="engine/tests/data/"):
        self.data_path = data_path
        self.risk_manager = RiskManager()
        self.gatekeeper = SignalGatekeeper(self.risk_manager)
        self.assets = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        self.results = {}

    def load_data(self, asset):
        file_path = os.path.join(self.data_path, f"{asset}_1m_30d.parquet")
        if not os.path.exists(file_path):
            print(f"[ERROR] No se encuentra el dataset para {asset}")
            return None
        df = pd.read_parquet(file_path)
        # Mapeo de columnas compactas a nombres estándar
        column_map = {'t': 'timestamp', 'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}
        df = df.rename(columns=column_map)
        return df

    def simulate_regime(self, df):
        # Simulación simplificada del detector de régimen para el backtest forense
        # En un escenario real, llamaríamos a engine.indicators.regime
        # Aquí derivamos estados basados en volatilidad y tendencia para estresar al Gatekeeper
        
        # Volatilidad (ATR-like)
        df['range'] = (df['high'] - df['low']) / df['close']
        df['vol_ma'] = df['range'].rolling(100).mean()
        
        # Tendencia (EMA cross)
        df['ema_fast'] = df['close'].rolling(20).mean()
        df['ema_slow'] = df['close'].rolling(50).mean()
        df['diff'] = df['ema_fast'] - df['ema_slow']
        
        regimes = []
        for i in range(len(df)):
            vol = df['range'].iloc[i]
            avg_vol = df['vol_ma'].iloc[i]
            diff = df['diff'].iloc[i]
            
            if pd.isna(avg_vol):
                regimes.append("UNKNOWN")
                continue
                
            if vol > avg_vol * 2.5:
                regimes.append("HIGH_VOLATILITY_STRESS")
            elif abs(diff) < (df['close'].iloc[i] * 0.0005):
                regimes.append("CHOPPY")
            elif diff > 0:
                regimes.append("MARKUP")
            else:
                regimes.append("MARKDOWN")
        
        df['regime'] = regimes
        return df

    def run(self):
        print("="*60)
        print("   SLINGSHOT v6.1 - LABORATORIO DE ESTRES FORENSE   ")
        print("="*60)
        
        global_total = 0
        global_approved = 0
        
        for asset in self.assets:
            df = self.load_data(asset)
            if df is None: continue
            
            print(f"[*] Procesando {asset} (30 dias de historia)...")
            df = self.simulate_regime(df)
            
            # Métricas del activo
            stats = {
                "total": 0,
                "approved": 0,
                "veto_choppy": 0,
                "veto_alignment": 0,
                "veto_stress": 0,
                "regimes": Counter(df['regime'])
            }
            
            # Muestreo: Evaluamos 1 señal hipotética cada 15 barras (15m) para simular el trigger del Advisor
            for i in range(100, len(df), 15):
                stats["total"] += 1
                
                current_regime = df['regime'].iloc[i]
                current_price = df['close'].iloc[i]
                
                # Generar señal hipotética (LONG si price > EMA, SHORT si price < EMA)
                sig_type = "LONG" if df['diff'].iloc[i] > 0 else "SHORT"
                
                # Sincronización de timestamp para evitar Veto de Obsolescencia (Time-Decay)
                actual_ts = df['timestamp'].iloc[i]
                if isinstance(actual_ts, (int, float, np.integer)):
                    # Si es unix, mantenerlo como número para que _to_dt lo procese
                    sig_timestamp = actual_ts
                else:
                    sig_timestamp = str(actual_ts)
                    
                # Simular geometría de riesgo válida (R:R = 2.0)
                sl = current_price * 0.99 if sig_type == "LONG" else current_price * 1.01
                tp = current_price * 1.02 if sig_type == "LONG" else current_price * 0.98

                mock_signal = {
                    "asset": asset,
                    "price": current_price,
                    "type": sig_type,
                    "signal_type": sig_type,
                    "timestamp": sig_timestamp,
                    "stop_loss": sl,
                    "take_profit_3r": tp,
                    "tp1": tp,
                    "atr_value": current_price * 0.01
                }
                
                regime_details = {
                    "regime": current_regime,
                    "bias": "BULLISH" if df['diff'].iloc[i] > 0 else "BEARISH",
                    "confidence": 85.0
                }
                
                # Inyectar desalineación macro aleatoria en el 10% de los casos para probar REGLA 2
                if np.random.random() < 0.1:
                    regime_details["bias"] = "BEARISH" if sig_type == "LONG" else "BULLISH"
                
                from unittest.mock import patch
                
                # Mockear ConfluenceManager para dar un score alto base y aislar los vetos de régimen
                def mock_evaluate(*args, **kwargs):
                    return {
                        "score": 85,
                        "conviction": "ALTA CONVICCIÓN",
                        "is_long": sig_type == "LONG",
                        "checklist": [],
                        "reasoning": "Mocked for backtest",
                        "rvol": 1.5,
                        "veto_reason": None
                    }
                
                with patch('engine.router.gatekeeper.confluence_manager.evaluate_signal', side_effect=mock_evaluate):
                    res = self.gatekeeper.process(
                        signals=[mock_signal],
                        df=df.iloc[i-100:i+1],
                        smc_map={},
                        key_levels=[],
                        interval="15m",
                        regime_details=regime_details,
                        silent=True
                    )
                
                if res.approved:
                    stats["approved"] += 1
                else:
                    reason = res.blocked[0].get("blocked_reason", "") if res.blocked else ""
                    if "CHOPPY" in reason: stats["veto_choppy"] += 1
                    elif "Desalineacion" in reason: stats["veto_alignment"] += 1
                    elif "Volatility" in reason or "Score" in reason: stats["veto_stress"] += 1

            self.results[asset] = stats
            global_total += stats["total"]
            global_approved += stats["approved"]
            
            print(f"    - Finalizado: {stats['approved']} aprobadas de {stats['total']} evaluadas.")

        # Generar reporte final JSON
        report = {
            "activos_evaluados": self.assets,
            "metricas_globales": {
                "total_evaluadas": global_total,
                "total_aprobadas": global_approved,
                "tasa_aprobacion_pct": round((global_approved / global_total * 100), 2) if global_total > 0 else 0
            },
            "desglose_por_activo": {}
        }
        
        for asset, stats in self.results.items():
            report["desglose_por_activo"][asset] = {
                "aprobadas": stats["approved"],
                "veto_choppy": stats["veto_choppy"],
                "veto_alignment": stats["veto_alignment"],
                "veto_stress": stats["veto_stress"],
                "distribucion_regimenes": dict(stats["regimes"])
            }
            
        with open("reporte_supervivencia_v6.json", "w") as f:
            json.dump(report, f, indent=2)
            
        print("\n" + "="*60)
        print("   REPORTE DE SUPERVIVENCIA v6.1 GENERADO CON EXITO   ")
        print("="*60)
        print(f"Tasa de Supervivencia Global: {report['metricas_globales']['tasa_aprobacion_pct']}%")
        print("Ubicacion: reporte_supervivencia_v6.json")

if __name__ == "__main__":
    sim = BacktestSimulator()
    sim.run()
