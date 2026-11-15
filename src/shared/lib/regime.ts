/**
 * Normaliza regímenes del motor cuantitativo (e.g. STRONG_BEAR, HIGH_VOLATILITY_STRESS)
 * hacia las claves canónicas de Wyckoff usadas en la interfaz.
 */
const REGIME_ALIASES: Record<string, string> = {
  STRONG_BEAR: 'MARKDOWN',
  WEAK_BEAR: 'MARKDOWN',
  BEAR_EXPANSION: 'MARKDOWN',
  BEARISH: 'MARKDOWN',
  STRONG_BULL: 'MARKUP',
  WEAK_BULL: 'MARKUP',
  BULL_EXPANSION: 'MARKUP',
  BULLISH: 'MARKUP',
  HIGH_VOLATILITY_STRESS: 'CHOPPY',
  VOLATILE: 'CHOPPY',
  SIDEWAYS: 'RANGING',
  CONSOLIDATION: 'RANGING',
};

export function normalizeRegimeKey(regime?: string | null): string {
  const raw = (regime ?? 'UNKNOWN').toUpperCase();
  return REGIME_ALIASES[raw] ?? raw;
}
