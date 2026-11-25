
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

# Activos que no existen en Binance Futures y deben ser ignorados por el provider
FUTURES_EXCLUDED_SYMBOLS = ["EURUSDT", "USDCUSDT"]

# ── Cliente Global Throttled (v8.7.0) ─────────────────────────────────────────
_shared_client: Optional[httpx.AsyncClient] = None
_semaphore = asyncio.Semaphore(3) # Máximo 3 peticiones simultáneas a Binance

async def get_client() -> httpx.AsyncClient:
    global _shared_client
    if _shared_client is None or _shared_client.is_closed:
        _shared_client = httpx.AsyncClient(
            timeout=httpx.Timeout(3.5, connect=2.0),
            verify=False,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) SlingshotQuant/10.0"},
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _shared_client

async def refresh_symbol_onchain(symbol: str, force: bool = False):
    """
    Lógica de refresco resiliente multi-exchange (Bybit V5 -> OKX -> Binance) para VPS y Cloud WAF.
    v8.7.0+: Incluye TTL de 45s para evitar redundancia entre workers.
    """
    symbol = symbol.upper()
    
    if symbol in FUTURES_EXCLUDED_SYMBOLS:
        logger.debug(f"[ONCHAIN] {symbol} saltado (Activo Spot-Only)")
        return

    # 0. Verificar TTL — Evita spam si varios workers piden el dato
    async with _lock:
        if not force and symbol in _cache:
            age = datetime.now().timestamp() - _cache[symbol].last_updated
            if age < 45:
                return

    # 1. Intentar obtener datos multi-exchange con Semáforo
    success = False
    new_oi = 0.0
    new_fr = 0.0
    provider_used = ""
    bybit_sym = "PAXGUSDT" if symbol == "XAUUSDT" else symbol
    last_error = "Desconocido"
    
    client = await get_client()
    
    async with _semaphore:
        # 1A. Primario: Bybit V5 Linear (HTTP 200 estable desde datacenter VPS)
        try:
            b_res = await client.get(
                "https://api.bybit.com/v5/market/tickers",
                params={"category": "linear", "symbol": bybit_sym},
            )
            if b_res.status_code == 200:
                b_json = b_res.json()
                b_list = (b_json.get("result") or {}).get("list") or []
                if b_json.get("retCode") == 0 and b_list:
                    item = b_list[0]
                    val = float(item.get("openInterest") or 0.0)
                    if val > 0:
                        new_oi = val
                        new_fr = float(item.get("fundingRate") or 0.0) * 100.0
                        provider_used = "BYBIT"
                        success = True
        except Exception as e:
            last_error = f"Bybit err: {e}"

        # 1B. Secundario: OKX Public Swap (incluye XAU-USDT-SWAP)
        if not success:
            try:
                inst_id = f"{symbol.replace('USDT', '')}-USDT-SWAP"
                okx_oi_r = await client.get(
                    "https://www.okx.com/api/v5/public/open-interest",
                    params={"instType": "SWAP", "instId": inst_id},
                )
                if okx_oi_r.status_code == 200:
                    okx_data = okx_oi_r.json().get("data") or []
                    if okx_data:
                        val = float(okx_data[0].get("oiCcy") or okx_data[0].get("oi") or 0.0)
                        if val > 0:
                            new_oi = val
                            okx_fr_r = await client.get(
                                "https://www.okx.com/api/v5/public/funding-rate",
                                params={"instId": inst_id},
                            )
                            if okx_fr_r.status_code == 200:
                                fr_list = okx_fr_r.json().get("data") or []
                                if fr_list:
                                    new_fr = float(fr_list[0].get("fundingRate") or 0.0) * 100.0
                            provider_used = "OKX"
                            success = True
            except Exception as e:
                last_error = f"OKX err: {e}"

        # 1C. Terciario: Binance Mirrors
        if not success:
            for base_url in MIRRORS:
                try:
                    oi_r = await client.get(f"{base_url}/fapi/v1/openInterest", params={"symbol": symbol})
                    if oi_r.status_code == 200:
                        val = float(oi_r.json().get("openInterest", 0))
                        if val > 0 or symbol not in ["BTCUSDT", "ETHUSDT", "SOLUSDT"]:
                            new_oi = val
                            fr_r = await client.get(f"{base_url}/fapi/v1/fundingRate", params={"symbol": symbol, "limit": 1})
                            if fr_r.status_code == 200:
                                fr_data = fr_r.json()
                                if isinstance(fr_data, list) and len(fr_data) > 0:
                                    new_fr = float(fr_data[-1].get("fundingRate", 0)) * 100
                            provider_used = "BINANCE"
                            success = True
                            break
                    elif oi_r.status_code == 429:
                        last_error = "Rate Limit 429"
                        logger.warning(f"[ONCHAIN] ⚠️ Binance Rate Limit (429) detectado en {base_url}")
                        await asyncio.sleep(2)
                    else:
                        last_error = f"HTTP {oi_r.status_code}"
                        logger.debug(f"[ONCHAIN] Mirror {base_url} retornó {oi_r.status_code} para {symbol}")
                except Exception as e:
                    last_error = f"Error en mirror {base_url}: {str(e)}"
                    logger.warning(f"[ONCHAIN] Mirror {base_url} falló para {symbol}: {e}")
                    continue

    # 2. Actualizar Caché Global
    async with _lock:
        if symbol not in _cache:
            _cache[symbol] = OnChainState(symbol=symbol)
            
        state = _cache[symbol]
        
        if success:
            # Hidratación Histórica Inteligente (~1h atrás) según proveedor activo
            if state.reference_oi is None or state.reference_oi == 0:
                try:
                    if provider_used == "BYBIT":
                        hist_r = await client.get(
                            "https://api.bybit.com/v5/market/open-interest",
                            params={"category": "linear", "symbol": bybit_sym, "intervalTime": "5min", "limit": 12},
                        )
                        if hist_r.status_code == 200:
                            hist_json = hist_r.json()
                            hist_list = (hist_json.get("result") or {}).get("list") or []
                            if hist_json.get("retCode") == 0 and hist_list:
                                state.reference_oi = float(hist_list[-1].get("openInterest", new_oi))
                                logger.info(f"[ONCHAIN] 📚 Referencia Histórica (Bybit) cargada para {symbol}: {state.reference_oi:,.0f}")
                    elif provider_used == "BINANCE":
                        hist_r = await client.get(f"{MIRRORS[0]}/futures/data/openInterestHist", params={"symbol": symbol, "period": "5m", "limit": 12})
                        if hist_r.status_code == 200:
                            hist_data = hist_r.json()
                            if isinstance(hist_data, list) and len(hist_data) > 0:
                                state.reference_oi = float(hist_data[0].get("sumOpenInterest", new_oi))
                                logger.info(f"[ONCHAIN] 📚 Referencia Histórica cargada para {symbol}: {state.reference_oi:,.0f}")
                except Exception as e:
                    logger.debug(f"[ONCHAIN] Fallback de referencia histórica para {symbol}: {e}")
                
                if state.reference_oi is None or state.reference_oi == 0:
                    state.reference_oi = new_oi
                    logger.debug(f"[ONCHAIN] 🔄 Fallback de referencia para {symbol} (Using current OI)")
            
            # Calcular Delta
            if state.reference_oi > 0:
                old_delta = state.delta_session
                state.delta_session = ((new_oi - state.reference_oi) / state.reference_oi) * 100
            
            state.oi = new_oi
            state.funding_rate = new_fr
            state.last_updated = datetime.now().timestamp()
            
            # Bias Simplificado (v8.5.9) - Alineado con Frontend (BULLISH_ACCUMULATION / BEARISH_DISTRIBUTION)
            if state.delta_session > 0.05: state.bias = "BULLISH_ACCUMULATION"
            elif state.delta_session < -0.05: state.bias = "BEARISH_DISTRIBUTION"
            elif state.funding_rate > 0.01: state.bias = "OVERLEVERAGED"
            else: state.bias = "NEUTRAL"
        else:
            # [HARDENING v8.7.0] Solo loguear error real si no es un activo excluido
            logger.error(f"❌ [ONCHAIN-PROVIDER] FALLO TOTAL en {symbol} | Último error: {last_error}")

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
            "is_spot_only": False,
            "whale_alerts_count": 0, # Placeholder (v8.5.9)
            "ts": s.last_updated
        }
    
    is_spot = sym_up in FUTURES_EXCLUDED_SYMBOLS
    return {
        "symbol": symbol, 
        "oi_delta_pct": 0, 
        "funding_rate": 0, 
        "onchain_bias": "NEUTRAL", 
        "is_spot_only": is_spot,
        "whale_alerts_count": 0,
        "ts": 0
    }
