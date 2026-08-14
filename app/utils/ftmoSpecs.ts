// app/utils/ftmoSpecs.ts

/**
 * Especificaciones de contrato oficiales de FTMO MetaTrader 5 (MT5 / cTrader).
 * En MT5 para Crypto, brokers como FTMO usan tamaños de contrato específicos por lote:
 * - BTCUSD: 1 Lote = 1 BTC (Contract Size: 1)
 * - ETHUSD: 1 Lote = 10 ETH (Contract Size: 10)
 * - SOLUSD: 1 Lote = 10 SOL (Contract Size: 10)
 * - AVAXUSD: 1 Lote = 10 AVAX (Contract Size: 10)
 * - NEARUSD / INJUSD / TIAUSD: 1 Lote = 10 o 100 Contratos
 */
export const FTMO_CONTRACT_SIZES: Record<string, number> = {
    'BTC': 1,
    'BTCUSD': 1,
    'BTCUSDT': 1,
    'ETH': 10,
    'ETHUSD': 10,
    'ETHUSDT': 10,
    'SOL': 10,
    'SOLUSD': 10,
    'SOLUSDT': 10,
    'AVAX': 10,
    'AVAXUSD': 10,
    'AVAXUSDT': 10,
    'INJ': 10,
    'INJUSD': 10,
    'INJUSDT': 10,
    'NEAR': 10,
    'NEARUSD': 10,
    'NEARUSDT': 10,
    'RENDER': 10,
    'RENDERUSD': 10,
    'RENDERUSDT': 10,
    'FET': 100,
    'FETUSD': 100,
    'FETUSDT': 100,
    'SUI': 100,
    'SUIUSD': 100,
    'SUIUSDT': 100,
    'TIA': 10,
    'TIAUSD': 10,
    'TIAUSDT': 10,
    'ATOM': 10,
    'ATOMUSD': 10,
    'ATOMUSDT': 10,
};

/**
 * Calcula los lotes exactos y listos para colocar en la casilla "Volumen" de MetaTrader 5.
 * @param symbol Par de trading (ej. BTCUSDT, ETHUSD)
 * @param riskUsd Riesgo fijo en dólares (ej. $750 para $100k, $1,500 para $200k)
 * @param slDist Distancia en dólares del Stop Loss (|Entrada - SL|)
 * @returns Número de lotes exactos redondeados a 2 decimales para MT5
 */
export function calculateMt5Lots(symbol: string, riskUsd: number, slDist: number): number {
    if (!slDist || slDist <= 0 || !riskUsd || riskUsd <= 0) return 0.01;
    
    // Normalizar símbolo
    const cleanSym = symbol.toUpperCase().replace('USDT', '').replace('USD', '');
    const contractSize = FTMO_CONTRACT_SIZES[cleanSym] || 1;
    
    // Monedas necesarias = Riesgo / Distancia SL
    const coinsNeeded = riskUsd / slDist;
    
    // Lotes MT5 = Monedas / Contract Size
    const rawLots = coinsNeeded / contractSize;
    
    // Redondear a 2 decimales y asegurar mínimo 0.01 lote
    const finalLots = Math.max(0.01, Math.round(rawLots * 100) / 100);
    return finalLots;
}
