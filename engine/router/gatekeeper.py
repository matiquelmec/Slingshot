"""
engine/router/gatekeeper.py — v10.0 APEX SOVEREIGN (Institutional Guardian)
=========================================================================
Portero Maestro de Slingshot. Ejecuta la auditoría final de seguridad:
1. Filtro Fractal (Alineación HTF 1M/1W/1D)
2. Filtro OTE (Value Zone Entry)
3. Filtro de Riesgo (Kelly Criterion & Drawdown)

FILTRO 1 — Direccional HTF:   ¿La señal sigue el sesgo institucional H1/H4?
FILTRO 2 — Ratio R:R:          ¿La geometría matemática cumple R:R ≥ 2.5?
FILTRO 3 — Score de Confluencia: ¿El Jurado Neural otorga ≥ 75% de confianza?
FILTRO 4 — Path Traversal:     ¿La señal sigue viva (no expiró, no tocó SL/TP)?

Una señal rechazada en cualquier filtro NO se descarta:
se archiva en 'blocked_signals' para el Modo Auditoría del Frontend.
"""
from __future__ import annotations
from engine.core.logger import logger

from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from engine.core.confluence import confluence_manager
from engine.risk.risk_manager import RiskManager
from collections import deque
import time

# --- CACHE DE AUDITORÍA v5.7 ---
SIGNALS_HISTORY = {} # {asset: deque([(timestamp, signal_type)])}


@dataclass
class GatekeeperContext:
    """
    Contexto externo para el Jurado de Confluencia.
    Todos los campos son opcionales para robustez ante datos faltantes.
    """
    ml_projection: dict = field(default_factory=dict)
    session_data: dict = field(default_factory=dict)
    news_items: list = field(default_factory=list)
    economic_events: list = field(default_factory=list)
    liquidation_clusters: list = field(default_factory=list)
    onchain_bias: str = "NEUTRAL"
    heatmap: dict = field(default_factory=dict) # v5.7 Neural Heatmap
    correlated_df: pd.DataFrame | None = None # [SMT Divergence]
    ghost_data: dict = field(default_factory=dict) # [v8.6.0] Ghost Sentinel Macro Data


@dataclass
class GatekeeperResult:
    """Resultado del proceso de filtrado para un lote de señales."""
    approved: list[dict] = field(default_factory=list)
    blocked: list[dict] = field(default_factory=list)


class SignalGatekeeper:
    """
    Aplica los 4 filtros institucionales en secuencia.
    Separa señales aprobadas de las bloqueadas (modo auditoría).
    """

    def __init__(self, risk_manager: RiskManager):
        self._risk = risk_manager

    def process(
        self,
        signals: list[dict],
        df: pd.DataFrame,
        smc_map: dict,
        key_levels: list,
        interval: str,
        htf_bias=None,
        fib_data: dict | None = None,
        context: GatekeeperContext | None = None,
        regime_details: dict | None = None,
        silent: bool = False,
    ) -> GatekeeperResult:
        """
        Procesa un lote de señales aplicando los 4 porteros en cadena.
        """
        if context is None:
            context = GatekeeperContext()

        result = GatekeeperResult()

        # Pre-calcular vectores de tiempo para Path Traversal (performance)
        try:
            df_time  = pd.to_datetime(df["timestamp"], utc=True)
            df_low   = df["low"].values
            df_high  = df["high"].values
            now_utc  = df_time.iloc[-1]
        except Exception:
            df_time = df_low = df_high = now_utc = None

        # ── (Filtro 0 News Blackout delegado 100% al Confluence Manager v8.5.9) ──
        # [BACKTEST_FIX v8.8.6] Usamos el tiempo de la vela, no el tiempo real del sistema
        try:
            now = pd.to_datetime(df["timestamp"].iloc[-1], utc=True)
        except Exception:
            now = pd.Timestamp.now(tz='UTC')

        # ── Filtro 0.5: Session Veto (Ruido de Cierre) ──────────────────────
        # Institucionalmente se evita operar en los últimos minutos de velas mayores (H4/D1).
        # Vetamos si estamos en los últimos 5 minutos de bloques de 4 horas (0, 4, 8, 12, 16, 20)
        # Ojo: la hora actual de un cierre a las 04:00 es las 03:55-03:59.
        minute_of_hour = now.minute
        hour_of_day = now.hour

        # ── Filtro 0.1: Ghost Sentinel Macro Veto (v8.6.0) ───────────────────
        # Bloquea según sentimiento macro global (DXY, Nasdaq, Fear & Greed)
        ghost = context.ghost_data.get("data", {}) if context.ghost_data else {}
        if ghost:
            block_longs = ghost.get("block_longs", False)
            block_shorts = ghost.get("block_shorts", False)
            reason = ghost.get("reason", "Macro Bias Restrictivo")
            
            new_signals = []
            for sig in signals:
                sig_type = sig.get("signal_type", "LONG")
                if sig_type == "LONG" and block_longs:
                    sig["gatekeeper_veto"] = f"GHOST_SENTINEL: {reason}"
                    result.blocked.append(sig)
                elif sig_type == "SHORT" and block_shorts:
                    sig["gatekeeper_veto"] = f"GHOST_SENTINEL: {reason}"
                    result.blocked.append(sig)
                else:
                    new_signals.append(sig)
            signals = new_signals
            if not signals: return result # Salida temprana si todo fue vetado por Macro
        
        if minute_of_hour >= 55:
            # Si la siguiente hora es divisible por 4 (cierre de H4) o es medianoche (cierre D1)
            if (hour_of_day + 1) % 4 == 0 or hour_of_day == 23:
                if not silent:
                    logger.warning(f"[GATEKEEPER] [SESSION_VETO] Bloqueo por ruido de cierre H4/D1 ({now.strftime('%H:%M')} UTC).")
                for sig in signals:
                    self._block(sig, "BLOCKED_BY_SESSION", "Session Veto: Alta volatilidad por cierre de vela mayor", result)
                return result

        # 🧠 [DELTA v6.1] Cerebro de Régimen (Mandatos de Supervivencia)
        regime_info = regime_details or {"regime": "UNKNOWN", "bias": "NEUTRAL", "confidence": 0}
        regime_type = str(regime_info.get("regime", "UNKNOWN")).upper()
        # ── [DELTA v9.0] Inteligencia de Régimen ──
        # Extraer minutos numéricos para Fase 1 adaptativa
        try:
            val = int("".join(filter(str.isdigit, interval)))
            if "h" in interval.lower(): val *= 60
            elif "d" in interval.lower(): val *= 1440
        except:
            val = 15

        # Si estamos en Swing/Macro (>15m), CHOPPY no es un veto total, los rangos son operables
        is_macro = val > 15
        is_choppy = regime_type == "CHOPPY"
        choppy_threshold = 40 if is_macro else 60
        
        regime_bias = str(regime_info.get("bias", "NEUTRAL")).upper()
        regime_stress = regime_type == "HIGH_VOLATILITY_STRESS"
        # --- [FORENSIC v8.2.8] Price Sanity Check --- 
        # Obtenemos el precio actual de mercado desde el DF para comparar coherencia
        market_price = float(df["close"].iloc[-1]) if not df.empty else 0.0

        for sig in signals[-10:]:  # Ventana de las últimas 10 señales
            # 1. 🛡️ Protección de Identidad: Validar coherencia de precio vs asset
            sig_price = float(sig.get("price", 0))
            asset = sig.get("asset", "UNKNOWN")
            
            if market_price > 0:
                price_diff_pct = abs(sig_price - market_price) / market_price
                # Si la señal se desvía más del 15% del precio actual del feed, es basura o de otro activo
                if price_diff_pct > 0.15:
                    logger.warning(f"🚨 [GATEKEEPER] DATA_POLLUTION detectada en {asset}: Precio {sig_price} incoherente vs Market {market_price}")
                    self._block(sig, "BLOCKED_BY_POLLUTION", f"Incoherencia de precio ({price_diff_pct:.1%}). Posible cruce de activos.", result)
                    continue

            # --- [PIPELINE START] Evaluamos Confluencia Primero (v6.5 Master) ---
            # Para que el score esté disponible para los filtros de alineación y régimen
            try:
                confluence_result = confluence_manager.evaluate_signal(
                    df=df,
                    signal=sig,
                    ml_projection=context.ml_projection,
                    session_data=context.session_data,
                    news_items=context.news_items,
                    economic_events=context.economic_events,
                    liquidation_clusters=context.liquidation_clusters,
                    htf_bias=htf_bias,
                    onchain_bias=context.onchain_bias,
                    heatmap=context.heatmap,
                    smc_map=smc_map,
                    correlated_df=context.correlated_df,
                    interval=interval # Pasar intervalo para Time-Decay
                )
                sig["confluence"] = confluence_result
            except Exception as e:
                logger.error(f"[GATEKEEPER] ConfluenceManager error: {e}")
                sig["confluence"] = {"score": 50, "confluences": []}

            sig_type = str(sig.get("signal_type", sig.get("type", ""))).upper()
            is_long = "LONG" in sig_type
            conf_score = sig["confluence"].get("score", 0)

            # 🧠 [SOVEREIGN v10.0] Veto Fractal Estricto
            # Si el Mensual y el Semanal están en contra de la señal, es un suicidio técnico.
            if htf_bias:
                fractal_veto = False
                m1 = htf_bias.m1_regime
                w1 = htf_bias.w1_regime
                
                # Regla de Oro: No operar contra el 1M y 1W si están en tendencia fuerte (Markup/Markdown)
                if is_long:
                    if m1 == 'MARKDOWN' and w1 == 'MARKDOWN':
                        fractal_veto = True
                        reason = "Veto Fractal: 1M y 1W en MARKDOWN. Prohibido buscar Longs."
                else:
                    if m1 == 'MARKUP' and w1 == 'MARKUP':
                        fractal_veto = True
                        reason = "Veto Fractal: 1M y 1W en MARKUP. Prohibido buscar Shorts."
                
                if fractal_veto:
                    if not silent:
                        logger.warning(f"[GATEKEEPER] [FRACTAL_VETO] {asset} {sig_type} bloqueado por alineación macro negativa.")
                    self._block(sig, "FRACTAL_VETO", reason, result)
                    continue

            # ── REGLA 2 (ALIGNMENT): Veto por Desalineación Macro ────────────
            alignment_veto = False
            if regime_bias == "BULLISH" and not is_long and "STRONG" in regime_type:
                # Si la confianza es brutal, permitimos contratendencia
                if conf_score < 80: alignment_veto = True # Elevado a 80 en v10.0
            elif regime_bias == "BEARISH" and is_long and "STRONG" in regime_type:
                if conf_score < 80: alignment_veto = True
                
            if alignment_veto:
                if not silent:
                    logger.info(f"[GATEKEEPER] [DELTA_BLOCK] Desalineacion Macroestructural ({sig_type} vs {regime_type}). Confianza {conf_score}% insuficiente para contratendencia.")
                self._block(sig, "DELTA_VETO", f"Desalineacion Macroestructural: Operando contra {regime_type} con confianza baja ({conf_score}%)", result)
                continue
            # (SMT_Strength se pasará en el contexto de riesgo si existe)
            smt_strength = sig.get('confluence', {}).get('smt_strength', 0) if sig.get('confluence') else 0
            
            # --- [DELTA v6.1] PROTECCIÓN DE GEOMETRÍA INSTITUCIONAL ---
            # Preservamos el setup original de la estrategia si existe
            orig_sl = sig.get('stop_loss')
            orig_tp = sig.get('tp1') or sig.get('take_profit_3r')

            risk_data = self._risk.calculate_position(
                current_price=sig["price"],
                signal_type=sig.get("signal_type", "LONG"),
                market_regime=sig.get("regime", "RANGING"),
                key_levels=key_levels,
                smc_data=smc_map,
                atr_value=sig.get("atr_value", 0.0),
                smt_strength=smt_strength,
                asset=sig.get("asset", "UNKNOWN"),
                liquidations=context.liquidation_clusters,
                heatmap=context.heatmap,
                fib_data=fib_data
            )
            
            # Si la estrategia ya definió un setup (Ej: SMC OB-Low), lo respetamos
            if orig_sl and orig_tp:
                risk_data['stop_loss'] = orig_sl
                risk_data['tp1'] = orig_tp
                risk_data['take_profit_3r'] = orig_tp
                
            sig.update(risk_data)

            # ── Filtro 2: Direccional HTF (AHORA DELEGADO AL CONFLUENCE MANAGER v5.7.155 Master Gold) ──
            # Se comenta para permitir que el Score registre el Veto de forma oficial
            # if htf_bias and htf_bias.direction != "NEUTRAL":
            #     is_long = "LONG" in str(sig.get("type", "")).upper()
            #     if htf_bias.direction == "BULLISH" and not is_long:
            #         sig["confluence"] = {"score": 0}
            #         self._block(sig, "BLOCKED_BY_HTF", f"Contra sesgo HTF Alcista: {htf_bias.reason}", result)
            #         continue
            #     if htf_bias.direction == "BEARISH" and is_long:
            #         sig["confluence"] = {"score": 0}
            #         self._block(sig, "BLOCKED_BY_HTF", f"Contra sesgo HTF Bajista: {htf_bias.reason}", result)
            #         continue

            # ── [FASE 1] Veto por Régimen Lateral (CHOPPY) ──
            # Ahora validamos el score real de confluencia contra el umbral adaptativo
            if is_choppy and conf_score < choppy_threshold:
                 if not silent:
                     logger.warning(f"⚠️ [GATEKEEPER] [DELTA_BLOCK] {interval} CHOPPY veto: Score {conf_score}% < {choppy_threshold}%")
                 self._block(sig, "BLOCKED_BY_DELTA", f"Régimen CHOPPY: Confianza {conf_score}% insuficiente", result)
                 continue

            score = conf_score

            # ── Filtro 1: Jerarquía de Timeframes (SIGMA v6.5 MASTER) ──
            if htf_bias:
                is_long = "LONG" in str(sig.get("signal_type", sig.get("type", ""))).upper()
                
                # REGLA DE ORO v6.6: Solo vetamos si el score es < 65% y hay conflicto.
                if score < 65 and htf_bias.direction != "NEUTRAL":
                    if (htf_bias.direction == "BULLISH" and not is_long) or \
                       (htf_bias.direction == "BEARISH" and is_long):
                        self._block(sig, "SIGMA_VETO", f"Conflicto de Tendencia (Score {score}% < 65%)", result)
                        continue


            # ── Filtro 2.7: Anti-Spam de Volatilidad (OMEGA v5.7) ─────────────
            asset = sig.get("asset", "UNKNOWN")
            now_ts = time.time()
            if asset not in SIGNALS_HISTORY:
                SIGNALS_HISTORY[asset] = deque(maxlen=20)
            
            sig_type = "LONG" if "LONG" in str(sig.get("signal_type", sig.get("type", ""))).upper() else "SHORT"
            recent_for_asset = list(SIGNALS_HISTORY[asset])
            
            # Contar señales contradictorias en los últimos 15 min (900 seg)
            contradictory_count = 0
            for ts, old_type in recent_for_asset:
                if now_ts - ts < 900 and old_type != sig_type:
                    contradictory_count += 1

            # Reducimos la sensibilidad de OMEGA en scalping para permitir volatilidad rápida
            # v8.2.1 Tuning: 5 contradicciones en 1m/5m para no asfixiar el radar
            max_contradictory = 5 if interval in ["1m", "5m"] else 3
            if contradictory_count >= max_contradictory:
                self._block(sig, "BLOCKED_CHOPPY", f"[OMEGA] Bloqueo por Choppy: >{max_contradictory} flips.", result)
                continue
            
            # Registrar éxito parcial (luego de pasar filtros estructurales base)
            SIGNALS_HISTORY[asset].append((now_ts, sig_type))

            # Original Filter 2.5: Conflict Manager (IA vs SMC)
            if context.ml_projection and "direction" in context.ml_projection:
                ml_dir = str(context.ml_projection["direction"]).upper()
                is_long = "LONG" in str(sig.get("signal_type", sig.get("type", ""))).upper()
                
                if is_long and ml_dir == "BAJISTA":
                    self._block(sig, "STAND_BY", "[CONFLICT MANAGER] ML proyecta Venta (Stand-by)", result)
                    continue
                if not is_long and ml_dir == "ALCISTA":
                    self._block(sig, "STAND_BY", "[CONFLICT MANAGER] ML proyecta Compra (Stand-by)", result)
                    continue

            # ── Filtro 2.6: Mitigación Instantánea (Volatilidad Ghost) ────────
            try:
                # Si la volatilidad de la vela actual excede severamente el tramo normal
                candle_spread = ((df["high"].iloc[-1] - df["low"].iloc[-1]) / df["close"].iloc[-1]) * 100
                # Adaptativo: 2.5% para 15m, 6% para 4h, 10% para 1d
                max_spread = 2.5 if val <= 15 else (6.0 if val <= 240 else 10.0)
                if candle_spread > max_spread:
                    self._block(sig, "BLOCKED_BY_VOLATILITY", f"Flash Volatility detectada ({candle_spread:.2f}%). Prevención de Slippage.", result)
                    continue
            except:
                pass

            # ── Filtro 4: R:R Mínimo y Zona de Valor OTE (v10.0) ───────────────
            rr_res = self._risk.validate_signal(sig)
            sig["rr_ratio"]     = rr_res["rr_ratio"]
            sig["trade_quality"] = rr_res["trade_quality"]

            # [SNIPER v10.0] Validación de Zona de Valor
            # Si no estamos en zona OTE (Optimal Trade Entry) o descuento/premium, el trade es ruidoso.
            ote_data = risk_data.get("fib_ote", {})
            if ote_data:
                is_in_zone = ote_data.get("is_in_ote", False)
                if not is_in_zone and conf_score < 85: # Solo permitimos fuera de OTE si el score es extremo
                    self._block(sig, "VALUE_ZONE_VETO", "Fuera de zona OTE / Descuento Premium", result)
                    continue

            # Umbral de Rentabilidad Matemática v6.7.8 (Extreme Survival)
            min_rr = self._risk.min_rr # Sniper Sync Master Gold
            if not rr_res.get("approved", False):
                if not silent:
                    logger.info(f"[GATEKEEPER] 🔴 DELTA BLOCK: R:R {sig.get('rr_ratio', 0):.2f} | Reason: {rr_res.get('reason', 'N/A')}")
                self._block(sig, "DELTA_VETO", f"R:R {sig.get('rr_ratio', 0):.2f} < {min_rr} | {rr_res.get('reason')}", result)
                continue

            # ── Filtro 5: Score de Confluencia Mínimo ──
            # [v8.2.1] Sintonía de Visibilidad: Bajamos los muros para que la UI respire
            # 🧠 REGLA 3 (STRESS): Elevación de Umbral por Volatilidad Extrema
            stress_premium = 15 if regime_stress else 0
            
            if asset == "BTCUSDT":
                min_score = 25 + stress_premium
            elif asset == "SOLUSDT":
                min_score = 45 + stress_premium
            elif asset == "ETHUSDT":
                min_score = 35 + stress_premium
            else:
                min_score = 35 + stress_premium
            
            if regime_stress and not silent:
                logger.warning(f"[GATEKEEPER] STRESS DETECTADO: Elevando umbral de score (+{stress_premium}%)")

            # [FORENSIC v6.8.2] Auditoría de Portero
            if not silent:
                logger.info(f"[GATEKEEPER_AUDIT] Asset: {asset} | Score: {score}% | Required: {min_score}%")
            
            # ── Filtro 5: Confluencia (Veredicto Final) ────────────────────
            # [v9.5] Score Adaptativo por Timeframe:
            # En Swing (4h+), 35% es suficiente si hay estructura. En Scalping (15m), 50% es ley.
            min_score_final = 50 if val <= 15 else 35
            
            if score < min_score_final:
                reason = sig.get("confluence", {}).get("veto_reason") or f"Confianza {score}% < {min_score_final}%"
                self._block(sig, "LOW_CONFLUENCE", reason, result)
                continue
            
            # ── Filtro 6: Path Traversal — ¿Sigue Viva? ──────────────────────
            if not self._is_alive(sig, df_time, df_low, df_high, now_utc):
                self._block(sig, "BLOCKED_EXPIRED", "Señal expirada o tocó SL/TP en el origen", result)
                continue

            # ✅ ¡SEÑAL TOTALMENTE VALIDADA! 
            sig["status"] = "APPROVED"
            result.approved.append(sig)

        # ── [SIGMA v5.7.15] AGRUPACIÓN POR ZONA (0.5%) & LÍMITE OMEGA ──
        if result.approved:
             result.approved = self._apply_master_filter(result.approved)

        return result

    def _apply_master_filter(self, approved_signals: list[dict]) -> list[dict]:
        """
        [DELL v5.7.15 - MANDO ABSOLUTO]
        1. Agrupa por Símbolo / Timeframe.
        2. Si están en +-0.5% del precio, fusionar.
        3. Solo permitir EL MEJOR cuadro (Top 1) por Activo.
        """
        from collections import defaultdict
        
        # Paso 1: Agrupar por Asset
        by_asset = defaultdict(list)
        for sig in approved_signals:
            by_asset[sig["asset"]].append(sig)
            
        final_list = []
        
        for asset, sigs in by_asset.items():
            # Ordenar por Score descendente para priorizar la de mayor confluencia
            sigs.sort(key=lambda x: x.get("confluence", {}).get("score", 0), reverse=True)
            
            merged_sigs = []
            for s in sigs:
                is_clustered = False
                for m in merged_sigs:
                    # Comprobar si el precio está dentro del 0.5% para fusión de zona
                    price_diff = abs(s["price"] - m["price"]) / m["price"]
                    if price_diff <= 0.005 and s["signal_type"] == m["signal_type"]:
                        is_clustered = True
                        m["reasoning"] = f"[Zona Institucional 🛡️] {m.get('reasoning', '')}"
                        break
                if not is_clustered:
                    merged_sigs.append(s)
            
            # [OMEGA v5.7.15] ANTI-REPETICIÓN: Solo el TOP 1 por activo
            # No queremos 10 cuadros de SOL, queremos EL MEJOR.
            if merged_sigs:
                final_list.append(merged_sigs[0])
            
        return final_list

    # ── Helpers privados ─────────────────────────────────────────────────────

    @staticmethod
    def _block(sig: dict, status: str, reason: str, result: GatekeeperResult):
        sig["status"] = status
        sig["blocked_reason"] = reason
        result.blocked.append(sig)

    @staticmethod
    def _is_alive(sig: dict, df_time, df_low, df_high, now_utc) -> bool:
        """Path Traversal vectorizado: verifica si la señal sigue activa."""
        if now_utc is None:
            return True

        expiry_str = sig.get("expiry_timestamp")
        if expiry_str:
            try:
                if now_utc > pd.to_datetime(expiry_str, utc=True):
                    return False
            except Exception:
                pass

        sl = float(sig.get("stop_loss", 0))
        tp = float(sig.get("take_profit_3r", 0))
        if sl <= 0 or tp <= 0:
            return True

        try:
            sig_time = pd.to_datetime(sig.get("timestamp"), utc=True)
            mask     = df_time >= sig_time
            if not mask.any():
                return True

            lows  = df_low[mask]
            highs = df_high[mask]
            # [v6.1] Soporte para signal_type y type (Unificación Institucional)
            sig_raw_type = str(sig.get("signal_type", sig.get("type", ""))).upper()
            is_long = "LONG" in sig_raw_type

            if is_long:
                return not ((lows <= sl).any() or (highs >= tp).any())
            else:
                return not ((highs >= sl).any() or (lows <= tp).any())
        except Exception:
            return True
