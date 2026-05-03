import pandas as pd
import os
import sys
import asyncio
from datetime import datetime
from unittest.mock import patch

# Añadir root al path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from engine.main_router import SlingshotRouter
from engine.indicators.liquidations import estimate_liquidation_clusters
from engine.indicators.htf_analyzer import HTFAnalyzer
from engine.core.logger import logger

# Configuración de logs para auditoría (WARNING para velocidad)
logger.setLevel("INFO")

class EventDrivenReplayEngine:
    """
    Motor de Backtesting de Grado Institucional (v8.8.5).
    Inyecta datos históricos en el router principal imitando el flujo del WebSocket,
    manteniendo una fidelidad del 100% con la lógica de producción.
    """
    
    def __init__(self, data_path: str, symbol: str = "BTCUSDT", interval: str = "15m", window_size: int = 200):
        self.data_path = data_path
        self.symbol = symbol
        self.interval = interval
        self.window_size = window_size
        self.router = SlingshotRouter()
        self.htf_analyzer = HTFAnalyzer()
        
        # Resultados SIGMA: Trade Tracker
        self.active_trades = []
        self.closed_trades = []
        self.equity_curve = []
        self.initial_balance = 10000.0
        self.current_balance = self.initial_balance

    def load_data(self) -> pd.DataFrame:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [DATA] Cargando Data Lake: {self.data_path}")
        if not os.path.exists(self.data_path):
            raise FileNotFoundError(f"Archivo no encontrado: {self.data_path}")
            
        df = pd.read_parquet(self.data_path)
        df.rename(columns={'o': 'open', 'h': 'high', 'l': 'low', 'c': 'close', 'v': 'volume'}, inplace=True)
        # Asegurar tipos y timestamp
        df['t'] = df['t'].astype('int64')
        df['timestamp'] = pd.to_datetime(df['t'], unit='s')
        df.set_index('timestamp', inplace=True, drop=False)
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [OK] {len(df)} velas cargadas. Inicio: {df['timestamp'].min()} | Fin: {df['timestamp'].max()}")
        
        # [AUDITORIA v10.0] Pre-generamos los DataFrames HTF para evitar re-calculo ineficiente
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [HTF] Generando estructuras superiores (Resampling)...")
        self.df_h1 = df.resample('1h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
        self.df_h4 = df.resample('4h').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
        self.df_1d = df.resample('1d').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
        self.df_1w = df.resample('1W').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
        self.df_1m = df.resample('1ME').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last', 'volume': 'sum'}).dropna()
        
        return df

    def run(self):
        """Ejecuta la simulación histórica."""
        df = self.load_data()
        total_candles = len(df)
        WINDOW_SIZE = 250 # Necesario para indicadores SMC
        
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [RUN] Iniciando Replay Engine Tick-by-Tick...")
        
        start_idx = WINDOW_SIZE
        with patch('engine.api.advisor.check_ollama_status', return_value=asyncio.sleep(0, result=False)):
            for i in range(start_idx, total_candles):
                # 1. Obtener Ventana Deslizante (15m)
                start_w = max(0, i - self.window_size)
                window = df.iloc[start_w : i].copy().reset_index(drop=True)
                current_candle = window.iloc[-1]
                current_time = current_candle['timestamp']
                current_price = current_candle['close']
                
                # 2. Obtener Contexto HTF Sincronizado (No miramos al futuro)
                # Solo pasamos los datos que existían hasta 'current_time'
                h1_window = self.df_h1[self.df_h1.index < current_time].tail(100)
                h4_window = self.df_h4[self.df_h4.index < current_time].tail(100)
                d1_window = self.df_1d[self.df_1d.index < current_time].tail(100)
                w1_window = self.df_1w[self.df_1w.index < current_time].tail(20)
                m1_window = self.df_1m[self.df_1m.index < current_time].tail(12)
                
                # 3. Analizar Sesgo con Fidelidad de Producción
                htf_bias = self.htf_analyzer.analyze_bias(
                    df_h1=h1_window,
                    df_h4=h4_window,
                    df_1d=d1_window,
                    df_1w=w1_window,
                    df_1m=m1_window
                )
                
                # Liquidaciones dinámicas
                live_liquidations = estimate_liquidation_clusters(window, current_price)
                
                self.router.set_context(
                    liquidation_clusters=live_liquidations,
                    ghost_data={"macro_bias": htf_bias.direction if htf_bias else "NEUTRAL"}
                )
                
                # 4. Procesar Señal
                result = self.router.process_market_data(
                    df=window,
                    asset=self.symbol,
                    interval=self.interval,
                    silent=True,
                    htf_bias=htf_bias
                )
                
                # 5. Capturar y Registrar Trades Aprobados
                gate_approved = result.get("signals", [])
                if gate_approved:
                    for sig in gate_approved:
                        self._record_trade(sig, current_candle['timestamp'], current_price)
                
                # 6. [SIGMA ENGINE] Actualizar estado de trades activos vela por vela
                self._update_active_trades(current_candle, result=result)
                
                # [AUDITORIA v8.9.3] Log de bloqueos reales
                gate_blocked = result.get("blocked_signals", [])
                for sig in gate_blocked:
                    reason = sig.get("blocked_reason") or sig.get("gatekeeper_veto") or "Motivo No Especificado"
                    # Usar el índice de la vela para el log
                    print(f"[{current_candle['timestamp']}] [BLOCKED] {sig.get('signal_type')} | Reason: {reason}")
                
                # Progress bar
                if i % 100 == 0:
                    prog = (i / total_candles) * 100
                    approved = len(self.active_trades) + len(self.closed_trades)
                    print(f"Progreso: {prog:.1f}% | Velas: {i}/{total_candles} | Aprobados: {approved}")

        self._print_scorecard()

    def _record_trade(self, result: dict, timestamp, entry_price: float):
        confluence = result.get("confluence", {})
        risk = result.get("risk", {})
        
        # Evitar abrir trades múltiples en la misma dirección si ya hay uno activo
        sig_type = result.get("signal_type", "UNKNOWN")
        if any(t['type'] == sig_type and t['status'] != 'CLOSED' for t in self.active_trades):
            return
            
        new_trade = {
            "id": f"{timestamp.strftime('%Y%m%d%H%M')}-{sig_type}",
            "timestamp": timestamp,
            "type": sig_type,
            "entry": entry_price,
            "score": confluence.get("score", 0),
            "tp1": result.get("tp1", risk.get("tp1", 0)),
            "tp2": result.get("tp2", risk.get("tp2", 0)),
            "tp3": result.get("tp3", risk.get("tp3", 0)),
            "sl_initial": result.get("stop_loss", risk.get("stop_loss", 0)),
            "sl_current": result.get("stop_loss", risk.get("stop_loss", 0)),
            "tp1_vol_pct": risk.get("tp1_vol_pct", 0.60),
            "status": "RUNNING",
            "r_realized": 0.0,
            "close_reason": "",
            "risk_amount": risk.get("risk_amount_usdt", 100), # Riesgo nominal de $100 por defecto
            "expected_rr": result.get("rr_ratio", 0)
        }
        
        if new_trade["sl_initial"] > 0 and new_trade["tp1"] > 0:
            self.active_trades.append(new_trade)
            print(f"[{timestamp}] [OPEN] {new_trade['type']} @ {new_trade['entry']:.2f} | SL: {new_trade['sl_initial']:.2f} | TP1: {new_trade['tp1']:.2f}")

    def _update_active_trades(self, candle, result=None):
        high = candle['high']
        low = candle['low']
        close = candle['close']
        ts = candle['timestamp']
        
        for trade in list(self.active_trades): # Copia superficial para iterar
            if trade['status'] == 'CLOSED':
                self.active_trades.remove(trade)
                self.closed_trades.append(trade)
                continue
                
            is_long = "LONG" in trade['type']
            risk_dist = abs(trade['entry'] - trade['sl_initial'])
            
            # --- EVALUACIÓN DE SL (Peor escenario primero) ---
            sl_hit = (is_long and low <= trade['sl_current']) or (not is_long and high >= trade['sl_current'])
            
            if sl_hit:
                # Si SL es tocado
                if trade['sl_current'] == trade['sl_initial']:
                    # Pérdida total del riesgo remanente
                    portion_lost = 1.0 if trade['status'] == 'RUNNING' else (1.0 - trade['tp1_vol_pct'])
                    trade['r_realized'] -= portion_lost # -1R o -0.4R
                    trade['close_reason'] = "STOP_LOSS"
                else:
                    # Cerrado en Trailing / Breakeven
                    trade['close_reason'] = "TRAILING_STOP"
                
                trade['status'] = 'CLOSED'
                trade['exit_price'] = trade['sl_current']
                print(f"[{ts}] [CLOSED] {trade['type']} | {trade['close_reason']} | R Acum: +{trade['r_realized']:.2f}R")
                self.active_trades.remove(trade)
                self.closed_trades.append(trade)
                continue
                
            # --- [APEX FASE 2] SMART TRAILING (SEGUIMIENTO ESTRUCTURAL) ---
            # Si el trade ya tocó TP1, activamos el seguimiento estructural por Order Blocks
            if trade['status'] == 'TP1_HIT' and result:
                # Extraemos OBs del metadata del resultado (si está disponible)
                smc_data = result.get("metadata", {}).get("smc_data", {})
                if smc_data:
                    if is_long:
                        # Buscar el OB alcista más reciente que esté por encima del SL actual pero debajo del precio
                        obs = smc_data.get("order_blocks", {}).get("bullish", [])
                        valid_obs = [ob['bottom'] for ob in obs if ob['bottom'] > trade['sl_current'] and ob['bottom'] < close]
                        if valid_obs:
                            new_sl = max(valid_obs)
                            if new_sl > trade['sl_current']:
                                trade['sl_current'] = new_sl
                                print(f"[{ts}] [SMART TRAIL] LONG | SL -> {new_sl:.2f} (Estructural OB)")
                    else:
                        # Para Shorts, buscar el OB bajista más reciente
                        obs = smc_data.get("order_blocks", {}).get("bearish", [])
                        valid_obs = [ob['top'] for ob in obs if ob['top'] < trade['sl_current'] and ob['top'] > close]
                        if valid_obs:
                            new_sl = min(valid_obs)
                            if new_sl < trade['sl_current']:
                                trade['sl_current'] = new_sl
                                print(f"[{ts}] [SMART TRAIL] SHORT | SL -> {new_sl:.2f} (Estructural OB)")

            # --- EVALUACIÓN DE TP1 (Cierre Parcial y Auto-Breakeven) ---
            tp1_hit = (is_long and high >= trade['tp1']) or (not is_long and low <= trade['tp1'])
            
            if tp1_hit and trade['status'] == 'RUNNING':
                # Toma de beneficios parcial
                reward_dist = abs(trade['tp1'] - trade['entry'])
                r_won = (reward_dist / risk_dist) if risk_dist > 0 else 0
                r_won_partial = r_won * trade['tp1_vol_pct']
                
                trade['r_realized'] += r_won_partial
                trade['status'] = 'TP1_HIT'
                
                # AUTO-BREAKEVEN: Movemos el SL al precio de entrada
                trade['sl_current'] = trade['entry']
                print(f"[{ts}] [PARTIAL] {trade['type']} | TP1 Hit @ {trade['tp1']:.2f} | R Asegurado: +{trade['r_realized']:.2f}R | SL -> BREAKEVEN")
                
            # --- EVALUACIÓN DE TP FINAL (Asumimos TP2 para simplificar la toma del Runner) ---
            tp2_hit = False
            if trade['tp2'] > 0:
                 tp2_hit = (is_long and high >= trade['tp2']) or (not is_long and low <= trade['tp2'])
            
            if tp2_hit and trade['status'] == 'TP1_HIT':
                 reward_dist = abs(trade['tp2'] - trade['entry'])
                 r_won = (reward_dist / risk_dist) if risk_dist > 0 else 0
                 # La ganancia de la parte remanente
                 r_won_runner = r_won * (1.0 - trade['tp1_vol_pct'])
                 
                 trade['r_realized'] += r_won_runner
                 trade['status'] = 'CLOSED'
                 trade['close_reason'] = "TP2_FULL_TARGET"
                 trade['exit_price'] = trade['tp2']
                 print(f"[{ts}] [FULL CLOSE] {trade['type']} | TP2 Hit @ {trade['tp2']:.2f} | R Total: +{trade['r_realized']:.2f}R")
                 self.active_trades.remove(trade)
                 self.closed_trades.append(trade)

    def _print_scorecard(self):
        print("\n" + "="*50)
        print(" SCORECARD INSTITUCIONAL (SIGMA BACKTEST) ")
        print("="*50)
        
        # Procesamos tanto los trades cerrados como los que quedaron abiertos al final del backtest
        all_trades = self.closed_trades + self.active_trades
        
        print(f"Total Trades Tomados: {len(all_trades)}")
        if not all_trades:
            print("No se operaron trades.")
            return
            
        longs = len([t for t in all_trades if t['type'] == 'LONG'])
        shorts = len([t for t in all_trades if t['type'] == 'SHORT'])
        
        # Metricas reales
        winners = len([t for t in all_trades if t['r_realized'] > 0])
        losers = len([t for t in all_trades if t['r_realized'] < 0])
        breakevens = len([t for t in all_trades if t['r_realized'] == 0 and t['status'] == 'CLOSED'])
        
        total_r = sum(t['r_realized'] for t in all_trades)
        avg_score = sum(t['score'] for t in all_trades) / len(all_trades)
        
        win_rate = (winners / len(all_trades)) * 100 if all_trades else 0
        
        print(f"Longs: {longs} | Shorts: {shorts}")
        print(f"Confluencia Promedio: {avg_score:.1f}%")
        print(f"\n[DESEMPEÑO REAL]")
        print(f"Win Rate (Trades con Ganancia): {win_rate:.1f}%")
        print(f"Ganadores: {winners} | Perdedores: {losers} | Breakeven: {breakevens}")
        print(f"[RETORNO TOTAL] (Curva R): +{total_r:.2f}R")
        
        print("\nDETALLE DE TRADES:")
        for i, t in enumerate(all_trades):
            estado = t.get('close_reason', t.get('status', 'N/A'))
            print(f"Trade #{i+1}: {t['type']} | Estado: {estado} | R Ganado: {t['r_realized']:.2f}R")
        
        print("="*50)
        print("NOTA: Este es un análisis de generación de señales. La ejecución (fills/slippage) requiere simulación de tick.")
        
        # [AUDITORIA v10.0] Guardar resultados en el archivo que el usuario tiene abierto
        import json
        audit_file = "backtest_audit.json"
        report_file = "tmp/backtest_report_BTCUSDT.json"
        
        # Estructura compatible con el frontend y el reporte del usuario
        summary = {
            "symbol": self.symbol,
            "interval": self.interval,
            "final_balance": self.current_balance,
            "net_profit": self.current_balance - self.initial_balance,
            "win_rate": win_rate,
            "total_trades": len(all_trades),
            "total_r": total_r,
            "avg_score": avg_score,
            "trade_log": all_trades
        }
        
        with open(audit_file, "w") as f:
            json.dump(all_trades, f, indent=4, default=str)
            
        with open(report_file, "w") as f:
            json.dump(summary, f, indent=4, default=str)
            
        print(f"\n[OK] Auditoria guardada en: {audit_file}")
        print(f"[OK] Reporte actualizado en: {report_file}")

if __name__ == "__main__":
    # Asegurar que existe data histórica (usar el fetcher si no existe)
    data_file = os.path.join(os.path.dirname(__file__), "../tests/data/BTCUSDT_15m_90d.parquet")
    
    if not os.path.exists(data_file):
        print(f"⚠️ Faltan datos históricos en: {data_file}")
        print("Por favor, ejecuta primero: python scripts/historical_fetcher.py")
    else:
        engine = EventDrivenReplayEngine(data_path=data_file, interval="15m")
        engine.run()
