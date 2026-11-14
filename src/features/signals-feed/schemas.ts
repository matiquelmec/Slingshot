import { z } from 'zod';

export const fetchSignalsQuerySchema = z.object({
  asset: z.string().optional(),
  status: z
    .enum(['ALL', 'PENDING', 'TRIGGERED', 'FILLED', 'CANCELLED', 'EXPIRED'])
    .default('ALL'),
  limit: z.number().int().min(1).max(100).default(50),
});

export type FetchSignalsQueryParams = z.infer<typeof fetchSignalsQuerySchema>;

export const createSignalInputSchema = z.object({
  asset: z.string().min(2).max(20),
  direction: z.enum(['LONG', 'SHORT']),
  timeframe: z.string().default('15m'),
  entryPrice: z.number().positive(),
  stopLoss: z.number().positive(),
  takeProfit1: z.number().positive().optional(),
  takeProfit2: z.number().positive().optional(),
  takeProfit3: z.number().positive().optional(),
  confluenceScore: z.number().min(0).max(100).default(0),
  kerValue: z.number().min(0).max(1).default(0),
  status: z
    .enum(['PENDING', 'TRIGGERED', 'FILLED', 'CANCELLED', 'EXPIRED'])
    .default('PENDING'),
});

export type CreateSignalInput = z.infer<typeof createSignalInputSchema>;

export interface SignalActionResult<T = unknown> {
  success: boolean;
  data?: T;
  error?: string;
  count?: number;
}
