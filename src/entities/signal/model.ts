import { z } from 'zod';

export const signalDirectionSchema = z.enum(['LONG', 'SHORT']);

export const quantitativeSignalSchema = z.object({
  id: z.string(),
  userId: z.string(),
  tenantId: z.string(),
  asset: z.string().min(2).max(20),
  direction: signalDirectionSchema,
  timeframe: z.enum(['1m', '5m', '15m', '1h', '4h', '1d']).default('15m'),
  entryPrice: z.number().positive(),
  stopLoss: z.number().positive(),
  takeProfit1: z.number().positive(),
  takeProfit2: z.number().positive(),
  takeProfit3: z.number().positive(),
  confluenceScore: z.number().min(0).max(100),
  kerValue: z.number().min(0).max(1),
  isExecutionAllowed: z.boolean(),
  status: z.enum(['PENDING', 'TRIGGERED', 'CANCELLED', 'EXPIRED']).default('PENDING'),
  createdAt: z.string().optional(),
});

export type QuantitativeSignal = z.infer<typeof quantitativeSignalSchema>;
