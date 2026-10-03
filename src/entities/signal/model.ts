import { z } from 'zod';

export const signalDirectionSchema = z.enum(['LONG', 'SHORT']);

export const quantitativeSignalSchema = z.object({
  id: z.string(),
  userId: z.string(),
  tenantId: z.string(),
  asset: z.string().min(2).max(20),
  direction: signalDirectionSchema,
  timeframe: z.enum(['1m', '5m', '15m', '1h', '4h', '1d']).default('15m'),
  entryPrice: z.number().positive(),
  stopLoss: z.number().positive(),
  takeProfit1: z.number().positive(),
  takeProfit2: z.number().positive(),
  takeProfit3: z.number().positive(),
  confluenceScore: z.number().min(0).max(100),
  kerValue: z.number().min(0).max(1),
  isExecutionAllowed: z.boolean(),
  status: z.enum(['PENDING', 'TRIGGERED', 'CANCELLED', 'EXPIRED']).default('PENDING'),
  createdAt: z.string().optional(),
});

export type QuantitativeSignal = z.infer<typeof quantitativeSignalSchema>;

/**
 * Universo Canónico Auditado en Backtest SSoT (13 Activos de Grado Institucional)
 * Cumple paridad estricta 1:1 con CANONICAL_AUDITED_UNIVERSE en engine/execution/nexus.py.
 */
export const CANONICAL_AUDITED_UNIVERSE = [
  'BTCUSDT',
  'ETHUSDT',
  'SOLUSDT',
  'BNBUSDT',
  'LINKUSDT',
  'XRPUSDT',
  'XAUUSDT',
  'SUIUSDT',
  'INJUSDT',
  'NEARUSDT',
  'FETUSDT',
  'ATOMUSDT',
  'TIAUSDT',
] as const;

/**
 * Activos podados de ejecución por expectativa matemática negativa auditada (SOP-102).
 */
export const PRUNED_EXCLUDED_ASSETS = ['AVAXUSDT', 'RENDERUSDT'] as const;

export const canonicalAssetSchema = z.enum(CANONICAL_AUDITED_UNIVERSE);
export type CanonicalAsset = z.infer<typeof canonicalAssetSchema>;

export function isCanonicalAuditedAsset(asset: string): asset is CanonicalAsset {
  return (CANONICAL_AUDITED_UNIVERSE as readonly string[]).includes(asset.toUpperCase());
}

export function isPrunedAsset(asset: string): boolean {
  return (PRUNED_EXCLUDED_ASSETS as readonly string[]).includes(asset.toUpperCase());
}

/**
 * Perfil analítico cuantitativo por activo auditado (SSoT v60.0).
 */
export interface AssetQuantitativeProfile {
  asset: CanonicalAsset;
  tier: 'TIER_S_CHAMPION' | 'TIER_A_HIGH_BETA' | 'TIER_B_CORE' | 'TIER_C_MACRO_PILLAR' | 'TIER_TRADFI_METALS';
  timeframeRole: '15M_SCALP_PURE' | '1H_SWING_PURE' | 'DUAL_15M_1H';
  alphaKellyMultiplier: number;
  historicalProfitFactor: number;
  netContributionR: number;
  reasonWhyTraded: string;
}

export const CANONICAL_ASSET_PROFILES: Record<CanonicalAsset, AssetQuantitativeProfile> = {
  FETUSDT: {
    asset: 'FETUSDT',
    tier: 'TIER_S_CHAMPION',
    timeframeRole: '15M_SCALP_PURE',
    alphaKellyMultiplier: 1.40,
    historicalProfitFactor: 2.75,
    netContributionR: 16.60,
    reasonWhyTraded: 'Campeón de Alpha (Trinidad). Alta reactividad a OBs y FVGs con expansión simétrica en 15m.',
  },
  INJUSDT: {
    asset: 'INJUSDT',
    tier: 'TIER_A_HIGH_BETA',
    timeframeRole: 'DUAL_15M_1H',
    alphaKellyMultiplier: 1.25,
    historicalProfitFactor: 1.68,
    netContributionR: 14.80,
    reasonWhyTraded: 'Alto beta y volumen institucional constante. Óptima captura de tendencias limpias sin falsos quiebres.',
  },
  BNBUSDT: {
    asset: 'BNBUSDT',
    tier: 'TIER_A_HIGH_BETA',
    timeframeRole: '15M_SCALP_PURE',
    alphaKellyMultiplier: 1.25,
    historicalProfitFactor: 2.82,
    netContributionR: 25.05,
    reasonWhyTraded: 'Trinidad del Alfa. Mayor contribución neta en 15m con bajo deslizamiento y alta profundidad de libro.',
  },
  SOLUSDT: {
    asset: 'SOLUSDT',
    tier: 'TIER_B_CORE',
    timeframeRole: '15M_SCALP_PURE',
    alphaKellyMultiplier: 1.20,
    historicalProfitFactor: 2.71,
    netContributionR: 22.34,
    reasonWhyTraded: 'Trinidad del Alfa. Liquidez masiva, spreads sub-0.03% y explosividad estructural en sesiones Londres/NY.',
  },
  NEARUSDT: {
    asset: 'NEARUSDT',
    tier: 'TIER_A_HIGH_BETA',
    timeframeRole: 'DUAL_15M_1H',
    alphaKellyMultiplier: 1.25,
    historicalProfitFactor: 1.64,
    netContributionR: 12.40,
    reasonWhyTraded: 'Líder en continuidad fractal. Excelente sinergia entre barridos de 1h y descuento OTE en 15m.',
  },
  SUIUSDT: {
    asset: 'SUIUSDT',
    tier: 'TIER_B_CORE',
    timeframeRole: '15M_SCALP_PURE',
    alphaKellyMultiplier: 1.00,
    historicalProfitFactor: 1.42,
    netContributionR: 5.93,
    reasonWhyTraded: 'Régimen de alta volatilidad y momentum independiente con desacoplamiento positivo de BTC.',
  },
  ATOMUSDT: {
    asset: 'ATOMUSDT',
    tier: 'TIER_B_CORE',
    timeframeRole: 'DUAL_15M_1H',
    alphaKellyMultiplier: 1.00,
    historicalProfitFactor: 1.56,
    netContributionR: 6.80,
    reasonWhyTraded: 'Consistencia en retrocesos a descuento (OB Retest) con bajo costo de financiamiento en Bitunix.',
  },
  TIAUSDT: {
    asset: 'TIAUSDT',
    tier: 'TIER_B_CORE',
    timeframeRole: '15M_SCALP_PURE',
    alphaKellyMultiplier: 1.00,
    historicalProfitFactor: 1.38,
    netContributionR: 4.50,
    reasonWhyTraded: 'Activo de rotación con volumen superior a $40M USDT y respeto de zonas de liquidez SSL/BSL.',
  },
  BTCUSDT: {
    asset: 'BTCUSDT',
    tier: 'TIER_C_MACRO_PILLAR',
    timeframeRole: 'DUAL_15M_1H',
    alphaKellyMultiplier: 0.75,
    historicalProfitFactor: 1.67,
    netContributionR: 10.20,
    reasonWhyTraded: 'Ancla macro institucional. Permite apalancamiento seguro 18x por estrecho SL y define el sesgo direccional.',
  },
  ETHUSDT: {
    asset: 'ETHUSDT',
    tier: 'TIER_C_MACRO_PILLAR',
    timeframeRole: 'DUAL_15M_1H',
    alphaKellyMultiplier: 0.75,
    historicalProfitFactor: 1.82,
    netContributionR: 11.50,
    reasonWhyTraded: 'Pilar sistémico. Máxima liquidez y confluencia limpia con las aperturas europeas y americanas.',
  },
  LINKUSDT: {
    asset: 'LINKUSDT',
    tier: 'TIER_C_MACRO_PILLAR',
    timeframeRole: 'DUAL_15M_1H',
    alphaKellyMultiplier: 0.75,
    historicalProfitFactor: 1.58,
    netContributionR: 7.10,
    reasonWhyTraded: 'Fuerte resiliencia estructural. Excelente tasa de TP1 (+1.2R) con rápida transición a Breakeven.',
  },
  XRPUSDT: {
    asset: 'XRPUSDT',
    tier: 'TIER_C_MACRO_PILLAR',
    timeframeRole: '15M_SCALP_PURE',
    alphaKellyMultiplier: 0.75,
    historicalProfitFactor: 1.25,
    netContributionR: 4.30,
    reasonWhyTraded: 'Volumen denso con libro de órdenes profundo. Amortiguado defensivamente por menor reactividad.',
  },
  XAUUSDT: {
    asset: 'XAUUSDT',
    tier: 'TIER_TRADFI_METALS',
    timeframeRole: '1H_SWING_PURE',
    alphaKellyMultiplier: 1.15,
    historicalProfitFactor: 1.97,
    netContributionR: 11.30,
    reasonWhyTraded: 'Descorrelación macro absoluta (rho < 0.35 frente a cripto). Libera slots bajo SOP-99 sin stacking direccional.',
  },
};

/**
 * Esquema Zod de Graduación de Order Blocks y Gravedad de Liquidación (SOP-112).
 */
export const orderBlockDetailSchema = z.object({
  top: z.number().positive(),
  bottom: z.number().positive(),
  volumeRatio: z.number().nonnegative(),
  strengthScore: z.number().min(0).max(100),
  touchCount: z.number().int().nonnegative(),
  isVirgin: z.boolean(),
  statusLabel: z.enum(['TIER_1_VIRGIN_ELITE', 'TESTED_ACTIVE', 'EXHAUSTED_WARNING']),
});

export const nearestLiquidityClusterSchema = z.object({
  price: z.number().positive(),
  type: z.enum(['LONG_LIQ', 'SHORT_LIQ']),
  strength: z.number().min(0).max(100),
  distancePct: z.number().nonnegative(),
  isMagnetic: z.boolean(),
});

export const obLiquidityAuditReportSchema = z.object({
  asset: z.string().min(2).max(20),
  activeObsCount: z.number().int().nonnegative(),
  virginObsCount: z.number().int().nonnegative(),
  dominantOb: orderBlockDetailSchema.nullable(),
  nearestLiqCluster: nearestLiquidityClusterSchema.nullable(),
  hasDualConfluence: z.boolean(),
  confluenceScoreBonus: z.number().nonnegative(),
  weightingRating: z.enum(['OPTIMA_INSTITUTIONAL', 'FUERTE', 'CAUTELA_EXHAUSTION']),
  recommendation: z.string(),
});

export type OrderBlockDetail = z.infer<typeof orderBlockDetailSchema>;
export type NearestLiquidityCluster = z.infer<typeof nearestLiquidityClusterSchema>;
export type ObLiquidityAuditReport = z.infer<typeof obLiquidityAuditReportSchema>;


