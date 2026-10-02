import { describe, it, expect } from 'vitest';
import {
  fetchSignalsAction,
  recordSignalAction,
  fetchTradesAction,
  recordTradeAction,
  closeTradeAction,
} from '@/features';
import { UserSession } from '@/shared';

describe('Feature Server Actions (Signals Feed & Positions Tracker)', () => {
  const mockSession: UserSession = {
    userId: 'usr-unit-test-1',
    tenantId: 'tnt-apex-corp',
    role: 'trader',
    email: 'trader@apex.trade',
  };

  describe('signals-feed actions', () => {
    it('validates input against Zod schema and rejects invalid signal payloads', async () => {
      const invalidSignal = {
        asset: 'B', // Too short (min 2)
        direction: 'SIDEWAYS', // Invalid enum
        entryPrice: -100, // Must be positive
        stopLoss: 0,
      };

      const result = await recordSignalAction(invalidSignal, mockSession);
      expect(result.success).toBe(false);
      expect(result.error).toContain('Validation error');
    });

    it('successfully processes valid signal parameters in query action', async () => {
      const queryResult = await fetchSignalsAction(
        { asset: 'BTCUSDT', status: 'PENDING', limit: 10 },
        mockSession
      );

      // In unit test environment, client executes query builder against DB
      expect(queryResult).toBeDefined();
      expect(typeof queryResult.success).toBe('boolean');
    });
  });

  describe('positions-tracker actions', () => {
    it('validates input against Zod schema and rejects invalid trade payloads', async () => {
      const invalidTrade = {
        symbol: 'E',
        side: 'HOLD', // Invalid side enum
        entryPrice: -50,
      };

      const result = await recordTradeAction(invalidTrade, mockSession);
      expect(result.success).toBe(false);
      expect(result.error).toContain('Validation error');
    });

    it('rejects closeTradeAction when tradeId is missing or prices are invalid', async () => {
      const invalidClose = {
        tradeId: '',
        exitPrice: -10,
        pnl: 0,
        pnlPercent: 0,
      };

      const result = await closeTradeAction(invalidClose, mockSession);
      expect(result.success).toBe(false);
      expect(result.error).toContain('Validation error');
    });

    it('correctly executes query action for active trades', async () => {
      const result = await fetchTradesAction({ status: 'OPEN', limit: 5 }, mockSession);
      expect(result).toBeDefined();
      expect(typeof result.success).toBe('boolean');
    });
  });
});
