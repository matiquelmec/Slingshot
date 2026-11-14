import { z } from 'zod';

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
