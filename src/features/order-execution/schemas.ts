import { z } from 'zod';

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
