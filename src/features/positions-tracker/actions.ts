'use server';

import { z } from 'zod';
import { db, trades, requireUserSession, UserSession } from '@/shared';
import { eq, and, desc } from 'drizzle-orm';
import { tradeSchema, Trade } from '@/entities';

export const fetchTradesQuerySchema = z.object({
  status: z.enum(['ALL', 'OPEN', 'CLOSED', 'CANCELLED']).default('ALL'),
  symbol: z.string().optional(),
  limit: z.number().int().min(1).max(100).default(50),
});

export type FetchTradesQueryParams = z.infer<typeof fetchTradesQuerySchema>;

export const createTradeInputSchema = z.object({
  symbol: z.string().min(2).max(20),
  side: z.enum(['BUY', 'SELL']),
  entryPrice: z.number().positive(),
  exitPrice: z.number().positive().optional(),
  quantity: z.number().nonnegative().default(0),
  signalId: z.string().optional(),
  pnl: z.number().default(0),
  pnlPercent: z.number().default(0),
  status: z.enum(['OPEN', 'CLOSED', 'CANCELLED']).default('OPEN'),
});

export type CreateTradeInput = z.infer<typeof createTradeInputSchema>;

export const closeTradeInputSchema = z.object({
  tradeId: z.string().min(1),
  exitPrice: z.number().positive(),
  pnl: z.number(),
  pnlPercent: z.number(),
});

export type CloseTradeInput = z.infer<typeof closeTradeInputSchema>;

export interface TradeActionResult<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  count?: number;
}

/**
 * Fetch Trades from Turso with Multi-Tenant Anti-IDOR scoping.
 */
export async function fetchTradesAction(
  rawParams?: unknown,
  mockSession?: UserSession
): Promise<TradeActionResult<Trade[]>> {
  try {
    const session = await requireUserSession(mockSession);
    const params = fetchTradesQuerySchema.parse(rawParams || {});

    const conditions = [eq(trades.tenantId, session.tenantId)];

    if (params.symbol && params.symbol !== 'ALL') {
      conditions.push(eq(trades.symbol, params.symbol.toUpperCase()));
    }

    if (params.status && params.status !== 'ALL') {
      conditions.push(eq(trades.status, params.status));
    }

    const rows = await db
      .select()
      .from(trades)
      .where(and(...conditions))
      .orderBy(desc(trades.createdAt))
      .limit(params.limit);

    const formatted: Trade[] = rows.map((r) => ({
      id: r.id,
      tenantId: r.tenantId,
      userId: r.userId,
      signalId: r.signalId,
      symbol: r.symbol,
      side: r.side as 'BUY' | 'SELL',
      entryPrice: r.entryPrice,
      exitPrice: r.exitPrice,
      quantity: r.quantity,
      pnl: r.pnl ?? 0,
      pnlPercent: r.pnlPercent ?? 0,
      status: r.status as 'OPEN' | 'CLOSED' | 'CANCELLED',
      createdAt: r.createdAt ? new Date(r.createdAt) : undefined,
      closedAt: r.closedAt ? new Date(r.closedAt) : undefined,
    }));

    return {
      success: true,
      data: formatted,
      count: formatted.length,
    };
  } catch (err: unknown) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Failed to fetch trades from Turso',
    };
  }
}

/**
 * Record an executed position or trade into Turso.
 */
export async function recordTradeAction(
  rawInput: unknown,
  mockSession?: UserSession
): Promise<TradeActionResult<{ tradeId: string }>> {
  const parseResult = createTradeInputSchema.safeParse(rawInput);
  if (!parseResult.success) {
    return {
      success: false,
      error: `Validation error: ${parseResult.error.issues.map((i) => i.message).join(', ')}`,
    };
  }

  const input = parseResult.data;

  try {
    const session = await requireUserSession(mockSession);
    const tradeId = crypto.randomUUID();

    await db.insert(trades).values({
      id: tradeId,
      tenantId: session.tenantId,
      userId: session.userId,
      signalId: input.signalId ?? null,
      symbol: input.symbol.toUpperCase(),
      side: input.side,
      entryPrice: input.entryPrice,
      exitPrice: input.exitPrice ?? null,
      quantity: input.quantity,
      pnl: input.pnl,
      pnlPercent: input.pnlPercent,
      status: input.status,
    });

    return {
      success: true,
      data: { tradeId },
    };
  } catch (err: unknown) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Database insert failed',
    };
  }
}

/**
 * Close an active trade in Turso with strict tenant ownership check.
 */
export async function closeTradeAction(
  rawInput: unknown,
  mockSession?: UserSession
): Promise<TradeActionResult<{ closed: boolean }>> {
  const parseResult = closeTradeInputSchema.safeParse(rawInput);
  if (!parseResult.success) {
    return {
      success: false,
      error: `Validation error: ${parseResult.error.issues.map((i) => i.message).join(', ')}`,
    };
  }

  const input = parseResult.data;

  try {
    const session = await requireUserSession(mockSession);

    // Assert ownership before updating
    const existing = await db
      .select()
      .from(trades)
      .where(and(eq(trades.id, input.tradeId), eq(trades.tenantId, session.tenantId)))
      .limit(1);

    if (existing.length === 0) {
      return {
        success: false,
        error: 'Trade not found or access denied for this tenant',
      };
    }

    await db
      .update(trades)
      .set({
        exitPrice: input.exitPrice,
        pnl: input.pnl,
        pnlPercent: input.pnlPercent,
        status: 'CLOSED',
        closedAt: new Date(),
      })
      .where(and(eq(trades.id, input.tradeId), eq(trades.tenantId, session.tenantId)));

    return {
      success: true,
      data: { closed: true },
    };
  } catch (err: unknown) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Failed to close trade',
    };
  }
}
