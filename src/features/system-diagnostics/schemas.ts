import { z } from 'zod';

export const systemDiagnosticsQuerySchema = z.object({
  includeDatabaseCheck: z.boolean().default(true),
  assetFilter: z.string().max(20).optional().default('ALL'),
});

export type SystemDiagnosticsQueryParams = z.infer<typeof systemDiagnosticsQuerySchema>;

export const multiYearCycleQuerySchema = z.object({
  targetBtcPrice: z.number().positive().optional().default(84600.0),
  includeDetailedPhases: z.boolean().optional().default(true),
});

export type MultiYearCycleQueryParams = z.infer<typeof multiYearCycleQuerySchema>;

export const monteCarloQuerySchema = z.object({
  iterations: z.number().int().min(1000).max(50000).optional().default(10000),
  horizonTrades: z.number().int().min(20).max(500).optional().default(100),
});

export type MonteCarloQueryParams = z.infer<typeof monteCarloQuerySchema>;

export const fullStackSyncQuerySchema = z.object({
  targetVpsUrl: z
    .string()
    .url()
    .optional()
    .default(
      process.env.BACKEND_INTERNAL_URL ||
        process.env.NEXT_PUBLIC_API_URL ||
        'http://127.0.0.1:8000'
    ),
});

export type FullStackSyncQueryParams = z.input<typeof fullStackSyncQuerySchema>;
