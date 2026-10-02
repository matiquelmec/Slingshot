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

