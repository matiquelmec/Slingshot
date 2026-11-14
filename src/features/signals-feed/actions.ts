'use server';

import { db, signals, requireUserSession, UserSession } from '@/shared';
import { eq, and, desc } from 'drizzle-orm';
import { QuantitativeSignal } from '@/entities';
import {
  fetchSignalsQuerySchema,
  createSignalInputSchema,
  type SignalActionResult,
} from './schemas';

export type { FetchSignalsQueryParams, CreateSignalInput, SignalActionResult } from './schemas';

/**
 * Fetch Signals from Turso with Multi-Tenant Anti-IDOR scoping.
 */
export async function fetchSignalsAction(
  rawParams?: unknown,
  mockSession?: UserSession
): Promise<SignalActionResult<QuantitativeSignal[]>> {
  try {
    const session = await requireUserSession(mockSession);
    const parsedParams = fetchSignalsQuerySchema.parse(rawParams || {});

    const conditions = [eq(signals.tenantId, session.tenantId)];

    if (parsedParams.asset && parsedParams.asset !== 'ALL') {
      conditions.push(eq(signals.asset, parsedParams.asset.toUpperCase()));
    }

    if (parsedParams.status && parsedParams.status !== 'ALL') {
      conditions.push(eq(signals.status, parsedParams.status));
    }

    const rows = await db
      .select()
      .from(signals)
      .where(and(...conditions))
      .orderBy(desc(signals.createdAt))
      .limit(parsedParams.limit);

    const safeDateIso = (val: unknown): string | undefined => {
      if (!val) return undefined;
      if (val instanceof Date) {
        if (isNaN(val.getTime())) return undefined;
        const normalized = val.getUTCFullYear() > 2100 ? new Date(Math.floor(val.getTime() / 1000)) : val;
        return isNaN(normalized.getTime()) ? undefined : normalized.toISOString();
      }
      if (typeof val === 'number') {
        const ms = val < 10000000000 ? val * 1000 : val;
        const d = new Date(ms);
        return isNaN(d.getTime()) ? undefined : d.toISOString();
      }
      if (typeof val === 'string') {
        const d = new Date(val);
        return isNaN(d.getTime()) ? undefined : d.toISOString();
      }
      return undefined;
    };

    const formatted: QuantitativeSignal[] = rows.map((r) => ({
      id: r.id,
      tenantId: r.tenantId,
      userId: r.userId,
      asset: r.asset,
      direction: r.direction as 'LONG' | 'SHORT',
      timeframe: (r.timeframe || '15m') as any,
      entryPrice: r.entryPrice,
      stopLoss: r.stopLoss,
      takeProfit1: r.takeProfit1 || r.entryPrice * 1.02,
      takeProfit2: r.takeProfit2 || r.entryPrice * 1.04,
      takeProfit3: r.takeProfit3 || r.entryPrice * 1.06,
      confluenceScore: r.confluenceScore,
      kerValue: r.kerValue,
      isExecutionAllowed: r.confluenceScore >= 70,
      status: (r.status || 'PENDING') as any,
      createdAt: safeDateIso(r.createdAt),
    }));

    return {
      success: true,
      data: formatted,
      count: formatted.length,
    };
  } catch (err: unknown) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Failed to fetch signals from Turso',
    };
  }
}

/**
 * Record a new Quantitative Signal directly to Turso.
 */
export async function recordSignalAction(
  rawInput: unknown,
  mockSession?: UserSession
): Promise<SignalActionResult<{ signalId: string }>> {
  const parseResult = createSignalInputSchema.safeParse(rawInput);
  if (!parseResult.success) {
    return {
      success: false,
      error: `Validation error: ${parseResult.error.issues.map((i) => i.message).join(', ')}`,
    };
  }

  const input = parseResult.data;

  try {
    const session = await requireUserSession(mockSession);
    const signalId = crypto.randomUUID();

    await db.insert(signals).values({
      id: signalId,
      tenantId: session.tenantId,
      userId: session.userId,
      asset: input.asset.toUpperCase(),
      direction: input.direction,
      timeframe: input.timeframe,
      entryPrice: input.entryPrice,
      stopLoss: input.stopLoss,
      takeProfit1: input.takeProfit1 ?? null,
      takeProfit2: input.takeProfit2 ?? null,
      takeProfit3: input.takeProfit3 ?? null,
      confluenceScore: input.confluenceScore,
      kerValue: input.kerValue,
      status: input.status,
    });

    return {
      success: true,
      data: { signalId },
    };
  } catch (err: unknown) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Database insert failed',
    };
  }
}
