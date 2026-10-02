import { describe, it, expect } from 'vitest';
import {
  CANONICAL_AUDITED_UNIVERSE,
  PRUNED_EXCLUDED_ASSETS,
  canonicalAssetSchema,
  isCanonicalAuditedAsset,
  isPrunedAsset,
} from '@/entities/signal';
import { MASTER_WATCHLIST } from '@/app/store/telemetry/constants';

describe('SSoT Canonical Audited Universe Contract (Paridad 1:1 Backtest vs Live)', () => {
  it('contains exactly 13 institutional canonical assets', () => {
    expect(CANONICAL_AUDITED_UNIVERSE).toHaveLength(13);
    const expectedAssets = [
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
    ];
    for (const asset of expectedAssets) {
      expect(CANONICAL_AUDITED_UNIVERSE).toContain(asset);
    }
  });

  it('strictly excludes pruned assets AVAXUSDT and RENDERUSDT from canonical universe', () => {
    for (const pruned of PRUNED_EXCLUDED_ASSETS) {
      expect(CANONICAL_AUDITED_UNIVERSE as readonly string[]).not.toContain(pruned);
      expect(isPrunedAsset(pruned)).toBe(true);
      expect(isCanonicalAuditedAsset(pruned)).toBe(false);
    }
  });

  it('validates canonical assets through Zod schema', () => {
    for (const asset of CANONICAL_AUDITED_UNIVERSE) {
      const parsed = canonicalAssetSchema.safeParse(asset);
      expect(parsed.success).toBe(true);
    }

    const invalidPruned = canonicalAssetSchema.safeParse('RENDERUSDT');
    expect(invalidPruned.success).toBe(false);

    const invalidRandom = canonicalAssetSchema.safeParse('DOGEUSDT');
    expect(invalidRandom.success).toBe(false);
  });

  it('ensures MASTER_WATCHLIST contains only valid canonical assets or spot proxy (PAXG)', () => {
    for (const sym of MASTER_WATCHLIST) {
      const isCanonicalOrProxy =
        isCanonicalAuditedAsset(sym) || sym === 'PAXGUSDT' || sym === 'XAUUSDT';
      expect(isCanonicalOrProxy).toBe(true);
      expect(isPrunedAsset(sym)).toBe(false);
    }
  });
});
