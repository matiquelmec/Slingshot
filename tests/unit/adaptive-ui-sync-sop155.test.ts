import { describe, it, expect } from 'vitest';
import fs from 'node:fs';
import path from 'node:path';
import {
  FTMO_SWING_AUDITED_UNIVERSE,
  getAssetMarketCategory,
  calculateMt5Lots,
  calculateBitunixPositionUsdt,
} from '@/app/utils/ftmoSpecs';
import { useAccountTelemetryStore } from '@/app/store/accountTelemetryStore';

describe('SOP-155: Adaptive Multi-Account UI Sync & Universe Separation', () => {
  it('strictly classifies all 13 Bitunix *USDT pairs as CRYPTO_ALTCOINS and 4 FTMO Swing assets as FTMO_INSTITUTIONAL', () => {
    const bitunix13 = [
      'BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'LINKUSDT', 'XRPUSDT',
      'XAUUSDT', 'SUIUSDT', 'INJUSDT', 'NEARUSDT', 'FETUSDT', 'ATOMUSDT', 'TIAUSDT',
    ];
    for (const sym of bitunix13) {
      expect(getAssetMarketCategory(sym)).toBe('CRYPTO_ALTCOINS');
    }
    for (const sym of FTMO_SWING_AUDITED_UNIVERSE) {
      expect(getAssetMarketCategory(sym)).toBe('FTMO_INSTITUTIONAL');
    }
    expect(getAssetMarketCategory('US100.cash')).toBe('FTMO_INSTITUTIONAL');
    expect(getAssetMarketCategory('UK100.cash')).toBe('FTMO_INSTITUTIONAL');
  });

  it('computes accurate MT5 lots without mangling USD suffixes and accurate Bitunix USDT notional', () => {
    expect(calculateMt5Lots('XAUUSD', 750, 10)).toBe(0.75);
    expect(calculateMt5Lots('XAGUSD', 750, 0.30)).toBe(0.5);
    expect(calculateMt5Lots('US100', 750, 50)).toBe(15);
    expect(calculateMt5Lots('UK100', 750, 25)).toBe(30);

    const notional = calculateBitunixPositionUsdt(1000, 2.5, 100, 98, 5.0);
    expect(notional).toBe(1250);
  });

  it('resolves dynamic FTMO Swing and Bitunix configs in accountTelemetryStore', () => {
    const store = useAccountTelemetryStore.getState();
    const ftmo50 = store.getResolvedFtmoConfig(50000, 'PHASE_1');
    expect(ftmo50.riskUsd).toBe(375);
    expect(ftmo50.riskPct).toBe(0.75);

    const ftmo200p2 = store.getResolvedFtmoConfig(200000, 'PHASE_2');
    expect(ftmo200p2.riskUsd).toBe(1000);
    expect(ftmo200p2.riskPct).toBe(0.5);

    const bitunix = store.getResolvedBitunixConfig();
    expect(bitunix.platform).toBe('BITUNIX');
    expect(bitunix.riskPct).toBe(2.5);
  });

  it('removes pruned assets AVAX, RENDER, US30, and GBPUSD from Radar and FTMO UI copy', () => {
    const root = process.cwd();
    const scanner = fs.readFileSync(path.join(root, 'src/app/components/radar/OpportunitiesScanner.tsx'), 'utf8');
    const ftmoView = fs.readFileSync(path.join(root, 'src/app/(dashboard)/ftmo/FtmoTerminalView.tsx'), 'utf8');

    expect(scanner).not.toContain('RENDER');
    expect(scanner).not.toContain('AVAX');
    expect(ftmoView).not.toContain('US30');
    expect(ftmoView).not.toContain('GBPUSD');
  });
});
