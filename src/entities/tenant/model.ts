import { z } from 'zod';

export const tenantSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(2).max(100),
  tier: z.enum(['starter', 'pro', 'institutional']).default('starter'),
  maxConcurrentPositions: z.number().int().positive().default(3),
  status: z.enum(['active', 'suspended', 'archived']).default('active'),
  createdAt: z.string().datetime().optional(),
});

export type Tenant = z.infer<typeof tenantSchema>;
