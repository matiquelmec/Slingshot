import { describe, it, expect } from 'vitest';
import {
  fetchBacktestAuditMetricsAction,
  backtestAuditQuerySchema,
} from '@/features';
import { UserSession } from '@/shared';

describe('Features: Backtest Metrics Audit Slice (FSD & Zero Trust)', () => {
  const mockSession: UserSession = {
    userId: 'user_quant_auditor',
    tenantId: 'tenant_institutional_audit',
    email: 'auditor@slingshot.internal',
    role: 'trader',
  };

  it('debe validar los esquemas Zod de consulta correctamente', () => {
    const validParams = backtestAuditQuerySchema.parse({
      playbook: 'LIQUIDITY_SWEEP_FVG',
      includeTearSheet: true,
    });
    expect(validParams.playbook).toBe('LIQUIDITY_SWEEP_FVG');
    expect(validParams.includeTearSheet).toBe(true);

    const defaultParams = backtestAuditQuerySchema.parse({});
    expect(defaultParams.playbook).toBe('ALL');
    expect(defaultParams.includeTearSheet).toBe(true);
  });

  it('debe rechazar consultas con playbooks inválidos', () => {
    expect(() =>
      backtestAuditQuerySchema.parse({
        playbook: 'INVALID_PLAYBOOK',
      })
    ).toThrow();
  });

  it('debe retornar métricas auditadas con paridad SSoT v60.0 y sin ganancia fantasma', async () => {
    const result = await fetchBacktestAuditMetricsAction(
      { playbook: 'ALL' },
      mockSession
    );

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();

    const data = result.data!;
    expect(data.auditStatus).toBe('VERIFIED_SSOT_PARITY');
    expect(data.totalTrades).toBe(437);
    expect(data.winRatePct).toBe(44.9);
    expect(data.liveParityVerified).toBe(true);
    expect(data.phantomProfitCleared).toBe(true);

    // Paridad matemática estricta: órdenes límite TP1 @ 1.2R y TP2 @ 2.0R
    expect(data.profitFactorBase).toBe(1.62);
    expect(data.profitFactorAlphaTier).toBe(1.79);
    expect(data.totalNetRBase).toBe(97.98);
    expect(data.maxDrawdownAlphaTierPct).toBe(-4.76); // < 5.0% Blindaje FTMO
    expect(data.asymmetryRatio).toBe(2.2);

    expect(data.playbooks.length).toBe(2);
  });

  it('debe filtrar correctamente por playbook específico', async () => {
    const result = await fetchBacktestAuditMetricsAction(
      { playbook: 'OB_DISCOUNT_RETEST' },
      mockSession
    );

    expect(result.success).toBe(true);
    expect(result.data).toBeDefined();
    expect(result.data!.playbooks.length).toBe(1);
    expect(result.data!.playbooks[0].name).toBe('OB_DISCOUNT_RETEST');
    expect(result.data!.playbooks[0].profitFactor).toBe(1.91);
  });
});
