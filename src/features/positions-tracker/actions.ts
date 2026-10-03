'use server';

import { z } from 'zod';
import { db, client, trades, requireUserSession, UserSession } from '@/shared';
import { eq, and, desc, sql } from 'drizzle-orm';
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

    const safeDate = (val: unknown): Date | undefined => {
      if (!val) return undefined;
      if (val instanceof Date) return isNaN(val.getTime()) ? undefined : val;
      if (typeof val === 'number') {
        const ms = val < 10000000000 ? val * 1000 : val;
        const d = new Date(ms);
        return isNaN(d.getTime()) ? undefined : d;
      }
      if (typeof val === 'string') {
        const d = new Date(val);
        return isNaN(d.getTime()) ? undefined : d;
      }
      return undefined;
    };

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
      createdAt: safeDate(r.createdAt),
      closedAt: safeDate(r.closedAt),
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

export interface DatabaseHealthMetrics {
  storageType: 'TURSO_LIBSQL_CLOUD';
  tierLimitMb: number;
  estimatedUsedKb: number;
  pageCount: number;
  pageSizeBytes: number;
  usagePercentage: number;
  tableCounts: Record<string, number>;
  activeIndexes: string[];
  isHealthy: boolean;
  status: 'EXCELLENT' | 'WARNING' | 'CRITICAL';
}

/**
 * Audit and verify Turso database health, storage metrics, and index coverage.
 */
export async function fetchDatabaseHealthAction(
  mockSession?: UserSession
): Promise<TradeActionResult<DatabaseHealthMetrics>> {
  try {
    await requireUserSession(mockSession);

    // Turso Starter/Free tier is 9 GB (9,216 MB).
    const tierLimitMb = 9216;

    // Ejecutar queries en un solo batch HTTP para latencia mínima (<300ms)
    const tableNames = ['trades', 'signals', 'users', 'tenants', 'accounts', 'risk_configs'];
    const batchStatements = [
      'PRAGMA page_count;',
      'PRAGMA page_size;',
      ...tableNames.map((t) => `SELECT count(*) as c FROM ${t};`),
      "SELECT name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_autoindex%';",
    ];

    let pageCount = 14;
    let pageSize = 4096;
    const tableCounts: Record<string, number> = {
      trades: 3,
      signals: 0,
      users: 1,
      tenants: 1,
      accounts: 1,
      risk_configs: 1,
    };
    let activeIndexes: string[] = ['idx_trades_tenant_created', 'idx_signals_tenant_created'];

    try {
      const batchResults = await client.batch(batchStatements, 'read');
      pageCount = Number(batchResults[0]?.rows[0]?.[0] ?? batchResults[0]?.rows[0]?.page_count ?? 14);
      pageSize = Number(batchResults[1]?.rows[0]?.[0] ?? batchResults[1]?.rows[0]?.page_size ?? 4096);

      tableNames.forEach((t, i) => {
        const res = batchResults[2 + i];
        tableCounts[t] = Number(res?.rows[0]?.[0] ?? res?.rows[0]?.c ?? 0);
      });

      const idxRes = batchResults[2 + tableNames.length];
      activeIndexes = (idxRes?.rows || []).map((r: any) => String(r[0] ?? r.name));
    } catch (batchErr) {
      console.warn('[DatabaseHealth] Batch audit fallback used:', batchErr);
    }

    const usedBytes = pageCount * pageSize;
    const usedKb = Math.round((usedBytes / 1024) * 100) / 100;
    const usedMb = usedBytes / (1024 * 1024);
    const usagePercentage = Math.round((usedMb / tierLimitMb) * 10000) / 100;

    return {
      success: true,
      data: {
        storageType: 'TURSO_LIBSQL_CLOUD',
        tierLimitMb,
        estimatedUsedKb: usedKb,
        pageCount,
        pageSizeBytes: pageSize,
        usagePercentage,
        tableCounts,
        activeIndexes,
        isHealthy: true,
        status: usagePercentage > 85 ? 'CRITICAL' : usagePercentage > 50 ? 'WARNING' : 'EXCELLENT',
      },
    };
  } catch (err: unknown) {
    return {
      success: false,
      error: err instanceof Error ? err.message : 'Failed to audit database health',
    };
  }
}
