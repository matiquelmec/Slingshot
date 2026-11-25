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
    'GER40': 25,
    'DAX40': 25,
    'DE40': 25,
    'UK100': 1,
    'US2000': 1,
    'EU50': 1,
    'UKOIL': 100,

    // Forex Majors & Cruces
    'EURUSD': 100000,
    'GBPUSD': 100000,
    'GBPJPY': 100000,
    'USDJPY': 100000,
    'AUDUSD': 100000,
    'USDCAD': 100000,

    // Cripto FTMO & Exchange (Símbolos reales verificados en FTMO MT5)
    'BTC': 1,
    'BTCUSD': 1,
    'BTCUSDT': 1,
    'ETH': 1,
    'ETHUSD': 1,
    'ETHUSDT': 1,
    'SOL': 1,
    'SOLUSD': 1,
    'SOLUSDT': 1,
    'DOT': 10,
    'DOTUSD': 10,
    'DOTUSDT': 10,
    'XRP': 100,
    'XRPUSD': 100,
    'XRPUSDT': 100,
    'USOIL': 100,
};

export const FTMO_SWING_AUDITED_UNIVERSE = ['XAUUSD', 'US100', 'XAGUSD', 'UK100'] as const;

/**
 * Lista de activos institucionales soportados en FTMO MT5 (sin pares *USDT de Bitunix)
 */
export const FTMO_INSTITUTIONAL_SYMBOLS = new Set([
    'XAUUSD', 'GOLD', 'XAGUSD', 'SILVER', 'USOIL', 'UKOIL', 'HGUSD',
    'US100', 'NAS100', 'USTEC', 'US500', 'SPX500', 'US30', 'DJ30', 'US2000',
    'GER40', 'DAX40', 'DE40', 'UK100', 'JP225', 'EU50',
    'EURUSD', 'GBPUSD', 'GBPJPY', 'USDJPY', 'AUDUSD', 'USDCAD', 'USDCHF', 'NZDUSD', 'EURJPY', 'EURGBP',
]);

/**
 * Identifica la categoría de mercado de un símbolo de forma estricta (SSoT):
 * - Todo par terminado en USDT pertenece a Bitunix (CRYPTO_ALTCOINS).
 * - Los activos TradFi (XAUUSD, US100, XAGUSD, UK100, etc.) pertenecen a FTMO_INSTITUTIONAL.
 */
export function getAssetMarketCategory(symbol: string): 'FTMO_INSTITUTIONAL' | 'CRYPTO_ALTCOINS' {
    const cleanSym = symbol.toUpperCase().replace('.CASH', '').replace('.S', '').replace('.P', '');
    if (cleanSym.endsWith('USDT')) {
        return 'CRYPTO_ALTCOINS';
    }
    if (
        FTMO_INSTITUTIONAL_SYMBOLS.has(cleanSym) ||
        cleanSym.startsWith('XAU') ||
        cleanSym.startsWith('XAG') ||
        cleanSym.startsWith('US100') ||
        cleanSym.startsWith('US500') ||
        cleanSym.startsWith('US30') ||
        cleanSym.startsWith('US2000') ||
        cleanSym.startsWith('UK100') ||
        cleanSym.startsWith('GER') ||
        cleanSym.startsWith('EU50') ||
        cleanSym.startsWith('USOIL') ||
        cleanSym.startsWith('UKOIL') ||
        cleanSym.startsWith('HG') ||
        cleanSym.startsWith('EUR') ||
        cleanSym.startsWith('GBP')
    ) {
        return 'FTMO_INSTITUTIONAL';
    }
    return 'CRYPTO_ALTCOINS';
}

/**
 * Calcula los lotes exactos para MetaTrader 5 sin mutilar sufijos USD de metales/FX.
 */
export function calculateMt5Lots(symbol: string, riskUsd: number, slDist: number): number {
    if (!slDist || slDist <= 0 || !riskUsd || riskUsd <= 0) return 0.01;

    const rawSym = symbol.toUpperCase().replace('.CASH', '').replace('.S', '').replace('.P', '');
    const isIndex = ['US100', 'NAS100', 'USTEC', 'US500', 'SPX500', 'US30', 'DJ30', 'US2000', 'UK100', 'EU50', 'JP225'].includes(rawSym);
    const contractSize = FTMO_CONTRACT_SIZES[rawSym] ?? (rawSym.length === 6 && !isIndex ? 100000 : 1);

    const rawLots = riskUsd / (slDist * contractSize);
    const minLot = isIndex ? 0.10 : 0.01;
    const rounded = Math.round(rawLots * 100) / 100;
    return Math.max(minLot, rounded);
}

/**
 * Calcula el nocional exacto en USDT para Bitunix Futures (SOP-41) con tope de apalancamiento.
 */
export function calculateBitunixPositionUsdt(
    equityUsd: number,
    riskPct: number,
    entryPrice: number,
    stopLoss: number,
    maxLeverageMult: number = 5.0
): number {
    if (equityUsd <= 0 || riskPct <= 0 || entryPrice <= 0) return 0;
    const dist = Math.abs(entryPrice - stopLoss);
    if (dist <= 0) return 0;
    const riskUsd = equityUsd * (riskPct / 100.0);
    const rawNotional = (riskUsd / dist) * entryPrice;
    const maxNotional = equityUsd * maxLeverageMult;
    return Math.round(Math.min(rawNotional, maxNotional) * 100) / 100;
}
