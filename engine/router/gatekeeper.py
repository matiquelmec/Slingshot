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
from engine.core.memory import blackbox
from engine.core.validator import validator_agent
from engine.risk.risk_manager import RiskManager
from collections import deque
import asyncio
import time

# New imports for dynamic config
from pathlib import Path
import json

CONFIG_PATH = Path(__file__).with_name('gatekeeper_config.json')

def _load_gatekeeper_config():
    """Carga la configuración de umbrales desde `gatekeeper_config.json`.
    Si el archivo no existe o falla la carga, devuelve valores por defecto.
    """
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"[GATEKEEPER] Error loading config: {e}")
    # Valores por defecto seguros (calibrados con auditoría v13.6)
    return {
        "confidence_thresholds": {
            "STRONG_BULL": 70,
            "STRONG_BEAR": 70,
            "CHOPPY": 65,
            "TRENDING_BULL": 65,
            "TRENDING_BEAR": 65,
            "TRANSITION": 65,
            "DEFAULT": 70
        },
        "rvol_thresholds": {
            "STRONG": 1.0,
            "CHOPPY": 1.2,
            "DEFAULT": 1.0
        },
        "ote_tolerance_pct": 0.5,
        "ote_min_confidence": 70,
        "min_score_long": 70,
        "min_score_short": 75,
        "blocked_hours_utc": [9, 12, 13, 16]
    }


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


class BayesianInferenceEngine:
    """
    [BAYESIAN INFERENCE ENGINE v1.0]
    Calcula la probabilidad condicional de éxito P(Éxito | Setup) usando
    el historial de la caja negra (BlackBox).
    
    Permite bypass dinámico de vetos rígidos si la probabilidad condicional
    histórica de éxito en ese escenario es superior al 60%.
    """
    def __init__(self, bb):
        self.bb = bb

    def estimate_probability(self, asset: str, signal_type: str, current_fp: dict) -> tuple[float, str]:
        """
        Retorna (probabilidad_de_exito: float, reasoning: str)
        """
        memory = self.bb.memory
        if len(memory) < 10:
            # Fallback seguro por falta de historial suficiente (a priori neutral)
            return 0.55, "Historial insuficiente en BlackBox (a priori 55% WR estimado)"

        # 1. Filtrar trades del mismo activo
        asset_trades = [t for t in memory if t.get("asset") == asset]
        if not asset_trades:
            # Si no hay trades del activo, buscamos en general por dirección
            asset_trades = [t for t in memory if t.get("signal_type") == signal_type]

        if len(asset_trades) < 5:
            return 0.55, "Historial parcial del activo insuficiente (a priori 55%)"

        # 2. Calcular probabilidades a priori
        successful_trades = [t for t in asset_trades if t.get("result") == "TAKE_PROFIT"]
        p_success = len(successful_trades) / len(asset_trades)

        # 3. Calcular verosimilitud condicional para características clave (Regime + OTE)
        regime_curr = current_fp.get("regime", "UNKNOWN")
        is_ote_curr = current_fp.get("is_in_ote", False)

        # Frecuencia en exitosos
        matches_success_regime = sum(1 for t in successful_trades if t.get("fingerprint", {}).get("regime") == regime_curr)
        matches_success_ote = sum(1 for t in successful_trades if t.get("fingerprint", {}).get("is_in_ote") == is_ote_curr)

        # Verosimilitudes (con suavizado de Laplace para evitar divisiones por cero)
        p_regime_given_success = (matches_success_regime + 1) / (len(successful_trades) + 2)
        p_ote_given_success = (matches_success_ote + 1) / (len(successful_trades) + 2)

        # Frecuencia global
        matches_total_regime = sum(1 for t in asset_trades if t.get("fingerprint", {}).get("regime") == regime_curr)
        matches_total_ote = sum(1 for t in asset_trades if t.get("fingerprint", {}).get("is_in_ote") == is_ote_curr)

        p_regime = (matches_total_regime + 1) / (len(asset_trades) + 2)
        p_ote = (matches_total_ote + 1) / (len(asset_trades) + 2)

        # 4. Teorema de Bayes
        # P(Éxito | Régimen, OTE) = [P(Régimen|Éxito) * P(OTE|Éxito) * P(Éxito)] / [P(Régimen) * P(OTE)]
        numerator = p_regime_given_success * p_ote_given_success * p_success
        denominator = p_regime * p_ote

        p_posterior = min(0.99, max(0.01, numerator / (denominator if denominator > 0 else 1.0)))

        # Normalización ponderada para evitar picos por Laplace
        p_posterior_normalized = (p_posterior + p_success) / 2.0

        return p_posterior_normalized, f"Bayes P(Win) = {p_posterior_normalized:.1%} | Priori P(Win) = {p_success:.1%} basado en {len(asset_trades)} trades."


class SignalGatekeeper:
    """
    Aplica los 4 filtros institucionales en secuencia.
    Separa señales aprobadas de las bloqueadas (modo auditoría).
    """

    def __init__(self, risk_manager: RiskManager):
        self._risk = risk_manager
        # Load dynamic configuration for thresholds
        self._config = _load_gatekeeper_config()
        self.bayes = BayesianInferenceEngine(blackbox)  # Motor Bayesiano v1.0

    async def process(
        self,
        signals: list[dict],
        df: pd.DataFrame,
        smc_map: dict,
        key_levels: list,
        interval: str,
        htf_bias: Optional[dict] = None,
        fib_data: Optional[dict] = None,
        context: Optional[GatekeeperContext] = None,
        regime_details: Optional[str] = None,
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
                    self._block(sig, "BLOCKED_BY_SESSION", "Peligro: Cierre de vela H4/D1 inminente (Ruido de cierre institucional)", result)
                return result

        # ── Filtro 0.6: Horario Destructivo (Auditoría v13.6) ────────────────
        # Horas con WR < 17% y R negativo: 09, 12, 13, 16 UTC
        blocked_hours = self._config.get('blocked_hours_utc', [9, 12, 13, 16])
        # [WEEKEND_OPTIMIZATION v10.0] Fines de semana no bloqueamos las 12 y 13 UTC (las noticias de Wall Street no aplican)
        is_weekend = now.weekday() >= 5
        if is_weekend:
            blocked_hours = [h for h in blocked_hours if h not in [12, 13]]

        if hour_of_day in blocked_hours:
            if not silent:
                logger.info(f"[GATEKEEPER] [HOUR_VETO] Hora {hour_of_day}:00 UTC bloqueada (históricamente destructiva).")
            for sig in signals:
                self._block(sig, "HOUR_VETO", f"Hora {hour_of_day}:00 UTC bloqueada por auditoría estadística (WR < 17%)", result)
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

        # Fase 1: Pre-filtrado secuencial rápido
        candidates = []
        for sig in signals[-10:]:
            sig_price = float(sig.get("price", 0))
            asset = sig.get("asset", "UNKNOWN")
            
            if market_price > 0:
                price_diff_pct = abs(sig_price - market_price) / market_price
                if price_diff_pct > 0.15:
                    logger.warning(f"🚨 [GATEKEEPER] DATA_POLLUTION detectada en {asset}: Precio {sig_price} incoherente vs Market {market_price}")
                    self._block(sig, "BLOCKED_BY_POLLUTION", f"Incoherencia de precio ({price_diff_pct:.1%}). Posible cruce de activos.", result)
                    continue

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
                    interval=interval
                )
                sig["confluence"] = confluence_result
            except Exception as e:
                logger.error(f"[GATEKEEPER] ConfluenceManager error: {e}")
                sig["confluence"] = {"score": 50, "confluences": []}

            sig_type = str(sig.get("signal_type", sig.get("type", ""))).upper()
            is_long = "LONG" in sig_type
            conf_score = sig["confluence"].get("score", 0)

            orig_sl = sig.get('stop_loss')
            orig_tp = sig.get('take_profit_3r')

            risk_data = self._risk.calculate_position(
                current_price=sig.get("price", 0),
                signal_type=sig_type,
                market_regime=regime_details or "RANGING",
                smc_data=smc_map,
                atr_value=sig.get("atr_value", 0.0),
                asset=sig.get("asset", "UNKNOWN"),
                htf_bias=htf_bias,
                fib_data=fib_data,
                confluence_score=conf_score
            )
            if orig_sl and orig_tp:
                risk_data['stop_loss'] = orig_sl
                risk_data['tp1'] = orig_tp
                risk_data['take_profit_3r'] = orig_tp
                
            sig.update(risk_data)

            # [200 IQ SPECIAL SL FILTER]
            if risk_data.get("sl_exceeded_max"):
                if not silent:
                    logger.warning(f"[GATEKEEPER] [SL_MAX_EXCEEDED] {asset} {sig_type} SL supera el límite máximo permitido para este activo.")
                self._block(sig, "SL_MAX_EXCEEDED", f"Stop Loss excede el porcentaje máximo permitido para {asset}.", result)
                continue

            if htf_bias:
                fractal_veto = False
                m1 = htf_bias.m1_regime
                w1 = htf_bias.w1_regime
                d1 = htf_bias.d1_regime
                h4 = htf_bias.h4_regime
                
                # [200 IQ ALTCOIN COUNTERTREND VETO]
                if not is_long and asset.upper() in ["ETHUSDT", "SOLUSDT"]:
                    if d1 in ["MARKUP", "BULLISH"] or h4 in ["MARKUP", "BULLISH"]:
                        reason = f"Veto Tendencial Altcoin: Prohibido abrir SHORT en {asset} mientras H4/D1 sea alcista (H4: {h4}, D1: {d1})"
                        if not silent:
                            logger.warning(f"[GATEKEEPER] [COUNTERTREND_VETO] {asset} SHORT bloqueado por régimen alcista H4/D1.")
                        self._block(sig, "COUNTERTREND_VETO", reason, result)
                        continue

                if is_long:
                    if (m1 == 'MARKDOWN' and w1 == 'MARKDOWN') or (d1 == 'MARKDOWN' and h4 == 'MARKDOWN'):
                        fractal_veto = True
                        reason = f"Veto Fractal: Tendencia macro bajista. Mensual/Semanal en Markdown ({m1}/{w1}) o Diario/H4 en Markdown ({d1}/{h4}). Prohibido buscar Longs."
                else:
                    if (m1 == 'MARKUP' and w1 == 'MARKUP') or (d1 == 'MARKUP' and h4 == 'MARKUP'):
                        fractal_veto = True
                        reason = f"Veto Fractal: Tendencia macro alcista. Mensual/Semanal en Markup ({m1}/{w1}) o Diario/H4 en Markup ({d1}/{h4}). Prohibido buscar Shorts."
                
                if fractal_veto:
                    # Inferencia Bayesiana en vivo
                    fp = blackbox.extract_fingerprint(sig)
                    p_win, bayes_reason = self.bayes.estimate_probability(asset, sig_type, fp)
                    
                    if p_win >= 0.57:
                        # [BAYESIAN BYPASS ACTIVE]
                        if not silent:
                            logger.info(f"🔮 [GATEKEEPER] [BAYES_BYPASS] {asset} {sig_type} ignorando Veto Fractal por probabilidad de exito favorable: {p_win:.1%}")
                        fractal_veto = False
                        
                        # Agregar confirmación al checklist de confluencia
                        checklist = sig.get("confluence", {}).get("checklist", [])
                        checklist.append({
                            "factor": "Bayes Shield",
                            "status": "CONFIRMADO",
                            "detail": f"🛡️ Bypass Probabilistico ({bayes_reason})"
                        })
                        
                        # Mitigación de riesgo: reducir riesgo a la mitad para trade contra-tendencia macro
                        sig["risk_pct"] = round(sig.get("risk_pct", 1.0) * 0.5, 2)
                        sig["position_size_usdt"] = round(sig.get("position_size_usdt", 100) * 0.5, 2)
                    elif conf_score >= 95:
                        if not silent:
                            logger.info(f"🚀 [GATEKEEPER] [SOVEREIGN_BYPASS] {asset} ignorando Veto Fractal por Score Extremo ({conf_score}%).")
                        fractal_veto = False
                    else:
                        if not silent:
                            logger.warning(f"[GATEKEEPER] [FRACTAL_VETO] {asset} {sig_type} bloqueado por alineacion macro negativa.")
                        self._block(sig, "FRACTAL_VETO", f"{reason} | {bayes_reason}", result)
                        continue

            # Dynamic alignment veto thresholds based on regime
            alignment_veto = False
            # Base required score per regime – now driven by config
            conf_thresholds = self._config.get('confidence_thresholds', {})
            default_score = conf_thresholds.get('DEFAULT', 65)
            # Determine required score based on regime and bias
            if regime_bias == "BULLISH" and not is_long:
                # Longs contra tendencia bajista
                required_score = conf_thresholds.get(regime_type.upper(), default_score)
                if conf_score < required_score:
                    alignment_veto = True
            elif regime_bias == "BEARISH" and is_long:
                # Shorts contra tendencia alcista
                required_score = conf_thresholds.get(regime_type.upper(), default_score)
                if conf_score < required_score:
                    alignment_veto = True
            # High score override
            if alignment_veto and conf_score >= 92:
                if not silent:
                    logger.info(f"⚡ [GATEKEEPER] [APEX_OVERRIDE] {asset} permitiendo contratendencia por alta absorción ({conf_score}%).")
                alignment_veto = False
            # Block if still vetoed
            if alignment_veto:
                if not silent:
                    logger.info(f"[GATEKEEPER] [DELTA_BLOCK] Desalineación macroestructural ({sig_type} vs {regime_type}). Confianza {conf_score}% insuficiente.")
                self._block(sig, "DELTA_VETO", f"Conflicto de Tendencia: Intentando operar contra {regime_type} con confianza insuficiente ({conf_score}%)", result)
                continue

            candidates.append(sig)

        # Fase 2: Inferencia de IA Concurrente para todas las señales sobrevivientes
        if candidates:
            tasks = [validator_agent.validate(sig) for sig in candidates]
            ai_results = await asyncio.gather(*tasks)
            for sig, ai_audit in zip(candidates, ai_results):
                sig["ai_audit"] = ai_audit
            # ---- Nuevo filtro RVOL ----
            for sig in list(candidates):
                rvol = float(sig.get('rvol', 0))
                # Determine required RVOL per regime – driven by config
                rvol_cfg = self._config.get('rvol_thresholds', {})
                if regime_type.startswith('STRONG'):
                    min_rvol = rvol_cfg.get('STRONG', 1.0)
                elif regime_type == 'CHOPPY':
                    min_rvol = rvol_cfg.get('CHOPPY', 1.2)
                else:
                    min_rvol = rvol_cfg.get('DEFAULT', 1.0)
                if rvol < min_rvol:
                    sig["blocked_reason"] = f"RVOL_VETO: Volumen relativo {rvol:.2f} < requerido {min_rvol} para régimen {regime_type}"
                    self._block(sig, "RVOL_VETO", sig["blocked_reason"], result)
                    candidates.remove(sig)

        # Fase 3: Post-filtrado secuencial
        for sig in candidates:
            asset = sig.get("asset", "UNKNOWN")
            sig_type = str(sig.get("signal_type", sig.get("type", ""))).upper()
            is_long = "LONG" in sig_type
            conf_score = sig["confluence"].get("score", 0)
            score = conf_score
            
            # Aplicar veredicto de la validación de la IA
            ai_audit = sig["ai_audit"]
            if not ai_audit.get("approved", True):
                sig["blocked_reason"] = f"AI_VETO: {ai_audit.get('ai_reasoning')}"
                if not silent:
                    logger.warning(f"🤖 [VALIDATOR] {sig.get('asset')} Vetoed: {ai_audit.get('ai_reasoning')}")
                self._block(sig, "AI_VETO", ai_audit.get("ai_reasoning"), result)
                continue

            # ── [FASE 1] Veto por Régimen Lateral (CHOPPY) ──
            if is_choppy and conf_score < choppy_threshold:
                 if not silent:
                     logger.warning(f"⚠️ [GATEKEEPER] [DELTA_BLOCK] {interval} CHOPPY veto: Score {conf_score}% < {choppy_threshold}%")
                 self._block(sig, "BLOCKED_BY_DELTA", f"Mercado Picadora (Choppy): Se requiere al menos {choppy_threshold}% de confianza (Actual: {conf_score}%)", result)
                 continue

            # ── Filtro 1: Jerarquía de Timeframes ──
            if htf_bias:
                if score < 65 and htf_bias.direction != "NEUTRAL":
                    if (htf_bias.direction == "BULLISH" and not is_long) or \
                       (htf_bias.direction == "BEARISH" and is_long):
                        self._block(sig, "SIGMA_VETO", f"Veto de Tendencia: La dirección HTF es opuesta y la confianza es baja ({score}%)", result)
                        continue

            # ── Filtro 2.7: Anti-Spam de Volatilidad ──
            # [BACKTEST_FIX] Usar timestamp de la señal en lugar de CPU time.time()
            try:
                now_ts = pd.to_datetime(sig.get("timestamp"), utc=True).timestamp()
            except Exception:
                now_ts = time.time()

            if asset not in SIGNALS_HISTORY:
                SIGNALS_HISTORY[asset] = deque(maxlen=20)
            
            sig_type_spam = "LONG" if "LONG" in str(sig.get("signal_type", sig.get("type", ""))).upper() else "SHORT"
            recent_for_asset = list(SIGNALS_HISTORY[asset])
            contradictory_count = 0
            for item in recent_for_asset:
                ts = item[0]
                old_type = item[-1]
                if now_ts - ts < 900 and old_type != sig_type_spam:
                    contradictory_count += 1

            max_contradictory = 5 if interval in ["1m", "5m"] else 3
            if contradictory_count >= max_contradictory:
                self._block(sig, "BLOCKED_CHOPPY", f"Filtro Anti-Spam: Demasiados cambios de dirección rápidos (Flips) en este activo.", result)
                continue
            
            SIGNALS_HISTORY[asset].append((now_ts, "APPROVED", sig_type_spam))

            # Conflict Manager (IA vs SMC) - DESACTIVADO A SOLICITUD DEL USUARIO
            # if context.ml_projection and "direction" in context.ml_projection:
            #     ml_dir = str(context.ml_projection["direction"]).upper()
            #     if is_long and ml_dir == "BAJISTA":
            #         self._block(sig, "STAND_BY", "[CONFLICT MANAGER] ML proyecta Venta (Stand-by)", result)
            #         continue
            #     if not is_long and ml_dir == "ALCISTA":
            #         self._block(sig, "STAND_BY", "[CONFLICT MANAGER] ML proyecta Compra (Stand-by)", result)
            #         continue

            # ── Filtro 2.6: Mitigación Instantánea (Volatilidad Ghost) ──
            try:
                candle_spread = ((df["high"].iloc[-1] - df["low"].iloc[-1]) / df["close"].iloc[-1]) * 100
                max_spread = 2.5 if val <= 15 else (6.0 if val <= 240 else 10.0)
                if candle_spread > max_spread:
                    self._block(sig, "BLOCKED_BY_VOLATILITY", f"Volatilidad Extrema: Movimiento de {candle_spread:.2f}% en una sola vela. Prevención de Slippage.", result)
                    continue
            except:
                pass

            # ── Filtro 4: R:R Mínimo y Zona de Valor OTE ──
            rr_res = self._risk.validate_signal(sig)
            sig["rr_ratio"]     = rr_res["rr_ratio"]
            sig["trade_quality"] = rr_res["trade_quality"]

            ote_data = sig.get("fib_ote", {})
            if ote_data:
                is_in_zone = ote_data.get("is_in_ote", False)
                # Allow a small tolerance around the OTE zone (configurable)
                ote_cfg = self._config.get('ote_tolerance_pct', 0.5)
                distance_pct = ote_data.get('distance_pct', 0)  # percent distance from zone centre if available
                # If within tolerance or confidence already high, accept
                if not is_in_zone and distance_pct > ote_cfg and conf_score < self._config.get('ote_min_confidence', 70):
                    self._block(sig, "VALUE_ZONE_VETO", "Entrada Ineficiente: El precio no está en zona OTE (Optimal Trade Entry) o Descuento/Premium.", result)
                    continue

            min_rr = self._risk.min_rr
            if not rr_res.get("approved", False):
                if not silent:
                    logger.info(f"[GATEKEEPER] 🔴 DELTA BLOCK: R:R {sig.get('rr_ratio', 0):.2f} | Reason: {rr_res.get('reason', 'N/A')}")
                self._block(sig, "DELTA_VETO", f"Matemática desfavorable: Ratio R:R de {sig.get('rr_ratio', 0):.2f} es inferior al mínimo institucional ({min_rr})", result)
                continue

            # Adjust min_score based on regime stress and asset
            stress_premium = 15 if regime_stress else 0
            if asset == "BTCUSDT":
                base_min = 25
            elif asset == "SOLUSDT":
                base_min = 45
            elif asset == "ETHUSDT":
                base_min = 35
            else:
                base_min = 35
            # Dynamic boost for strong regimes
            if regime_type.startswith('STRONG'):
                base_min += 10
            elif regime_type == 'CHOPPY':
                base_min += 5
            min_score = base_min + stress_premium
            
            if regime_stress and not silent:
                logger.warning(f"[GATEKEEPER] STRESS DETECTADO: Elevando umbral de score (+{stress_premium}%)")
            
            if not silent:
                logger.info(f"[GATEKEEPER_AUDIT] Asset: {asset} | Score: {score}% | Required: {min_score}% (Regime: {regime_type})")
            
            # Final fallback threshold – direction-aware (Auditoría v13.6)
            # Para activos principales con calibración adaptativa, respetamos el min_score calculado dinámicamente.
            # Para cortos en altcoins volátiles, sumamos un offset de +5 por seguridad.
            # Para activos genéricos, usamos el fallback direccional estándar.
            asset_upper = asset.upper()
            if asset_upper in ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT", "BNBUSDT", "LINKUSDT", "PAXGUSDT", "XAGUSDT"]:
                min_score_final = min_score
                if not is_long and asset_upper != "BTCUSDT":
                    min_score_final += 5  # Offset de seguridad para cortos en altcoins volátiles
            else:
                min_score_long = self._config.get('min_score_long', 70)
                min_score_short = self._config.get('min_score_short', 75)
                min_score_final = min_score_long if is_long else min_score_short
                min_score_final = max(min_score_final, min_score)

            if score < min_score_final:
                reason = sig.get("confluence", {}).get("veto_reason") or f"Confianza {score}% < {min_score_final}% ({'LONG' if is_long else 'SHORT'} - Activo: {asset})"
                self._block(sig, "LOW_CONFLUENCE", reason, result)
                continue
            
            # ── Filtro 5.5: Black Box (Memoria de Errores) ──
            bb_check = blackbox.check_setup(sig)
            sig["blackbox"] = bb_check
            if bb_check["match"]:
                if not silent:
                    logger.warning(f"🧠 [GATEKEEPER] [BLACKBOX_VETO] {asset}: {bb_check['reason']}")
                self._block(sig, "BLACKBOX_VETO", bb_check["reason"], result)
                continue

            # ── Filtro 6: Path Traversal ──
            if not self._is_alive(sig, df_time, df_low, df_high, now_utc):
                self._block(sig, "BLOCKED_EXPIRED", "Señal expirada o tocó SL/TP en el origen", result)
                continue

            # ✅ Aprobada
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
        sig["rejection_reason"] = reason
        
        # ── DE-DUPLICADOR DE VETOS ──
        # Evitar registrar alertas y bloqueos repetitivos en un intervalo de 15 minutos (900s)
        asset = sig.get("asset", "UNKNOWN")
        now = time.time()
        
        if asset not in SIGNALS_HISTORY:
            SIGNALS_HISTORY[asset] = deque(maxlen=20)
            
        # Comprobar si hay una alerta idéntica en los últimos 15 minutos
        duplicate = False
        for old_time, old_status, old_type in SIGNALS_HISTORY[asset]:
            if old_status == status and old_type == sig.get("signal_type") and (now - old_time) < 900:
                duplicate = True
                break
                
        if not duplicate:
            SIGNALS_HISTORY[asset].append((now, status, sig.get("signal_type")))
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
