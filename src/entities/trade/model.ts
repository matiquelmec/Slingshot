import { z } from 'zod';

export const tradeSideSchema = z.enum(['BUY', 'SELL']);
export const tradeStatusSchema = z.enum(['OPEN', 'CLOSED', 'CANCELLED']);

export const tradeSchema = z.object({
  id: z.string().uuid().optional(),
  tenantId: z.string(),
  userId: z.string(),
  signalId: z.string().nullable().optional(),
  symbol: z.string().min(2).max(20),
  side: tradeSideSchema,
  entryPrice: z.number().positive(),
  exitPrice: z.number().positive().nullable().optional(),
  quantity: z.number().nonnegative().default(0),
  pnl: z.number().default(0),
  pnlPercent: z.number().default(0),
  status: tradeStatusSchema.default('OPEN'),
  createdAt: z.date().optional(),
  closedAt: z.date().nullable().optional(),
});

export type Trade = z.infer<typeof tradeSchema>;
