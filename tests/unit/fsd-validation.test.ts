import { describe, it, expect } from 'vitest';
import { tenantSchema, quantitativeSignalSchema } from '@/entities';
import { executeOrderAction } from '@/features/order-execution/actions';
import { UserSession } from '@/shared/auth';

describe('FSD Entities & Server Actions Contracts', () => {
  const mockSession: UserSession = {
    userId: 'user-001',
    tenantId: 'tenant-001',
    role: 'trader',
    email: 'trader@slingshot.internal',
  };

  const validSignal = {
    id: 'sig-888',
    userId: 'user-001',
    tenantId: 'tenant-001',
    asset: 'ETHUSDT',
    direction: 'LONG' as const,
    timeframe: '15m' as const,
    entryPrice: 2450.5,
    stopLoss: 2410.0,
    takeProfit1: 2510.0,
    takeProfit2: 2570.0,
    takeProfit3: 2650.0,
    confluenceScore: 82,
    kerValue: 0.42,
    isExecutionAllowed: true,
    status: 'PENDING' as const,
  };

  it('validates a compliant quantitative signal against domain schema', () => {
    const parseResult = quantitativeSignalSchema.safeParse(validSignal);
    expect(parseResult.success).toBe(true);
  });

  it('rejects invalid signals with negative prices or invalid KER values', () => {
    const invalidSignal = {
      ...validSignal,
      entryPrice: -100,
      kerValue: 1.5, // KER must be between 0 and 1
    };

    const parseResult = quantitativeSignalSchema.safeParse(invalidSignal);
    expect(parseResult.success).toBe(false);
  });

  it('validates a compliant tenant schema', () => {
    const tenant = {
      id: 'a0eebc99-9c0b-4ef8-bb6d-6bb9bd380a11',
      name: 'Slingshot Institutional Fund',
      tier: 'institutional' as const,
      maxConcurrentPositions: 10,
      status: 'active' as const,
    };

    const parseResult = tenantSchema.safeParse(tenant);
    expect(parseResult.success).toBe(true);
  });

  it('executes order Server Action successfully when inputs and tenant session match', async () => {
    const input = {
      signalId: 'sig-888',
      asset: 'ETHUSDT',
      direction: 'LONG' as const,
      orderType: 'LIMIT' as const,
      price: 2450.5,
      stopLoss: 2410.0,
      positionSizeUsdt: 500,
    };

    const result = await executeOrderAction(input, validSignal, mockSession);
    expect(result.success).toBe(true);
    expect(result.orderId).toBeDefined();
    expect(result.tenantId).toBe('tenant-001');
  });

  it('fails Server Action execution when input validation fails', async () => {
    const invalidInput = {
      signalId: '',
      asset: 'E', // Too short
      direction: 'INVALID_DIRECTION',
      price: -10,
    };

    const result = await executeOrderAction(invalidInput, validSignal, mockSession);
    expect(result.success).toBe(false);
    expect(result.error).toContain('Invalid input');
  });

  it('blocks Server Action execution on tenant ownership mismatch', async () => {
    const input = {
      signalId: 'sig-888',
      asset: 'ETHUSDT',
      direction: 'LONG' as const,
      orderType: 'LIMIT' as const,
      price: 2450.5,
      stopLoss: 2410.0,
      positionSizeUsdt: 500,
    };

    const foreignSession: UserSession = {
      userId: 'user-intruder',
      tenantId: 'tenant-002',
      role: 'trader',
      email: 'intruder@external.io',
    };

    const result = await executeOrderAction(input, validSignal, foreignSession);
    expect(result.success).toBe(false);
    expect(result.error).toContain('Tenant violation');
  });
});
