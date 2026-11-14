import { z } from 'zod';

export const backtestAuditQuerySchema = z.object({
  playbook: z.enum(['ALL', 'LIQUIDITY_SWEEP_FVG', 'OB_DISCOUNT_RETEST']).default('ALL'),
  includeTearSheet: z.boolean().default(true),
});

export type BacktestAuditQueryParams = z.infer<typeof backtestAuditQuerySchema>;

export const theoryVsPracticeQuerySchema = z.object({
  comparisonScope: z
    .enum(['FULL_SPECTRUM', 'SL_TP_RELIABILITY', 'EXECUTION_FRICTION', 'CAPITAL_PRESERVATION'])
    .default('FULL_SPECTRUM'),
  assetFilter: z.string().default('ALL'),
});

export type TheoryVsPracticeQueryParams = z.infer<typeof theoryVsPracticeQuerySchema>;
