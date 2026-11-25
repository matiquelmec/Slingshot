import { describe, expect, it } from 'vitest';
import { getClientVenueLiquidityStatus } from '@/shared/lib/marketCalendar';

describe('SOP-160 Market Calendar (Client Mirror)', () => {
    it('blocks NYSE/CME on Good Friday and allows Crypto with thin liquidity flag', () => {
        const gf = new Date('2026-04-03T14:00:00Z');
        expect(getClientVenueLiquidityStatus(gf, 'US100.cash').execution_allowed).toBe(false);
        const btc = getClientVenueLiquidityStatus(gf, 'BTCUSDT');
        expect(btc.execution_allowed).toBe(true);
        expect(btc.liquidity_regime).toBe('US_BANK_HOLIDAY_THIN');
    });

    it('enforces Black Friday Early Close 13:00 NY cutoff at 12:30 NY', () => {
        const open = new Date('2026-11-27T15:00:00Z');
        const closed = new Date('2026-11-27T17:35:00Z');
        expect(getClientVenueLiquidityStatus(open, 'XAUUSD').execution_allowed).toBe(true);
        expect(getClientVenueLiquidityStatus(closed, 'XAUUSD').execution_allowed).toBe(false);
    });

    it('blocks UK100 on UK Summer Bank Holiday while US100 stays open', () => {
        const bh = new Date('2026-08-31T10:00:00Z');
        expect(getClientVenueLiquidityStatus(bh, 'UK100.cash').execution_allowed).toBe(false);
        expect(getClientVenueLiquidityStatus(bh, 'US100.cash').execution_allowed).toBe(true);
    });
});
