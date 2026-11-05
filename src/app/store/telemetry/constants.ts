export const MASTER_WATCHLIST = [
    "BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT", "LINKUSDT", "XRPUSDT", "XAUUSDT",
    "SUIUSDT", "INJUSDT", "NEARUSDT", "FETUSDT", "ATOMUSDT", "TIAUSDT"
];
export const APPROVED_SCALP_15M_ASSETS = [
    "BNBUSDT", "ETHUSDT", "SOLUSDT", "NEARUSDT", "FETUSDT", "INJUSDT", "ATOMUSDT"
];
export const APPROVED_SWING_1H_ASSETS = [
    "XAUUSDT", "BTCUSDT", "NEARUSDT", "ATOMUSDT"
];

export function getAssetExecutionBadge(symbol: string): {
    label: string;
    isExecutable: boolean;
    mode: 'DUAL' | 'SCALP_15M' | 'SWING_1H' | 'RADAR';
} {
    const clean = (symbol || '').replace(/[\s\/]/g, '').toUpperCase();
    const in15m = APPROVED_SCALP_15M_ASSETS.includes(clean);
    const in1h = APPROVED_SWING_1H_ASSETS.includes(clean);
    if (in15m && in1h) {
        return { label: 'DUAL 15M/1H', isExecutable: true, mode: 'DUAL' };
    }
    if (in15m) {
        return { label: 'EXEC 15M', isExecutable: true, mode: 'SCALP_15M' };
    }
    if (in1h) {
        return { label: 'EXEC 1H', isExecutable: true, mode: 'SWING_1H' };
    }
    return { label: 'RADAR', isExecutable: false, mode: 'RADAR' };
}

export const FTMO_WATCHLIST = [
    "XAUUSD", "XAGUSD", "US100", "US500", "USOIL", "GER40", "EURUSD", "USDJPY", "USDCAD", "GBPJPY"
];
export const STORAGE_KEY = 'slingshot_signal_history_v2';
export const CACHE_DURATION_MS = 2 * 60 * 60 * 1000;
export const MAX_RETRIES = 5;
