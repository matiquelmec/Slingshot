// app/utils/ftmoSpecs.ts

/**
 * Categorías de Mercado disponibles en Slingshot Trading
 */
export type MarketCategory = 'ALL' | 'FTMO_INSTITUTIONAL' | 'CRYPTO_ALTCOINS';

/**
 * Especificaciones de contrato oficiales de FTMO MetaTrader 5 (MT5 / cTrader).
 * 
 * - METALES:
 *   - XAUUSD (Oro): 1 Lote = 100 Onzas troy (Contract Size: 100).
 *   - XAGUSD (Plata): 1 Lote = 5000 Onzas (Contract Size: 5000).
 * 
 * - ÍNDICES:
 *   - US100 / NAS100 (Nasdaq): 1 Lote = 1 Contrato (Contract Size: 1).
 *   - US30 (Dow Jones): 1 Lote = 1 Contrato (Contract Size: 1).
 *   - US500 (S&P 500): 1 Lote = 1 Contrato (Contract Size: 1).
 * 
 * - FOREX:
 *   - EURUSD, GBPUSD, USDJPY, AUDUSD: 1 Lote = 100,000 Unidades base (Contract Size: 100,000).
 * 
 * - CRIPTO FTMO:
 *   - BTCUSD: 1 Lote = 1 BTC (Contract Size: 1).
 *   - ETHUSD: 1 Lote = 10 ETH (Contract Size: 10).
 *   - SOLUSD: 1 Lote = 10 SOL (Contract Size: 10).
 *   - AVAXUSD: 1 Lote = 10 AVAX (Contract Size: 10).
 */
export const FTMO_CONTRACT_SIZES: Record<string, number> = {
    // Metales & Commodities
    'XAU': 100,
    'XAUUSD': 100,
    'GOLD': 100,
    'PAXG': 1,      // Tokenized Gold 1:1 on Binance/Bitunix
    'PAXGUSDT': 1,
    'XAG': 5000,
    'XAGUSD': 5000,
    'SILVER': 5000,
    'HG': 25000,
    'HGUSD': 25000,
    'COPPER': 25000,

    // Índices
    'US100': 1,
    'NAS100': 1,
    'USTEC': 1,
    'US30': 1,
    'DJ30': 1,
    'US500': 1,
    'SPX500': 1,
    'ES': 1,

    // Forex Majors
    'EURUSD': 100000,
    'GBPUSD': 100000,
    'USDJPY': 100000,
    'AUDUSD': 100000,
    'USDCAD': 100000,

    // Cripto FTMO & Exchange
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
    'ATOM': 100,
    'ATOMUSD': 100,
    'ATOMUSDT': 100,
};

/**
 * Lista de activos institucionales soportados en FTMO MT5
 */
export const FTMO_INSTITUTIONAL_SYMBOLS = new Set([
    'XAUUSD', 'GOLD', 'PAXGUSDT', 'XAGUSD', 'HGUSD', 'COPPER',
    'US100', 'NAS100', 'US30', 'DJ30', 'US500', 'SPX500',
    'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD',
    'BTCUSD', 'BTCUSDT', 'ETHUSD', 'ETHUSDT', 'SOLUSD', 'SOLUSDT', 'AVAXUSD', 'AVAXUSDT'
]);

/**
 * Identifica la categoría de mercado de un símbolo
 */
export function getAssetMarketCategory(symbol: string): 'FTMO_INSTITUTIONAL' | 'CRYPTO_ALTCOINS' {
    const cleanSym = symbol.toUpperCase().replace('.S', '').replace('.P', '');
    if (
        FTMO_INSTITUTIONAL_SYMBOLS.has(cleanSym) || 
        cleanSym.startsWith('XAU') || 
        cleanSym.startsWith('US100') || 
        cleanSym.startsWith('US30') || 
        cleanSym.startsWith('US500') || 
        cleanSym.startsWith('HG') || 
        cleanSym.startsWith('EUR')
    ) {
        return 'FTMO_INSTITUTIONAL';
    }
    return 'CRYPTO_ALTCOINS';
}

/**
 * Calcula los lotes exactos y listos para colocar en la casilla "Volumen" de MetaTrader 5.
 * @param symbol Par de trading (ej. XAUUSD, BTCUSDT, EURUSD, US100)
 * @param riskUsd Riesgo fijo en dólares (ej. $750 para $100k, $1,500 para $200k)
 * @param slDist Distancia en dólares del Stop Loss (|Entrada - SL|)
 * @returns Número de lotes exactos redondeados a 2 decimales para MT5
 */
export function calculateMt5Lots(symbol: string, riskUsd: number, slDist: number): number {
    if (!slDist || slDist <= 0 || !riskUsd || riskUsd <= 0) return 0.01;
    
    // Normalizar símbolo
    const rawSym = symbol.toUpperCase().replace('.S', '').replace('.P', '');
    const cleanSym = rawSym.replace('USDT', '').replace('USD', '');
    
    const contractSize = FTMO_CONTRACT_SIZES[rawSym] || FTMO_CONTRACT_SIZES[cleanSym] || 1;
    
    // Para Forex: SL Distancia en pips/precio (ej. 0.0015) -> Riesgo / (Dist * 100,000)
    // Para Metales: SL Distancia en dólares (ej. $5.00) -> Riesgo / (Dist * 100 onzas)
    // Para Cripto/Índices: Riesgo / (Dist * Contract Size)
    const rawLots = riskUsd / (slDist * contractSize);
    
    // Redondear a 2 decimales y asegurar mínimo 0.01 lote
    const finalLots = Math.max(0.01, Math.round(rawLots * 100) / 100);
    return finalLots;
}
