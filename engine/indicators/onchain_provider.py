
import httpx
import asyncio
from typing import Dict, Optional, List
from datetime import datetime
from engine.core.logger import logger
from dataclasses import dataclass, field, asdict

@dataclass
class OnChainState:
    symbol: str
    oi: float = 0.0
    funding_rate: float = 0.0
    delta_session: float = 0.0
    bias: str = "NEUTRAL"
    last_updated: float = 0.0
    reference_oi: Optional[float] = None

# ── Caché Global ──────────────────────────────────────────────────────────────
_cache: Dict[str, OnChainState] = {}
_lock = asyncio.Lock()

MIRRORS = [
    "https://fapi.binance.com",
    "https://fapi1.binance.com",
    "https://fapi2.binance.com",
    "https://fapi3.binance.com"
]

async def get_onchain_data(symbol: str) -> OnChainState:
    """Retorna los datos on-chain desde el caché central."""
    async with _lock:
        if symbol not in _cache:
            _cache[symbol] = OnChainState(symbol=symbol.upper())
        return _cache[symbol]

async def refresh_all_onchain(symbols: List[str]):
    """
    Refresco centralizado de métricas on-chain para todos los activos VIP.
    Optimizado para evitar rate-limits y validar datos basura (ceros).
    """
    tasks = [refresh_symbol_onchain(s) for s in symbols]
    await asyncio.gather(*tasks)

async def refresh_symbol_onchain(symbol: str):
    """Lógica de refresco resiliente para un símbolo específico."""
    symbol = symbol.upper()
    
    # 1. Intentar obtener datos desde mirrors
    success = False
    new_oi = 0.0
    new_fr = 0.0
    
    for base_url in MIRRORS:
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                # Obtenemos OI y FR secuencialmente para máxima estabilidad
                oi_r = await client.get(f"{base_url}/fapi/v1/openInterest", params={"symbol": symbol})
                if oi_r.status_code == 200:
                    val = float(oi_r.json().get("openInterest", 0))
                    # Validación de Seguridad: Si es un activo mayor y el OI es 0, es un error del mirror
                    if val > 0 or symbol not in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
                        new_oi = val
                        
                        # Si el OI es válido, pedimos el Funding
                        fr_r = await client.get(f"{base_url}/fapi/v1/fundingRate", params={"symbol": symbol, "limit": 1})
                        if fr_r.status_code == 200:
                            fr_data = fr_r.json()
                            if isinstance(fr_data, list) and len(fr_data) > 0:
                                new_fr = float(fr_data[-1].get("fundingRate", 0)) * 100
                        
                        success = True
                        break
        except Exception as e:
            continue

    # 2. Actualizar Caché Global
    async with _lock:
        if symbol not in _cache:
            _cache[symbol] = OnChainState(symbol=symbol)
            
        state = _cache[symbol]
        
        if success:
            # Hidratación de referencia histórica si no existe
            if state.reference_oi is None or state.reference_oi == 0:
                state.reference_oi = new_oi
            
            # Calcular Delta
            if state.reference_oi > 0:
                old_delta = state.delta_session
                state.delta_session = ((new_oi - state.reference_oi) / state.reference_oi) * 100
                if state.delta_session != old_delta:
                    logger.info(f"[ONCHAIN] ⚓ {symbol} | OI: {new_oi:,.0f} | Δ: {state.delta_session:+.6f}% | FR: {new_fr:.5f}%")
            
            state.oi = new_oi
            state.funding_rate = new_fr
            state.last_updated = datetime.now().timestamp()
            
            # Bias Simplificado (v8.5.9) - Alineado con Frontend (BULLISH_ACCUMULATION / BEARISH_DISTRIBUTION)
            if state.delta_session > 0.1: state.bias = "BULLISH_ACCUMULATION"
            elif state.delta_session < -0.1: state.bias = "BEARISH_DISTRIBUTION"
            elif state.funding_rate > 0.01: state.bias = "OVERLEVERAGED"
            else: state.bias = "NEUTRAL"
        else:
            logger.warning(f"[ONCHAIN-PROVIDER] ⚠️ No se pudo refrescar {symbol}. Manteniendo caché previo.")

def get_onchain_summary(symbol: str) -> Dict:
    """Helper para obtener un dict listo para JSON alineado con el Frontend."""
    sym_up = symbol.upper()
    if sym_up in _cache:
        s = _cache[sym_up]
        return {
            "symbol": s.symbol,
            "oi_delta_pct": s.delta_session,
            "funding_rate": s.funding_rate,
            "onchain_bias": s.bias,
            "whale_alerts_count": 0, # Placeholder (v8.5.9)
            "ts": s.last_updated
        }
    return {
        "symbol": symbol, 
        "oi_delta_pct": 0, 
        "funding_rate": 0, 
        "onchain_bias": "NEUTRAL", 
        "whale_alerts_count": 0,
        "ts": 0
    }
