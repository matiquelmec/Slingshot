import { z } from 'zod';

export const userRoleSchema = z.enum(['admin', 'trader', 'viewer']);

export const userSchema = z.object({
  id: z.string().uuid().optional(),
  tenantId: z.string(),
  email: z.string().email(),
  role: userRoleSchema.default('trader'),
  createdAt: z.date().optional(),
  updatedAt: z.date().optional(),
});

export type User = z.infer<typeof userRoleSchema>;
