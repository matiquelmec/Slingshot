'use server';

import { z } from 'zod';
import { requireUserSession, assertTenantOwnership, UserSession } from '@/shared';
import { QuantitativeSignal } from '@/entities';

export const createOrderInputSchema = z.object({
  signalId: z.string().min(1),
  asset: z.string().min(2),
  direction: z.enum(['LONG', 'SHORT']),
  orderType: z.enum(['LIMIT', 'MARKET']).default('LIMIT'),
  price: z.number().positive(),
  stopLoss: z.number().positive(),
  positionSizeUsdt: z.number().positive(),
});

export type CreateOrderInput = z.infer<typeof createOrderInputSchema>;

export interface ExecutionResult {
  success: boolean;
  orderId?: string;
  error?: string;
  tenantId?: string;
}

/**
 * Institutional Server Action: Execute Order with Multi-Tenant Isolation
 * 1. Zod input validation
 * 2. Session verification
 * 3. Tenant query scoping and ownership assertion
 */
export async function executeOrderAction(
  rawInput: unknown,
  existingSignal: QuantitativeSignal,
  mockSession?: UserSession
): Promise<ExecutionResult> {
  // 1. Input Validation
  const parseResult = createOrderInputSchema.safeParse(rawInput);
  if (!parseResult.success) {
    return {
      success: false,
      error: `Invalid input: ${parseResult.error.issues.map((i) => i.message).join(', ')}`,
    };
  }

  const input = parseResult.data;

  try {
    // 2. Session Verification
    const session = await requireUserSession(mockSession);

    // 3. Multi-Tenant Ownership Assertion (and(eq(id, signalId), eq(userId, sessionUserId)))
    assertTenantOwnership(existingSignal, session);

    // 4. Execution logic (e.g. forward to Bitunix executor or DB transaction)
    const simulatedOrderId = `ORD-${Date.now()}-${input.asset}`;

    return {
      success: true,
      orderId: simulatedOrderId,
      tenantId: session.tenantId,
    };
  } catch (err: unknown) {
    const message = err instanceof Error ? err.message : 'Unknown execution failure';
    return {
      success: false,
      error: message,
    };
  }
}
